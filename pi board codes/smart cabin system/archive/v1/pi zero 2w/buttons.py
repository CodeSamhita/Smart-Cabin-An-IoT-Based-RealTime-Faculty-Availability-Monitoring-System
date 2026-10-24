# Smart Cabin cabin device - the hardware buttons: Available / In a meeting / Not available.
# Pressing the button of the status that is already set by hand goes back to Auto (sensors).
# One leg of each button to its GPIO pin, the other to GND (no resistor needed: the Pi's pull-up is used).

import time

import config
import shared

GPIO = None
last_pressed = ""


def start():
    global GPIO
    if config.SIMULATE:
        shared.set_sensor("buttons", "ok (simulated: use the buttons on the page)")
        return
    import RPi.GPIO as gpio
    GPIO = gpio
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for pin in config.BUTTON_PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)    # pressed = connected to GND = LOW
    shared.set_sensor("buttons", "ok")


def press(name):
    # Used by the real buttons and the page. Same button again = Auto.
    global last_pressed
    mode = "auto" if name == last_pressed else name
    last_pressed = "" if mode == "auto" else name
    with shared.lock:
        shared.state["button"] = mode
        shared.state["report_now"] = True
    shared.add_event("button", mode)


def watch():
    # Thread: reacts when a button goes from up to down
    if GPIO is None:
        return
    was_down = {name: False for name in config.BUTTON_PINS}
    while True:
        for name, pin in config.BUTTON_PINS.items():
            down = GPIO.input(pin) == GPIO.LOW
            if down and not was_down[name]:
                press(name)
            was_down[name] = down
        time.sleep(0.05)
