import time
import neopixel

from lib.configuration import config

COLOR = config.get("color", (220, 238, 247))
DELAY = config.get("delay", 60)
BRIGHTNESS = 0.1


class Sunrise:

    def __init__(self, pixels: neopixel.NeoPixel):
        self.pixels = pixels

    def sunrise(self):
        """
        Start the sun to risin'
        """
        light_order = [
            11, 20, 12, 19, 2, 5, 26, 29, 3, 4, 10, 13, 18, 21, 27, 28,
            1, 6, 9, 14, 17, 22, 25, 30, 0, 7, 8, 15, 16, 23, 24, 31,
        ]
        for light in light_order:
            self.pixels[light] = (
                round(COLOR[0] * BRIGHTNESS),
                round(COLOR[1] * BRIGHTNESS),
                round(COLOR[2] * BRIGHTNESS),
            )
            try:
                self.pixels.write()
                time.sleep(DELAY)
            except ValueError:
                time.sleep(1)
        self.brighten()

    def brighten(self):
        """
        Increase brightness
        """
        for br in range(1, 8):
            brighter = br * BRIGHTNESS
            try:
                self.pixels.fill((
                    round(COLOR[0] * brighter),
                    round(COLOR[1] * brighter),
                    round(COLOR[2] * brighter),
                ))
                self.pixels.write()
                time.sleep(DELAY)
            except OSError as e:
                print(f"OSError: {e}")
        self.stop()

    def stop(self):
        """
        Set all to off
        """
        self.pixels.fill((0, 0, 0))
        self.pixels.write()
        time.sleep(0.05)
        self.pixels.write()

