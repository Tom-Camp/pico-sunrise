"""A simulated Pico that runs the real main.py and lib/*.py against fake hardware.

Real time and the board's clock are tracked separately. The board's clock starts unset and is only
correct after a successful NTP sync. Nothing is added to sys.modules: firmware code gets its imports
from Board._import, so it can only see what the board provides.
"""

import builtins
import calendar
import time
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
EASTERN = ZoneInfo("America/New_York")
UNSET_CLOCK = calendar.timegm((2021, 1, 1, 0, 0, 0))
WEEK = [(5, 45)] * 5 + [(6, 0)] * 2
WIFI_CONNECT_SECONDS = 3


class SimulationOver(BaseException):
    """The simulated period has ended."""


class Stuck(BaseException):
    """The firmware is busy-looping without letting time pass."""


class BoardReset(BaseException):
    """machine.reset() was called."""


def eastern(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)


class Board:
    """
    start: Eastern time at power-on
    days: how long to simulate
    wifi_outages, ntp_outages: (from, to) hours after power-on
    drift_ppm: how fast (positive) or slow (negative) the board's clock and sleeps run
    sync_error_at: hours after power-on when one NTP sync raises a non-OSError
    """

    def __init__(self, start, days=1, wifi_outages=(), ntp_outages=(), drift_ppm=0, sync_error_at=None):
        self.start = eastern(start).timestamp()
        self.end = self.start + days * 86400
        self.now = self.start
        self.wifi_outages = wifi_outages
        self.ntp_outages = ntp_outages
        self.rate = 1 + drift_ppm / 1e6
        self.sync_error_at = sync_error_at
        self.sunrises = []
        self.negative_sleeps = []
        self.resets = 0
        self.failed_connects = 0
        self.power_on()

    # Time

    def power_on(self):
        self._clock_value, self._clock_set_at = UNSET_CLOCK, self.now
        self._modules = {}
        self._connected_at = None
        self._radio_on = False
        self._polls = 0
        self._lit = False

    def clock(self) -> int:
        return int(self._clock_value + (self.now - self._clock_set_at) * self.rate)

    def set_clock(self):
        self._clock_value, self._clock_set_at = self.now, self.now

    def hours(self, t=None) -> float:
        return ((self.now if t is None else t) - self.start) / 3600

    def local(self) -> datetime:
        return datetime.fromtimestamp(self.now, EASTERN)

    def _sleep(self, seconds):
        self._polls = 0
        if seconds < 0:
            self.negative_sleeps.append(seconds)
            return
        self.now += seconds / self.rate
        if self.now > self.end:
            raise SimulationOver

    # Network

    def _outage_between(self, start, end) -> bool:
        return any(a <= self.hours(end) and self.hours(start) < b for a, b in self.wifi_outages)

    def connected(self) -> bool:
        self._polls += 1
        if self._polls > 1000:
            raise Stuck(f"polling WiFi without sleeping at {self.local()}")
        if not self._radio_on or self._connected_at is None:
            return False
        # Like the real radio, a dropped link does not come back without connect()
        if self._outage_between(self._connected_at - WIFI_CONNECT_SECONDS, self.now):
            return False
        return self.now >= self._connected_at

    def _settime(self):
        if not self.connected():
            raise OSError("no link")
        if any(a <= self.hours() < b for a, b in self.ntp_outages):
            raise OSError("NTP timeout")
        if self.sync_error_at is not None and self.hours() >= self.sync_error_at:
            self.sync_error_at = None
            raise ValueError("simulated driver error")
        self.set_clock()

    # Fake MicroPython modules

    def _fake(self, name):
        board = self

        class WLAN:
            def __init__(self, interface):
                pass

            def active(self, on):
                board._radio_on = on
                if not on:
                    board._connected_at = None

            def connect(self, ssid, password):
                board._connected_at = board.now + WIFI_CONNECT_SECONDS
                if board._outage_between(board.now, board._connected_at):
                    board.failed_connects += 1

            def isconnected(self):
                return board.connected()

            def ifconfig(self):
                return ("192.0.2.2", "255.255.255.0", "192.0.2.1", "192.0.2.1")

        class NeoPixel(list):
            def __init__(self, pin, n):
                super().__init__([(0, 0, 0)] * n)

            def fill(self, color):
                self[:] = [color] * len(self)

            def write(self):
                lit = any(any(pixel) for pixel in self)
                if lit and not board._lit:
                    board.sunrises.append(board.local())
                board._lit = lit

        def reset():
            board.resets += 1
            raise BoardReset

        def mktime(value):
            if len(value) not in (8, 9):
                raise TypeError("mktime needs a tuple of length 8 or 9")
            return calendar.timegm(value[:6])

        fakes = {
            "machine": {"Pin": lambda n: n, "reset": reset},
            "neopixel": {"NeoPixel": NeoPixel},
            "network": {"WLAN": WLAN, "STA_IF": 0},
            "ntptime": {"settime": self._settime},
            "secrets": {"SSID": "test", "PASSWORD": "test"},
            "time": {
                "sleep": self._sleep,
                "time": self.clock,
                # MicroPython returns 8 elements, CPython 9
                "localtime": lambda t: tuple(time.gmtime(t))[:8],
                "mktime": mktime,
            },
            # Fixed so that changing your own wake times doesn't break the tests
            "lib.configuration": {"config": {"week": WEEK, "color": (51, 153, 255), "delay": 60}},
        }
        if name not in fakes:
            return None
        module = types.ModuleType(name)
        vars(module).update(fakes[name])
        return module

    # Running firmware code

    def _import(self, name, globals=None, locals=None, fromlist=(), level=0):
        return self.load(name)

    def _execute(self, path: Path, namespace: dict):
        namespace["__builtins__"] = {**vars(builtins), "__import__": self._import}
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)

    def load(self, name):
        """Return a firmware module: a fake if there is one, otherwise the real file."""
        if name not in self._modules:
            module = self._fake(name)
            if module is None:
                path = ROOT / (name.replace(".", "/") + ".py")
                if not name.startswith("lib.") or not path.exists():
                    raise ImportError(f"the board has no module {name!r}")
                module = types.ModuleType(name)
                self._execute(path, vars(module))
            self._modules[name] = module
        return self._modules[name]

    def run(self):
        """Run main.py, rebooting on machine.reset(), until the simulated period ends."""
        while True:
            try:
                self._execute(ROOT / "main.py", {"__name__": "__main__"})
                raise AssertionError("main.py returned")
            except BoardReset:
                self.power_on()
            except SimulationOver:
                return self

    # Results

    def expected_alarms(self):
        """Alarm times in the simulated period, from the real timezone database."""
        alarms = []
        day = datetime.fromtimestamp(self.start, EASTERN).date()
        while True:
            alarm = datetime(day.year, day.month, day.day, *WEEK[day.weekday()], tzinfo=EASTERN)
            if alarm.timestamp() > self.end:
                return alarms
            if alarm.timestamp() > self.start:
                alarms.append(alarm)
            day += timedelta(days=1)

    def assert_alarms_on_time(self, tolerance=60):
        expected = [a.astimezone(UTC) for a in self.expected_alarms()]
        actual = [s.astimezone(UTC) for s in self.sunrises]
        assert expected, "the simulated period contains no alarms"
        assert len(actual) == len(expected), f"expected {expected}, got {actual}"
        for want, got in zip(expected, actual):
            assert abs((got - want).total_seconds()) <= tolerance, f"expected {want}, got {got}"
        assert not self.negative_sleeps
