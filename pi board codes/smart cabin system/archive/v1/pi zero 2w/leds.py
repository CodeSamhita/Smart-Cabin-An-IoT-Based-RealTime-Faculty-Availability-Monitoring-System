# Smart Cabin cabin device - the NeoPixel (WS2812) light in front of the faculty member.
#   green = available, yellow = in a meeting, red = not in the cabin,
#   blue  = setup going on (face registering, card linking, phone pairing),
#   short white flash = a card was read, short purple flash = unknown card.
# In simulation the colour is only shown on the device's page.

import time

import config
import shared

COLOURS = {"green": (0, 200, 0), "yellow": (230, 150, 0), "red": (220, 0, 0), "blue": (0, 0, 255),
           "white": (200, 200, 200), "purple": (150, 0, 200), "off": (0, 0, 0)}

strip = None
current = "off"


def start():
    global strip
    if config.SIMULATE:
        shared.set_sensor("led", "ok (simulated: shown on the page)")
        return
    try:
        from rpi_ws281x import PixelStrip
        strip = PixelStrip(config.LED_COUNT, config.LED_PIN, 800000, 10, False, config.LED_BRIGHTNESS)
        strip.begin()
        shared.set_sensor("led", "ok")
    except Exception as error:
        shared.set_sensor("led", "error: " + str(error) + " (run with sudo)")


def show(name):
    global current
    current = name
    with shared.lock:
        shared.state["led"] = name
    if strip is None:
        return
    r, g, b = COLOURS.get(name, COLOURS["off"])
    for i in range(config.LED_COUNT):
        strip.setPixelColorRGB(i, r, g, b)
    strip.show()


def flash(name, seconds=0.4):
    # A short flash, then back to the colour before
    before = current
    show(name)
    time.sleep(seconds)
    show(before)
