# Single NeoPixel (WS2812) LED test - bare-bone. Press Enter to go to the next colour.
# Run:  sudo python3 3_test_neopixel.py      (sudo is needed to drive the LED)
#
# Wiring (GPIO number, physical pin in brackets):
#   DIN -> GPIO18 (12)   5V -> 5V (2)   GND -> GND (14)
#
# Library (once):
#   sudo apt install -y python3-pip python3-dev gcc
#   sudo pip3 install rpi_ws281x --break-system-packages

import os
import sys

LED_PIN = 18                  # must be GPIO18 (the PWM pin)
LED_COUNT = 1
BRIGHTNESS = 60               # 0 - 255

COLOURS = [("RED", (255, 0, 0)), ("GREEN", (0, 255, 0)), ("BLUE", (0, 0, 255)), ("YELLOW", (255, 255, 0)),
           ("CYAN", (0, 255, 255)), ("MAGENTA", (255, 0, 255)), ("WHITE", (255, 255, 255)), ("OFF", (0, 0, 0))]


def check_sudo():
    print("[1] Running with sudo?")
    if os.geteuid() != 0:
        print("    FAIL: run it with sudo:  sudo python3 3_test_neopixel.py")
        return False
    print("    PASS")
    return True


def check_board():
    print("[2] Board supported?")
    with open("/proc/device-tree/model") as f:
        model = f.read().rstrip("\x00")
    print("    Board:", model)
    if "Pi 5" in model:
        print("    FAIL: the rpi_ws281x library does not work on the Pi 5")
        return None
    print("    PASS")
    return model


def check_audio(model):
    # GPIO18's PWM is shared with the 3.5 mm audio. With audio on, the LED can flicker or show wrong colours.
    print("[3] Audio off? (it shares the PWM with GPIO18)")
    if "Zero" in model:
        print("    PASS: the Zero has no 3.5 mm audio jack, so nothing else uses the PWM")
        return
    try:
        with open("/boot/firmware/config.txt") as f:
            lines = [line.strip() for line in f]
    except OSError:
        print("    INFO: can't read /boot/firmware/config.txt, skipped")
        return
    if "dtparam=audio=on" in lines:
        print("    WARN: audio is on. If the colours look wrong, change it to dtparam=audio=off in")
        print("          /boot/firmware/config.txt  (sudo nano /boot/firmware/config.txt)  and sudo reboot")
    else:
        print("    PASS")


def start_led():
    print("[4] LED library starts?")
    try:
        from rpi_ws281x import PixelStrip
    except ImportError:
        print("    FAIL: rpi_ws281x missing - see the install lines at the top of this file")
        return None
    try:
        led = PixelStrip(LED_COUNT, LED_PIN, 800000, 10, False, BRIGHTNESS)
        led.begin()
    except Exception as error:
        print("    FAIL:", error)
        return None
    print("    PASS: sending to GPIO18")
    print("    Note: a WS2812 can't send anything back, so the only check from here on is your eyes.")
    return led


def show(led, colour):
    led.setPixelColorRGB(0, colour[0], colour[1], colour[2])
    led.show()


def cycle_colours(led):
    print()
    print("[5] Colour test: press Enter for the next colour, q + Enter to quit")
    number = 0
    while True:
        name, colour = COLOURS[number % len(COLOURS)]
        show(led, colour)
        answer = input("    " + str(number % len(COLOURS) + 1) + "/" + str(len(COLOURS)) + "  " +
                       name.ljust(8) + str(colour) + "  > ").strip().lower()
        if answer == "q":
            break
        number += 1


def main():
    print("NeoPixel LED test")
    if not check_sudo():
        return
    model = check_board()
    if model is None:
        return
    check_audio(model)
    led = start_led()
    if led is None:
        return
    try:
        cycle_colours(led)
    except KeyboardInterrupt:
        print()
    show(led, (0, 0, 0))
    print("LED off. If it never lit: check DIN -> GPIO18 (pin 12), 5V, GND,")
    print("and that the wire goes to the LED's DIN / IN side (not DOUT).")


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("Run this on the Raspberry Pi.")
    main()
