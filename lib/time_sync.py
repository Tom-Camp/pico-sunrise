import ntptime
import secrets

from lib.wifi_manager import WiFiManager

NTP_SERVER: str = "us.pool.ntp.org"

wifi = WiFiManager(ssid=secrets.SSID, password=secrets.PASSWORD)


def sync_and_set_rtc() -> bool:
    """Connect to WiFi and set the RTC to UTC. Return True on success."""
    try:
        # Always reconnect; the link may have dropped since the last sync
        if not wifi.connect(timeout=10):
            return False
        ntptime.settime()
        return True
    except OSError as e:
        print("NTP sync failed:", e)
        return False
