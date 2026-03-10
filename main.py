import machine
import neopixel
import time

import secrets
from lib.sunrise import Sunrise
from lib.time_sync import sync_and_set_rtc, next_alarm
from lib.wifi_manager import WiFiManager

wifi = WiFiManager(ssid=secrets.SSID, password=secrets.PASSWORD)


light_pin = machine.Pin(28)
sunrise = Sunrise(pixels=neopixel.NeoPixel(light_pin, 32))

while True:
    try:
        sync_and_set_rtc()
        sleep_time = next_alarm()
        # Wake an hour before the alarm
        time.sleep(sleep_time - 3600)
        sync_and_set_rtc()
        # Set wake time
        wake_time = next_alarm()
        time.sleep(wake_time)
        sunrise.sunrise()
    except KeyboardInterrupt:
        sunrise.stop()
    except Exception as e:
        sunrise.stop()
        time.sleep(5)
        machine.reset()
