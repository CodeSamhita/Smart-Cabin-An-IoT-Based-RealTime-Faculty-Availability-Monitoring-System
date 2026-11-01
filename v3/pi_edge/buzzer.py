# Smart Cabin edge device - the buzzer (GPIO23, see settings.py). Which event plays which sound: notify.py.
#   ok       one short beep        refused   two short beeps       photo   a tick
#   done     short + long          warning   two long beeps
#   arrive   three quick beeps     meeting   two medium beeps      leave   one long beep
# The sound plays in the background, so the card reader and the camera never wait for it.
# Active buzzer: the pin on = sound. Passive buzzer (BUZZER_PASSIVE): a tone of BUZZER_TONE Hz.
# Not on a Pi: nothing sounds, the part shows Not present.

import threading
import time

import settings
import shared

# (seconds on, seconds off) for each sound
SOUNDS = {"ok": [(0.08, 0)],
          "refused": [(0.08, 0.08), (0.08, 0)],
          "photo": [(0.03, 0)],
          "done": [(0.08, 0.08), (0.3, 0)],
          "warning": [(0.4, 0.2), (0.4, 0)],
          "arrive": [(0.05, 0.06), (0.05, 0.06), (0.05, 0)],
          "meeting": [(0.18, 0.12), (0.18, 0)],
          "leave": [(0.6, 0)]}

gpio = None                     # RPi.GPIO once the pin is set up
tone = None                     # PWM for a passive buzzer
lock = threading.Lock()         # one sound at a time


def start():
    global gpio, tone
    if settings.SIMULATE:
        shared.set_part("buzzer", False, "no buzzer on this computer (" + settings.COMPUTER + ")", present=False)
        return
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(settings.BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        if settings.BUZZER_PASSIVE:
            tone = GPIO.PWM(settings.BUZZER_PIN, settings.BUZZER_TONE)
        gpio = GPIO
        kind = "passive, %d Hz" % settings.BUZZER_TONE if settings.BUZZER_PASSIVE else "active"
        shared.set_part("buzzer", True, "on GPIO%d (%s)" % (settings.BUZZER_PIN, kind))
    except Exception as problem:
        shared.set_part("buzzer", False, str(problem) + " (the program must run with sudo)")


def sound(on):
    if tone is not None and on:
        tone.start(50)
    elif tone is not None:
        tone.stop()
    else:
        gpio.output(settings.BUZZER_PIN, gpio.HIGH if on else gpio.LOW)


def play(name):
    with lock:
        try:
            for on_seconds, off_seconds in SOUNDS[name]:
                sound(True)
                time.sleep(on_seconds)
                sound(False)
                time.sleep(off_seconds)
        except Exception as problem:
            shared.set_part("buzzer", False, str(problem))


def beep(name="ok"):
    if gpio is None or name not in SOUNDS:
        return
    threading.Thread(target=play, args=(name,), name="buzzer", daemon=True).start()
