# Smart Cabin edge device - the NeoPixel (WS2812) light.
#   green = available, yellow = in a meeting, red = not available, blue = registration going on,
#   white = light for the camera in a dark room (a moment only), purple flash = unknown card,
#   two red blinks = a card was left on the reader.
# In simulation the colour is only shown on the device's page.
# Zero 2W / Pi 4: rpi_ws281x on GPIO18. Pi 5: rpi_ws281x does not work there, so pi5neo on SPI1 (data on GPIO20).

import threading
import time

import settings
import shared

COLOURS = {"green": (0, 200, 0), "yellow": (230, 150, 0), "red": (220, 0, 0), "blue": (0, 0, 255),
           "white": (255, 255, 255), "purple": (150, 0, 200), "off": (0, 0, 0)}
STATUS_COLOUR = {"available": "green", "meeting": "yellow", "not_available": "red"}

strip = None                    # rpi_ws281x strip (Zero 2W / Pi 4)
neo = None                      # pi5neo strip (Pi 5)
lock = threading.Lock()
steady = "off"                  # the colour to come back to after a flash


def start():
    global strip, neo
    if settings.SIMULATE:
        shared.set_part("led", False, "no NeoPixel on this computer (" + settings.COMPUTER
                        + ") - its colour is shown on the device page", present=False)
        return
    try:
        if settings.IS_PI5:
            from pi5neo import Pi5Neo
            neo = Pi5Neo(settings.LED_SPI_DEVICE, settings.LED_COUNT, 800)
            shared.set_part("led", True, "%d NeoPixel(s) on GPIO20 (Pi 5, %s)" % (settings.LED_COUNT, settings.LED_SPI_DEVICE))
        else:
            from rpi_ws281x import PixelStrip
            strip = PixelStrip(settings.LED_COUNT, settings.LED_PIN, 800000, 10, False, settings.LED_BRIGHTNESS)
            strip.begin()
            shared.set_part("led", True, "%d NeoPixel(s) on GPIO%d" % (settings.LED_COUNT, settings.LED_PIN))
    except Exception as problem:
        hint = " (Pi 5: is SPI1 on? see install.py)" if settings.IS_PI5 else " (the program must run with sudo)"
        shared.set_part("led", False, str(problem) + hint)


def paint(name, brightness=None):
    shared.update(led=name)
    if strip is None and neo is None:
        return
    try:
        level = brightness or settings.LED_BRIGHTNESS
        r, g, b = COLOURS.get(name, COLOURS["off"])
        if neo is not None:                                   # Pi 5: no brightness setting, so scale the colour
            for i in range(settings.LED_COUNT):
                neo.set_led_color(i, r * level // 255, g * level // 255, b * level // 255)
            neo.update_strip()
            return
        strip.setBrightness(level)
        for i in range(settings.LED_COUNT):
            strip.setPixelColorRGB(i, r, g, b)
        strip.show()
    except Exception as problem:
        shared.set_part("led", False, str(problem))


def show(name):
    # The steady colour (status or blue during registration)
    global steady
    with lock:
        steady = name
        paint(name)


def show_status(status, force=False):
    # Blue (registration) stays until the registration ends (force=True)
    if force or steady != "blue":
        show(STATUS_COLOUR.get(status, "red"))


def flash(name, seconds=0.4, times=1):
    with lock:
        for i in range(times):
            paint(name, settings.FLASH_BRIGHTNESS if name == "white" else None)
            time.sleep(seconds)
            paint(steady)
            if i < times - 1:
                time.sleep(seconds)


def light_on():
    # White for a dark-room picture; light_off() puts the status colour back
    lock.acquire()
    paint("white", settings.FLASH_BRIGHTNESS)


def light_off():
    paint(steady)
    lock.release()
