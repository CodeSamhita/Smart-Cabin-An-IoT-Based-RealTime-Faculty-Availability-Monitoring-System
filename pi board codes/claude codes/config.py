# Every setting in one place.
import os
import sys

SIM = "--sim" in sys.argv          # python3 main.py --sim : no hardware, everything is pretended
PORT = 8000                        # the setup page: http://<pi>:8000

FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(FOLDER, "data")
FACES_FOLDER = os.path.join(DATA_FOLDER, "faces")
USERS_CSV = os.path.join(DATA_FOLDER, "users.csv")
DEVICES_CSV = os.path.join(DATA_FOLDER, "devices.csv")
MODEL_FOLDER = os.path.join(FOLDER, "models")

# Face
RESOLUTION = (1296, 972)           # faces need the pixels (none found at 640x480 in a test photo)
FACE_SAMPLES = 10                  # photos taken when registering
FACE_SECONDS = 30                  # give up registering a face after this long
FACE_MATCH = 0.36                  # cosine score at or above this = the same person (as in test 8)
MIN_FACE_CONFIDENCE = 0.9          # ignore weak face detections
YUNET_NEW = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_OLD = "https://github.com/opencv/opencv_zoo/raw/4fb591053ba1201c07c68929cc324787d5afaa6c/models/face_detection_yunet/face_detection_yunet_2022mar.onnx"
SFACE = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

# RFID (RC522 on SPI, RST on GPIO25 = pin 22)
RST_PIN = 25
CARD_SECONDS = 30                  # stop waiting for a tap after this long

# Bluetooth
MAX_DEVICES = 5                    # per user
PAIR_SECONDS = 60                  # how long the Pi is visible and pairable when adding a device
GUARD_SECONDS = 3                  # how often other connections to the Pi are dropped (detect-only)
