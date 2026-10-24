# Smart Cabin cabin device (Raspberry Pi Zero 2W / Pi 4) - settings. Change values here, not in the code.
import os

FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(FOLDER, "data")        # this device's own files (token, face, zones, cache)
MODEL_FOLDER = os.path.join(FOLDER, "models")

# The laptop server. With the Windows "Mobile hotspot" the laptop is always 192.168.137.1.
SERVER_URL = "http://192.168.137.1:8080"
PAGE_PORT = 8000                                   # this device's own setup page

# On a laptop (not a Pi) the hardware is simulated, so everything can be tried without a Pi.
ON_PI = os.path.exists("/proc/device-tree/model") and "Raspberry Pi" in open("/proc/device-tree/model").read()
SIMULATE = not ON_PI
SIM_PICTURE = os.path.join(DATA_FOLDER, "sim_picture.jpg")   # simulation: this picture is "the camera"

# Parts that are wired. Set to False for anything missing; the rest still works.
USE_CAMERA = True
USE_RFID = True
USE_BLUETOOTH = True
USE_BUTTONS = True
USE_LEDS = True

# Pins (GPIO / BCM numbers). Wiring: see README.md in this folder.
RFID_RST_PIN = 25
BUTTON_PINS = {"available": 5, "meeting": 6, "away": 26}     # pressing the same one again = back to Auto
LED_PIN = 18                                                 # must be GPIO18 (PWM)
LED_COUNT = 1
LED_BRIGHTNESS = 60                                          # 0 - 255

# Camera. Faces need more pixels than whole bodies (tested: no face at 640x480, found at 1296x972).
CAMERA_SIZE = (1296, 972)
PICTURE_SECONDS = 5           # a picture every 5 s normally ...
FAST_PICTURE_SECONDS = 1.5    # ... and every 1.5 s for FAST_SECONDS after anything changes
FAST_SECONDS = 30

# People counting (same as hardware test 7)
PEOPLE_MODEL = "mobilenet"    # "mobilenet" (fast) or "yolo" (needs models/yolov8n.onnx)
PEOPLE_CONFIDENCE = 0.5
STEADY_PICTURES = 3           # the count changes only after 3 pictures agree
STILL_SECONDS = 60            # a box that doesn't change for this long is a photo / poster, not counted
MOVE_THRESHOLD = 4.0

# Face recognition (same as hardware test 8)
FACE_THRESHOLD = 0.36         # higher = stricter
FACE_SAMPLES = 10             # photos taken when registering

# Presence rules (BUILD_PLAN.md section 3)
ARRIVE_PICTURES = 2           # face matched in 2 pictures in a row = arrived
CARD_CONFIRM_SECONDS = 120    # after a card login, the camera or phone must confirm within this time
LEAVE_SECONDS = 180           # no face and no phone for this long = left
PHONE_CHECK_SECONDS = 15      # l2ping every phone this often
CARD_REPEAT_SECONDS = 3       # the same card within 3 s counts once

# Talking to the server
REPORT_SECONDS = 3            # send the evidence this often (and straight away after an event)
CONFIG_SECONDS = 60           # fetch the owner, cards and phones this often
PAIR_SECONDS = 60             # Bluetooth pairing window
