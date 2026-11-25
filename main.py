import time

import machine
import neopixel

from lib.alarm import next_alarm
from lib.sunrise import Sunrise
from lib.time_sync import sync_and_set_rtc


light_pin = machine.Pin(28)
sunrise = Sunrise(pixels=neopixel.NeoPixel(light_pin, 32))

# The clock is wrong until the first sync, so don't continue without it
while not sync_and_set_rtc():
    time.sleep(5)

while True:
    try:
        # Wake two hours before the alarm to correct drift and DST changes
        time.sleep(max(0, next_alarm(time.time()) - 7200))
        # If this fails, the existing clock is good enough
        sync_and_set_rtc()
        time.sleep(next_alarm(time.time()))
        sunrise.sunrise()
    except KeyboardInterrupt:
        # Re-raise to drop to the REPL; otherwise the loop would just continue
        sunrise.stop()
        raise
    except Exception as e:
        print("Error:", repr(e))
        sunrise.stop()
        time.sleep(5)
        machine.reset()
