# Smart Cabin edge device (Raspberry Pi) - every setting in one place. Change values here, not in the code.
# Nothing about the cabin is written here: the server knows where this device is from its serial number.

import os
import platform
import sys


def argument(flag, default=""):
    # python main.py --sim --port 8001  ->  argument("--port") = "8001"
    if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(flag) + 1]
    return default


FOLDER = os.path.dirname(os.path.abspath(__file__))
MODEL_FOLDER = os.path.join(FOLDER, "models")

# Which computer is this? On anything that is not a Pi (Windows, Mac, a Linux PC) the program runs as usual,
# only without the Pi's hardware: the camera is the computer's webcam (or a --picture file), cards are typed
# on the page, and the LED colour is shown on the page. --sim does the same on a real Pi.
BOARD = open("/proc/device-tree/model").read().strip("\x00 \n") if os.path.exists("/proc/device-tree/model") else ""
ON_PI = "Raspberry Pi" in BOARD
SIMULATE = "--sim" in sys.argv or not ON_PI           # True = no Pi hardware here
COMPUTER = "Raspberry Pi" if ON_PI else (platform.system() or "unknown")      # e.g. "Windows"
IS_PI5 = "Pi 5" in BOARD
FAST_BOARD = "Pi 4" in BOARD or IS_PI5 or not ON_PI   # Pi 4 / Pi 5 / a laptop: shorter picture intervals
USE_WEBCAM = "--no-webcam" not in sys.argv            # no Pi camera: use this computer's webcam if it has one
TEST_PICTURE_GIVEN = "--picture" in sys.argv          # a picture file instead of a camera (for testing)
SIM_SERIAL = argument("--serial", "")                 # pretend to be this device (several on one computer)

# This device's own files. Each simulated serial gets its own folders, so several can run on one laptop.
DATA_FOLDER = os.path.join(FOLDER, "data", SIM_SERIAL) if SIM_SERIAL else os.path.join(FOLDER, "data")
LOG_FOLDER = os.path.join(FOLDER, "logs", SIM_SERIAL) if SIM_SERIAL else os.path.join(FOLDER, "logs")
SIM_PICTURE = argument("--picture", os.path.join(DATA_FOLDER, "sim_picture.jpg"))

# The laptop server (the Windows "Mobile hotspot" laptop is always 192.168.137.1)
SERVER_URL = argument("--server", "https://192.168.137.1:8080")
PAGE_PORT = int(argument("--port", "8000"))          # this device's own page: https://<pi>:8000
REPORT_SECONDS = 2            # send the status this often (and straight after a change)
HELLO_SECONDS = 60            # ask the server "who am I, where am I, who is registered here?" this often
SERVER_TIMEOUT = 8            # seconds to wait for the server

# Pins (GPIO / BCM numbers)
RFID_RST_PIN = 25             # RC522: SDA 8, SCK 11, MOSI 10, MISO 9, RST 25, 3.3 V
LED_PIN = 18                  # NeoPixel data on a Zero 2W / Pi 4, must be GPIO18
LED_SPI_DEVICE = "/dev/spidev1.0"   # NeoPixel on a Pi 5: data on GPIO20 (pin 38), SPI1 (the RC522 uses SPI0)
LED_COUNT = 1                 # number of NeoPixels
LED_BRIGHTNESS = 60           # 0 - 255 for the status colours
FLASH_BRIGHTNESS = 255        # the white light for the camera in a dark room
BUZZER_PIN = 23               # buzzer signal on GPIO23 (pin 16), GND pin 20; a bare 5 V buzzer needs a transistor
BUZZER_PASSIVE = False        # False = active buzzer (beeps by itself), True = passive (needs a tone)
BUZZER_TONE = 2000            # Hz, for a passive buzzer

