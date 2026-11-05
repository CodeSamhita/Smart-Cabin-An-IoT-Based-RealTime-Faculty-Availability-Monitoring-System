# Smart Cabin edge device - the NeoPixel (WS2812) light.
#   green = available, yellow = in a meeting, red = not available, blue = registration going on.
#   Dark room (set_lamp): the light stays white as a lamp for the camera and blinks the status colour every few seconds.
#   Flashes for events (card tap, unknown card, ...): notify.py.
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
wanted = "off"                  # the steady colour asked for (status, or blue during registration)
lamp = False                    # dark room: the light stays white and blinks the status colour


def start():
    global strip, neo
    threading.Thread(target=blink_status, name="led-blink", daemon=True).start()
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


def paint_steady():
    # The colour shown between flashes: white while the lamp is on (dark room), else the status colour
    if lamp and wanted != "blue":
        paint("white", settings.LAMP_BRIGHTNESS)
    else:
        paint(wanted)


def show(name):
    # The steady colour asked for (status, or blue during registration)
    global wanted
    with lock:
        wanted = name
        paint_steady()


def show_status(status, force=False):
    # Blue (registration) stays until the registration ends (force=True)
    if force or wanted != "blue":
        show(STATUS_COLOUR.get(status, "red"))


def flash(name, seconds=0.4, times=1):
    with lock:
        for i in range(times):
            paint(name, settings.FLASH_BRIGHTNESS if name == "white" else None)
            time.sleep(seconds)
            paint_steady()
            if i < times - 1:
                time.sleep(seconds)


def set_lamp(on):
    # Dark room: the light stays white (a lamp for the camera) and blinks the status colour (see blink_status)
    global lamp
    if lamp != on:
        lamp = on
        with lock:
            paint_steady()


def lamp_off_moment():
    # For one picture without the lamp (to see whether the room is still dark); lamp_back() ends it
    lock.acquire()
    paint("off")


def lamp_back():
    paint_steady()
    lock.release()


def blink_status():
    # Thread: while the lamp is on, the status colour blinks every LAMP_BLINK_SECONDS, so the status is still seen
    while True:
        time.sleep(settings.LAMP_BLINK_SECONDS)
        if lamp and wanted != "blue":
            flash(wanted, 0.3)
