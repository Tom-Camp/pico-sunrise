import ntptime
import time
import secrets

from lib.configuration import config
from lib.wifi_manager import WiFiManager

STD_OFFSET: int = 5 * 3600
DST_OFFSET: int = 4 * 3600
NTP_SERVER: str = "us.pool.ntp.org"


def nth_weekday(nth_year: int, nth_month: int, target_wday: int, n: int) -> int:
    # target_wday: Monday=0 … Sunday=6
    first_day_wday = time.localtime(time.mktime((nth_year, nth_month, 1, 0, 0, 0, 0, 0)))[6]
    # days to the first occurrence of target_wday
    delta = (target_wday - first_day_wday) % 7
    day = 1 + delta + (n - 1) * 7
    return day


def is_dst(utc_tuple: tuple) -> bool:
    """Return True if the given UTC tuple falls within US DST period."""
    year, month, mday, hour, minute, second, weekday, yearday = utc_tuple

    # DST start: second Sunday in March at 02:00 UTC‑05 → 07:00 UTC
    dst_start_day: int = nth_weekday(year, 3, 6, 2)
    dst_start_ts: int = time.mktime((year, 3, dst_start_day, 7, 0, 0, 0, 0))

    # DST end: first Sunday in November at 02:00 UTC‑04 → 06:00 UTC
    dst_end_day: int = nth_weekday(year, 11, 6, 1)
    dst_end_ts: int = time.mktime((year, 11, dst_end_day, 6, 0, 0, 0, 0))

    now_ts = time.mktime(utc_tuple)
    return dst_start_ts <= now_ts < dst_end_ts


def sync_and_set_rtc() -> None:
    wifi = WiFiManager(ssid=secrets.SSID, password=secrets.PASSWORD)
    wifi.connect(10)
    try:
        ntptime.settime()
    except OSError as e:
        print("NTP sync failed:", e)
        return None
    return None


def utc_to_eastern(local_ts: int) -> int:
    offset = DST_OFFSET if is_dst(time.localtime(local_ts)) else STD_OFFSET
    return local_ts + (offset * -1)


def next_alarm() -> int:
    date_ts: int = utc_to_eastern(time.time())
    tomorrow_ts: int = date_ts + 86400
    date_local: tuple = time.localtime(date_ts)
    week: dict = config.get("week", {})
    hour, minute = week[date_local[6]]
    wake_today: int = time.mktime((
        date_local[0], # year
        date_local[1], # month 1-12
        date_local[2], # day 1-31
        hour,          # hour 0-23
        minute,        # minute 0-59
        0,             # second 0-59
        date_local[6], # weekday 0-6
        date_local[7], # yearday 1-366
    ))
    if wake_today <= date_ts:
        tomorrow_local: tuple = time.localtime(tomorrow_ts)
        hour, minute = week[tomorrow_local[6]]
        wake_tomorrow: int = time.mktime((
            tomorrow_local[0],
            tomorrow_local[1],
            tomorrow_local[2],
            hour,
            minute,
            0,
            tomorrow_local[6],
            tomorrow_local[7],
        ))
        return wake_tomorrow - date_ts
    return wake_today - date_ts