# Wi-Fi: the network set when flashing the SD card = the laptop hotspot (its name differs by image: "preconfigured",
# or "netplan-wlan0-<Wi-Fi name>" on trixie). Every network NOT added on the page counts as a setup network: used first
# when it is on, and it can't be removed on the page. Networks added on the page (campus Wi-Fi) are named WIFI_PREFIX...
WIFI_PREFIX = "smartcabin "
HOSTNAME = "smartcabin"       # the page is also at https://smartcabin.local (mDNS: works without a DNS server)

# Camera and vision (see PLAN.md section 4)
CAMERA_SIZE = (1296, 972)     # for face checks only: faces need the pixels (no face found at 640x480 in tests)
LIVE_SIZE = (640, 480)        # for the headcount and the live view (the middle of the three tested sizes)
LIVE_FPS = 10 if FAST_BOARD else 5   # live view pictures per second, only while someone watches it
PICTURE_SECONDS = 2 if FAST_BOARD else 5         # a headcount picture this often ...
FAST_PICTURE_SECONDS = 1 if FAST_BOARD else 1.5  # ... and this often for FAST_SECONDS after something changes
FAST_SECONDS = 30
OPENCV_THREADS = 2            # leave the other cores for RFID, the page and the server link
WARM_TEMPERATURE = 70         # above this: pictures half as often
HOT_TEMPERATURE = 78          # above this: vision pauses until it is back under WARM_TEMPERATURE

PEOPLE_MODEL = "auto"         # "auto" = YOLOv8n on a Pi 4 if models/yolov8n.onnx exists, else MobileNet-SSD
PEOPLE_CONFIDENCE = 0.5
STEADY_PICTURES = 3           # the headcount changes only after 3 pictures agree

FACE_THRESHOLD = 0.36         # cosine similarity at or above this = the registered person
FACE_PHOTOS = 10              # photos taken when registering a face
FACE_RECHECK_SECONDS = 30     # once the person is in, check the face only this often
WHOLE_PICTURE_FACE_SECONDS = 15   # no person box found: look for a face in the whole picture this often

DARK_LEVEL = 40               # average brightness (0 - 255) under this = the room is dark: the light becomes a lamp
LAMP_OFF_LEVEL = 55           # the lamp goes off again only when the room alone is this bright (no flickering on / off)
LAMP_CHECK_SECONDS = 60       # with the lamp on, look at the room without it this often
LAMP_BRIGHTNESS = 200         # 0 - 255, the white lamp
LAMP_BLINK_SECONDS = 3        # with the lamp on, the status colour blinks this often
FLASH_SECONDS = 0.6           # the camera adjusts to a change of light this long before a picture
FACE_MIN_BRIGHTNESS = 70      # registration: a face darker than this (0 - 255) is refused (light behind the person)
FACE_MIN_CONTRAST = 22        # registration: a face flatter than this (grey spread) is refused

# Presence rules (PLAN.md section 3)
ARRIVE_FACE_CHECKS = 2        # face matched in 2 checks in a row = arrived (1 while a card tap is being checked)
CARD_CONFIRM_SECONDS = 120    # after a card tap, the camera looks for the face this long (a tap alone is never "in")
TAP_OUT_SECONDS = 30          # a tap while in: out if the face is not seen for this long after it
REPORT_IN_AFTER_SECONDS = 100 # the server is told "in" only after this long in (the Pi's light / page change at once)
LEAVE_SECONDS = 120           # face not seen for this long = left (card-only person: nobody counted for this long)
FACE_RECENT_SECONDS = 120     # "face seen" (pages, confidence) = within this time
CARD_LEFT_SECONDS = 5         # a card lying on the reader longer than this = warning

# Confidence table: face (F) x card (R), from hardware test 10 without the Bluetooth column
CONFIDENCE = {(0, 0): 2, (0, 1): 35, (1, 0): 70, (1, 1): 90}   # card only stays under 50: the face decides
SOMEONE_COUNTED_BONUS = 10    # added while the person is in and the camera counts someone
CONFIDENCE_MAX = 95

REGISTRATION_MINUTES = 5      # a registration on the page ends after this long
CARD_WAIT_SECONDS = 30        # wait this long for a card tap when linking a card
