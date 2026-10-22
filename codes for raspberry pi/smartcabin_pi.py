# Smart Cabin - Raspberry Pi: face recognition + RFID + Bluetooth phones + manual buttons + NeoPixel LEDs,
# all shown on a web page, with a check of every part of the hardware.
#
# Face recognition, same idea as face_app.py:
#   1. DETECT : find where the faces are in the picture   (YuNet model)
#   2. EMBED  : turn each face into 128 numbers            (SFace model)
#   3. MATCH  : compare with the saved people (cosine similarity). Too far from everyone -> "Unknown"
# It uses OpenCV's small face models instead of PyTorch: nothing big to install, and they run fast on the
# Raspberry Pi 4's CPU (board details: board_specs.md).
#
# Status of each person, in this order:
#   1. Their manual override (web page, or the hardware buttons) wins, until cleared or OVERRIDE_MINUTES pass
#   2. Otherwise "Available" if their face was seen recently, their RFID card is tapped in, or their phone is near
#   3. Otherwise "Away"
# The hardware buttons and the LEDs belong to one person (chosen on the web page): the cabin owner.
#
# Run:  sudo python3 smartcabin_pi.py      (sudo is needed for the LEDs and Bluetooth checks)
# The first run installs missing libraries and downloads the two face models by itself.
# Wiring: see the bottom of this file.

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------- Settings you can tune ----------------
CAMERA = "pi"                 # "pi" = ribbon-cable Pi Camera, "usb" = USB webcam
WIDTH, HEIGHT = 640, 480
FPS = 6                       # pictures checked per second (1 - 10). The Pi 4 manages about 5-10; lower it if the CPU runs hot.
THRESHOLD = 0.36              # higher = stricter matching (try 0.30 - 0.50)
MIN_FACE_CONFIDENCE = 0.9     # ignore weak detections
SAMPLES_PER_PERSON = 10       # photos taken during registration
PRESENT_SECONDS = 15          # "In cabin" if the face was seen in the last 15 seconds
PORT = 8000

# Extra hardware. Set to False for anything not wired yet - everything else still works.
USE_RFID = True               # RC522 card reader
USE_BUTTONS = True            # push buttons for manual override
USE_LEDS = True               # NeoPixel (WS2812) LED strip or ring
USE_BLUETOOTH = True          # paired phones count as "in cabin" while they are near the Pi

# Pins are GPIO (BCM) numbers, not the physical pin numbers. See the wiring at the bottom.
RFID_RST_PIN = 25
BUTTON_PINS = {"Available": 5, "Busy": 6, "Back soon": 26}   # press the same button again = back to automatic
OVERRIDE_MINUTES = 60         # an override ends by itself after this long
CARD_REPEAT_SECONDS = 3       # ignore the same card for 3 s, so one tap counts once
LED_PIN = 18                  # must be GPIO18 (the PWM pin)
LED_COUNT = 8
LED_BRIGHTNESS = 60           # 0 - 255
BT_CHECK_SECONDS = 15         # how often to look for the paired phones
BT_PRESENT_SECONDS = 60       # a phone counts as near if it answered in the last 60 s
# --------------------------------------------------------

STATUS_COLORS = {"Available": (0, 200, 0), "Busy": (220, 0, 0), "Back soon": (230, 150, 0), "Away": (30, 30, 30)}
SETUP_COLOR = (0, 0, 255)     # blue while registering a face, linking a card or pairing a phone

FOLDER = os.path.dirname(os.path.abspath(__file__))
MODEL_FOLDER = os.path.join(FOLDER, "models")
DB_FILE = os.path.join(FOLDER, "known_faces_pi.json")
CARDS_FILE = os.path.join(FOLDER, "cards_pi.json")
PHONES_FILE = os.path.join(FOLDER, "phones_pi.json")
SETTINGS_FILE = os.path.join(FOLDER, "settings_pi.json")

# OpenCV's official model files. Older OpenCV (below 4.8, e.g. 4.6 on Raspberry Pi OS) needs the older detector.
YUNET_NEW = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_OLD = "https://github.com/opencv/opencv_zoo/raw/4fb591053ba1201c07c68929cc324787d5afaa6c/models/face_detection_yunet/face_detection_yunet_2022mar.onnx"
SFACE = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"


# ---------- Step 0: install anything that is missing ----------
def is_raspberry_pi():
    try:
        with open("/proc/device-tree/model") as f:
            return "Raspberry Pi" in f.read()
    except OSError:
        return False


def is_missing(module):
    try:
        __import__(module)
        return False
    except ImportError:
        return True


def command_exists(name):
    return subprocess.run(["which", name], capture_output=True).returncode == 0


ON_PI = is_raspberry_pi()


def install_missing_libraries():
    if not sys.platform.startswith("linux"):
        # Laptop (for testing): only the face libraries, with pip
        pip_names = []
        if is_missing("cv2"):
            pip_names.append("opencv-python")
        if is_missing("numpy"):
            pip_names.append("numpy")
        if pip_names:
            subprocess.run([sys.executable, "-m", "pip", "install"] + pip_names, check=True)
        return

    # Must have: camera and face recognition
    core = []
    if is_missing("cv2"):
        core.append("python3-opencv")
    if is_missing("numpy"):
        core.append("python3-numpy")
    if CAMERA == "pi" and is_missing("picamera2"):
        core.append("python3-picamera2")

    # Nice to have: RFID, buttons, LEDs, Bluetooth. If these fail, the program still runs without them.
    extras = []
    pip_names = []
    if ON_PI and (USE_RFID or USE_BUTTONS) and is_missing("RPi.GPIO"):
        extras.append("python3-rpi-lgpio")
    if ON_PI and USE_RFID and is_missing("spidev"):
        extras.append("python3-spidev")
    if ON_PI and USE_BLUETOOTH and not (command_exists("bluetoothctl") and command_exists("l2ping")):
        extras.append("bluez")
    if ON_PI and USE_BLUETOOTH and not command_exists("bt-agent"):
        extras.append("bluez-tools")     # bt-agent accepts the phone's pairing request
    if ON_PI and USE_RFID and is_missing("mfrc522"):
        pip_names.append("mfrc522")
    if ON_PI and USE_LEDS and is_missing("rpi_ws281x"):
        pip_names.append("rpi_ws281x")
    if pip_names:
        extras += ["python3-pip", "python3-dev", "gcc"]    # needed to build the LED library

    if core or extras:
        print("Installing", " ".join(core + extras), "- this can take several minutes on the Pi...")
        subprocess.run(["sudo", "apt-get", "update"])
    if core:
        subprocess.run(["sudo", "apt-get", "install", "-y"] + core, check=True)
    if extras:
        subprocess.run(["sudo", "apt-get", "install", "-y"] + extras)
    if pip_names:
        # --no-deps: the GPIO and SPI libraries already came from apt above
        subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "--no-deps"] + pip_names)


install_missing_libraries()
import cv2            # noqa: E402  (imported here, after installing)
import numpy as np    # noqa: E402


def download_models():
    os.makedirs(MODEL_FOLDER, exist_ok=True)
    major, minor = cv2.__version__.split(".")[:2]
    yunet_url = YUNET_NEW if (int(major), int(minor)) >= (4, 8) else YUNET_OLD

    paths = []
    for url in [yunet_url, SFACE]:
        path = os.path.join(MODEL_FOLDER, url.split("/")[-1])
        if not os.path.exists(path):
            print("Downloading", os.path.basename(path), "...")
            urllib.request.urlretrieve(url, path + ".part")
            os.replace(path + ".part", path)      # only keep the file once it is complete
        paths.append(path)
    return paths


def run_command(args, timeout=5):
    # Run a system command and return what it printed ("" if it failed or took too long)
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


# ---------- Saved files ----------
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def load_db():
    # {name: array of face embeddings}
    saved = load_json(DB_FILE, {})
    return {name: np.array(vectors, dtype=np.float32) for name, vectors in saved.items()}


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({name: vectors.tolist() for name, vectors in db.items()}, f)


# ---------- Shared state (camera, hardware and Bluetooth threads write, web server reads) ----------
lock = threading.RLock()      # RLock: the same thread may lock again without getting stuck
db = {}                       # name -> face embeddings
cards = {}                    # card id -> name
phones = {}                   # phone Bluetooth address -> name
settings = {}                 # {"button_person": name}
state = {
    "jpeg": None,             # newest picture with boxes drawn
    "frame_id": 0,
    "last_frame_time": 0.0,
    "in_view": [],            # names seen in the newest picture
    "last_seen": {},          # name -> time the face was last seen
    "card_in": {},            # name -> time they tapped their card in (removed when they tap out)
    "phone_seen": {},         # name -> time their phone last answered
    "overrides": {},          # name -> {"status", "until", "source"}
    "fps": 0.0,
    "register_name": None,    # set by the web page to start registering a face
    "register_started": 0.0,
    "link_name": None,        # set by the web page: the next card tapped gets this name
    "link_started": 0.0,
    "pairing_name": None,     # set while waiting for a phone to pair
    "last_card": "",
    "last_card_time": 0.0,
    "message": "",
    # part -> [level, text]. level is "ok", "warn", "error" or "off"
    "hardware": {"camera": ["warn", "starting"], "rfid": ["off", "switched off in settings"],
                 "buttons": ["off", "switched off in settings"], "leds": ["off", "switched off in settings"],
                 "bluetooth": ["off", "switched off in settings"], "power": ["off", "only checked on a Raspberry Pi"]},
}


def set_hardware(part, level, text):
    with lock:
        if state["hardware"][part] == [level, text]:
            return
        state["hardware"][part] = [level, text]
    print("  " + part + ": " + level + " - " + text)


def set_message(text):
    with lock:
        state["message"] = text
    print(text)


# ---------- Camera ----------
camera = None


def open_camera():
    global camera
    if CAMERA == "pi":
        from picamera2 import Picamera2
        if not Picamera2.global_camera_info():
            raise RuntimeError("no camera found - check the ribbon cable (blue side) and both clips")
        camera = Picamera2()
        # "RGB888" in picamera2 gives the same colour order OpenCV uses (BGR)
        camera.configure(camera.create_video_configuration(main={"size": (WIDTH, HEIGHT), "format": "RGB888"}))
        camera.start()
    else:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            camera = None
            raise RuntimeError("no USB camera found")
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)


def close_camera():
    global camera
    try:
        if CAMERA == "pi":
            camera.close()
        else:
            camera.release()
    except Exception:
        pass
    camera = None


def read_frame():
    if CAMERA == "pi":
        return camera.capture_array()
    ok, frame = camera.read()
    return frame if ok else None


# ---------- Face recognition (same 3 steps as face_app.py) ----------
detector = None
recognizer = None


def load_models():
    global detector, recognizer
    if not hasattr(cv2, "FaceDetectorYN"):
        sys.exit("This OpenCV (" + cv2.__version__ + ") is too old. Need 4.5.4 or newer (Raspberry Pi OS Bookworm).")
    yunet_path, sface_path = download_models()
    detector = cv2.FaceDetectorYN.create(yunet_path, "", (WIDTH, HEIGHT), MIN_FACE_CONFIDENCE)
    recognizer = cv2.FaceRecognizerSF.create(sface_path, "")


def find_faces(frame):
    # Each face row: x, y, w, h, 10 numbers for eyes/nose/mouth, confidence
    detector.setInputSize((frame.shape[1], frame.shape[0]))
    ok, faces = detector.detect(frame)
    return [] if faces is None else faces


def embed(frame, face):
    aligned = recognizer.alignCrop(frame, face)      # straighten and crop the face
    vec = recognizer.feature(aligned).flatten()
    return vec / np.linalg.norm(vec)                 # length 1 so dot product == cosine similarity


def identify(vec, db):
    # Return (name, score). Name is "Unknown" if nobody is similar enough.
    best_name, best_score = "Unknown", -1.0
    for name, vectors in db.items():
        score = float(np.max(vectors @ vec))         # best match among that person's samples
        if score > best_score:
            best_name, best_score = name, score
    if best_score < THRESHOLD:
        return "Unknown", best_score
    return best_name, best_score


def camera_loop():
    samples = []
    last_sample = 0.0
    while True:
        start = time.time()

        # (Re)connect the camera if it is not open
        if camera is None:
            try:
                open_camera()
                with lock:
                    state["last_frame_time"] = time.time()   # so the health check gives it time for the first picture
                set_hardware("camera", "ok", "connected")
            except Exception as error:
                set_hardware("camera", "error", "not connected: " + str(error))
                time.sleep(10)
                continue

        try:
            frame = read_frame()
        except Exception as error:
            set_hardware("camera", "error", "stopped working: " + str(error))
            close_camera()
            time.sleep(5)
            continue
        if frame is None:
            set_hardware("camera", "error", "gives no picture")
            time.sleep(1)
            continue
        set_hardware("camera", "ok", "working")

        with lock:
            registering = state["register_name"]
            known = dict(db)

        faces = find_faces(frame)
        names = []
        for face in faces:
            x, y, w, h = [int(v) for v in face[:4]]
            if registering:
                # Take a sample only when exactly one face is visible, spaced out a little
                if len(faces) == 1 and time.time() - last_sample > 0.3:
                    samples.append(embed(frame, face))
                    last_sample = time.time()
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                continue
            name, score = identify(embed(frame, face), known)
            color = (0, 200, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, name + " (" + format(score, ".2f") + ")", (x, max(y - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            names.append(name)

        if registering:
            cv2.putText(frame, "Registering " + registering + ": " + str(len(samples)) + "/" + str(SAMPLES_PER_PERSON),
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            if finish_registration(registering, samples):
                samples = []

        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        now = time.time()
        with lock:
            state["jpeg"] = jpeg.tobytes()
            state["frame_id"] += 1
            state["last_frame_time"] = now
            state["in_view"] = names
            for name in names:
                if name != "Unknown":
                    state["last_seen"][name] = now

        # Wait so we check about FPS pictures per second
        time.sleep(max(0, 1 / FPS - (time.time() - start)))
        with lock:
            state["fps"] = round(1 / (time.time() - start), 1)


def finish_registration(name, samples):
    # Returns True when registering is over (saved or timed out)
    with lock:
        if len(samples) >= SAMPLES_PER_PERSON:
            new = np.array(samples, dtype=np.float32)
            db[name] = np.vstack([db[name], new]) if name in db else new
            save_db(db)
            state["message"] = "Saved face of " + name + "."
            state["register_name"] = None
            return True
        if time.time() - state["register_started"] > 30:
            state["message"] = "Registration timed out. Make sure only one face is in view."
            state["register_name"] = None
            return True
        return False


# ---------- Status rules ----------
def all_names():
    with lock:
        return sorted(set(db) | set(cards.values()) | set(phones.values()))


def evidence(name, now):
    # Which sensors say this person is in the cabin right now
    with lock:
        how = []
        seen = state["last_seen"].get(name)
        if seen is not None and now - seen < PRESENT_SECONDS:
            how.append("face")
        if name in state["card_in"]:
            how.append("card")
        phone = state["phone_seen"].get(name)
        if phone is not None and now - phone < BT_PRESENT_SECONDS:
            how.append("phone")
        return how


def person_status(name, now):
    # Returns (status, reason)
    with lock:
        override = state["overrides"].get(name)
        if override and now > override["until"]:
            del state["overrides"][name]             # override time is over
            override = None
        if override:
            minutes_left = int((override["until"] - now) / 60) + 1
            return override["status"], "set by " + override["source"] + ", " + str(minutes_left) + " min left"
        how = evidence(name, now)
        if how:
            return "Available", "in cabin (" + " + ".join(how) + ")"
        return "Away", "not seen"


def button_person():
    # The person the hardware buttons and LEDs belong to
    names = all_names()
    with lock:
        chosen = settings.get("button_person")
    if chosen in names:
        return chosen
    return names[0] if names else None


def set_override(name, status, source):
    with lock:
        current = state["overrides"].get(name)
        if status == "Auto" or (current and current["status"] == status):
            state["overrides"].pop(name, None)
            state["message"] = name + ": back to automatic status."
        elif status in STATUS_COLORS:
            state["overrides"][name] = {"status": status, "until": time.time() + OVERRIDE_MINUTES * 60,
                                        "source": source}
            state["message"] = name + ": " + status + " (set by " + source + ")."


def card_tapped(card_id):
    now = time.time()
    with lock:
        # The reader sees a card many times while it is held, so ignore repeats
        if card_id == state["last_card"] and now - state["last_card_time"] < CARD_REPEAT_SECONDS:
            state["last_card_time"] = now
            return
        state["last_card"], state["last_card_time"] = card_id, now

        if state["link_name"] and now - state["link_started"] < 30:
            cards[card_id] = state["link_name"]
            save_json(CARDS_FILE, cards)
            state["message"] = "Card " + card_id + " linked to " + state["link_name"] + "."
            state["link_name"] = None
            return

        name = cards.get(card_id)
        if name is None:
            state["message"] = "Unknown card " + card_id + ". Link it from the web page."
        elif name in state["card_in"]:
            del state["card_in"][name]
            state["message"] = name + " tapped out."
        else:
            state["card_in"][name] = now
            state["message"] = name + " tapped in."


# ---------- Hardware: RFID, buttons, LEDs ----------
GPIO = None
rfid_reader = None
leds = None


def start_hardware():
    global GPIO, rfid_reader, leds
    if not ON_PI:
        for part in ["rfid", "buttons", "leds", "bluetooth"]:
            set_hardware(part, "off", "not a Raspberry Pi")
        return

    if USE_RFID or USE_BUTTONS:
        try:
            import RPi.GPIO as gpio_library
            GPIO = gpio_library
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
        except Exception as error:
            print("  GPIO library not working:", error)

    if USE_BUTTONS:
        try:
            for pin in BUTTON_PINS.values():
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)   # pressed = connected to GND = LOW
            set_hardware("buttons", "ok", "ready - press one to test (wiring can't be checked until pressed)")
        except Exception as error:
            set_hardware("buttons", "error", "can't use the GPIO pins: " + str(error))

    if USE_RFID:
        if not os.path.exists("/dev/spidev0.0"):
            run_command(["sudo", "raspi-config", "nonint", "do_spi", "0"], 30)    # turn SPI on
            set_hardware("rfid", "error", "SPI was off, now turned on - reboot the Pi (sudo reboot)")
        else:
            try:
                from mfrc522 import MFRC522
                rfid_reader = MFRC522(pin_rst=RFID_RST_PIN)
                check_rfid()
            except Exception as error:
                set_hardware("rfid", "error", "library problem: " + str(error))

    if USE_LEDS:
        if os.geteuid() != 0:
            set_hardware("leds", "error", "need sudo - run: sudo python3 smartcabin_pi.py")
        else:
            try:
                from rpi_ws281x import PixelStrip
                leds = PixelStrip(LED_COUNT, LED_PIN, 800000, 10, False, LED_BRIGHTNESS)
                leds.begin()
                set_hardware("leds", "ok", "sending colours (LEDs can't report back - look at them)")
            except Exception as error:
                set_hardware("leds", "error", "can't start: " + str(error))

    if USE_BLUETOOTH:
        run_command(["rfkill", "unblock", "bluetooth"])
        run_command(["bluetoothctl", "power", "on"])
        check_bluetooth_adapter()

    threading.Thread(target=hardware_loop, daemon=True).start()


def check_rfid():
    # The RC522 has a version number inside. If we can't read it, the reader is not connected.
    version = rfid_reader.Read_MFRC522(0x37)
    if version in (0x00, 0xFF):
        set_hardware("rfid", "error", "not responding - check the wires and that it is on 3.3 V")
        return False
    with lock:
        was_broken = state["hardware"]["rfid"][0] != "ok"
    if was_broken:
        rfid_reader.MFRC522_Init()                   # it came back, so set it up again
    set_hardware("rfid", "ok", "connected (chip version " + hex(version) + ")")
    return True


def read_card():
    # Returns the card id like "A1B2C3D4", or None if no card is on the reader
    status, tag_type = rfid_reader.MFRC522_Request(rfid_reader.PICC_REQIDL)
    if status != rfid_reader.MI_OK:
        return None
    status, uid = rfid_reader.MFRC522_Anticoll()
    if status != rfid_reader.MI_OK:
        return None
    return "".join(format(b, "02X") for b in uid[:4])


def show_leds(color):
    for i in range(LED_COUNT):
        leds.setPixelColorRGB(i, color[0], color[1], color[2])
    leds.show()


def button_pressed(status):
    name = button_person()
    if name is None:
        set_message("Button pressed, but no one is registered yet.")
        return
    set_override(name, status, "button")
    set_hardware("buttons", "ok", "working (last press: " + status + " at " + time.strftime("%H:%M:%S") + ")")


def hardware_loop():
    pressed_since = {name: None for name in BUTTON_PINS}
    last_color = None
    last_rfid_check = 0.0
    while True:
        now = time.time()
        try:
            # Buttons: act once when a button goes down. Held down for 10 s = stuck or wires touching.
            if GPIO and state["hardware"]["buttons"][0] != "off":
                stuck = []
                for name, pin in BUTTON_PINS.items():
                    pressed = GPIO.input(pin) == GPIO.LOW
                    if pressed and pressed_since[name] is None:
                        pressed_since[name] = now
                        button_pressed(name)
                    if not pressed:
                        pressed_since[name] = None
                    if pressed and now - pressed_since[name] > 10:
                        stuck.append(name)
                if stuck:
                    set_hardware("buttons", "warn", ", ".join(stuck) + " button stuck down or its wires are touching")
                elif state["hardware"]["buttons"][0] == "warn":
                    set_hardware("buttons", "ok", "working")

            # RFID: check the reader is still there every 5 s, read cards in between
            if rfid_reader:
                if now - last_rfid_check > 5:
                    check_rfid()
                    last_rfid_check = now
                if state["hardware"]["rfid"][0] == "ok":
                    card_id = read_card()
                    if card_id:
                        card_tapped(card_id)

            # LEDs show the button person's status. Only send new colours when it changes.
            if leds:
                name = button_person()
                status = person_status(name, now)[0] if name else "Away"
                with lock:
                    setting_up = state["register_name"] or state["link_name"] or state["pairing_name"]
                color = SETUP_COLOR if setting_up else STATUS_COLORS[status]
                if color != last_color:
                    show_leds(color)
                    last_color = color
        except Exception as error:
            print("Hardware error:", error)
            time.sleep(1)
        time.sleep(0.1)


def stop_hardware():
    try:
        if leds:
            show_leds((0, 0, 0))
        if GPIO:
            GPIO.cleanup()
    except Exception:
        pass


# ---------- Bluetooth phones ----------
def check_bluetooth_adapter():
    text = run_command(["bluetoothctl", "show"])
    if "Powered: yes" in text:
        set_hardware("bluetooth", "ok", "ready, " + str(len(phones)) + " phone(s) paired")
    elif "Controller" in text:
        run_command(["bluetoothctl", "power", "on"])
        set_hardware("bluetooth", "warn", "was switched off, turning it on")
    else:
        set_hardware("bluetooth", "error", "no Bluetooth adapter found (or the bluetooth service is not running)")


def paired_devices():
    # Addresses of the phones paired with the Pi
    text = run_command(["bluetoothctl", "devices", "Paired"])
    if "Device" not in text:
        text = run_command(["bluetoothctl", "paired-devices"])     # older bluetoothctl
    return [line.split()[1] for line in text.splitlines() if line.startswith("Device ")]


def pair_phone(name):
    # Make the Pi visible for 60 s and accept the first phone that pairs
    with lock:
        state["pairing_name"] = name
    set_message("Pairing for " + name + ": on the phone open Bluetooth and choose '" + socket.gethostname() + "' within 60 s.")
    before = paired_devices()
    for setting in ["pairable", "discoverable"]:
        run_command(["bluetoothctl", setting, "on"])
    agent = None
    try:
        agent = subprocess.Popen(["bt-agent", "--capability=NoInputNoOutput"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass

    found = None
    end = time.time() + 60
    while time.time() < end and found is None:
        time.sleep(2)
        new = [address for address in paired_devices() if address not in before]
        if new:
            found = new[0]

    if agent:
        agent.terminate()
    run_command(["bluetoothctl", "discoverable", "off"])
    with lock:
        state["pairing_name"] = None
    if found:
        run_command(["bluetoothctl", "trust", found])
        add_phone(name, found)
    else:
        set_message("No phone paired within 60 s. You can also type the phone's Bluetooth address.")


def add_phone(name, address):
    with lock:
        phones[address.upper()] = name
        save_json(PHONES_FILE, phones)
    set_message("Phone " + address.upper() + " linked to " + name + ".")


def phone_is_near(address):
    # l2ping asks the phone for a tiny reply. Works while the phone's Bluetooth is on, even if it is locked.
    return "bytes from" in run_command(["l2ping", "-c", "1", "-t", "3", address], 8)


def bluetooth_loop():
    last_adapter_check = 0.0
    while True:
        if time.time() - last_adapter_check > 30:
            check_bluetooth_adapter()
            last_adapter_check = time.time()
        with lock:
            phone_list = dict(phones)
            pairing = state["pairing_name"]
        if not pairing and state["hardware"]["bluetooth"][0] == "ok":
            for address, name in phone_list.items():
                if phone_is_near(address):
                    with lock:
                        state["phone_seen"][name] = time.time()
        time.sleep(BT_CHECK_SECONDS)


# ---------- Health: camera picture age, power supply and temperature ----------
def check_power():
    text = run_command(["vcgencmd", "get_throttled"])
    if "=" not in text:
        set_hardware("power", "off", "can't read (vcgencmd missing)")
        return
    flags = int(text.strip().split("=")[1], 16)
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temperature = int(f.read()) / 1000
    except OSError:
        temperature = 0
    temp_text = ", CPU " + format(temperature, ".0f") + " C"
    if flags & 0x1:
        set_hardware("power", "error", "UNDER-VOLTAGE now - use a 5 V 3 A USB-C supply (Pi 4), power the LEDs separately" + temp_text)
    elif temperature > 80:
        set_hardware("power", "warn", "too hot, the Pi is slowing down" + temp_text)
    elif flags & 0x10000:
        set_hardware("power", "warn", "under-voltage happened since the last start - check the supply" + temp_text)
    else:
        set_hardware("power", "ok", "good" + temp_text)


def health_loop():
    while True:
        with lock:
            age = time.time() - state["last_frame_time"]
            camera_ok = state["hardware"]["camera"][0] == "ok"
        if camera_ok and age > 10:
            set_hardware("camera", "error", "no new picture for " + str(int(age)) + " s - check the ribbon cable")
        if ON_PI:
            check_power()
        time.sleep(5)


# ---------- Everything for the web page ----------
def status():
    now = time.time()
    names = all_names()
    owner = button_person()
    with lock:
        people = []
        for name in names:
            status_text, reason = person_status(name, now)
            times = [t for t in [state["last_seen"].get(name), state["card_in"].get(name), state["phone_seen"].get(name)] if t]
            people.append({"name": name, "status": status_text, "reason": reason,
                           "how": " + ".join(evidence(name, now)) or "-",
                           "last_seen": time.strftime("%H:%M:%S", time.localtime(max(times))) if times else "-",
                           "override": state["overrides"][name]["status"] if name in state["overrides"] else "Auto",
                           "has": [label for label, found in [("face", name in db), ("card", name in cards.values()),
                                                              ("phone", name in phones.values())] if found]})
        linking = state["link_name"] if now - state["link_started"] < 30 else None
        owner_status = person_status(owner, now) if owner else ("Away", "no one registered yet")
        return {"time": time.strftime("%H:%M:%S"), "fps": state["fps"], "in_view": state["in_view"],
                "button_person": owner, "owner_status": owner_status[0], "owner_reason": owner_status[1],
                "registering": state["register_name"], "linking": linking, "pairing": state["pairing_name"],
                "message": state["message"], "people": people, "device_name": socket.gethostname(),
                "cards": [{"id": card_id, "name": name} for card_id, name in sorted(cards.items())],
                "phones": [{"address": address, "name": name} for address, name in sorted(phones.items())],
                "hardware": [{"part": part, "level": value[0], "text": value[1]} for part, value in state["hardware"].items()]}


def delete_person(name):
    with lock:
        db.pop(name, None)
        save_db(db)
        for card_id in [c for c, n in cards.items() if n == name]:
            del cards[card_id]
        save_json(CARDS_FILE, cards)
        for address in [a for a, n in phones.items() if n == name]:
            del phones[address]
            run_command(["bluetoothctl", "remove", address])
        save_json(PHONES_FILE, phones)
        for table in ["last_seen", "card_in", "phone_seen", "overrides"]:
            state[table].pop(name, None)
        state["message"] = "Deleted " + name + "."


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Cabin Pi</title>
<style>
  body { margin: 0; padding: 16px; font-family: sans-serif; background: #f4f4f4; color: #222; }
  .wrap { max-width: 860px; margin: auto; }
  .box { background: #fff; border-radius: 8px; padding: 12px; margin-bottom: 12px; overflow-x: auto; }
  img { width: 100%; border-radius: 6px; background: #000; }
  table { width: 100%; border-collapse: collapse; }
  td, th { text-align: left; padding: 6px; border-bottom: 1px solid #eee; vertical-align: top; }
  input, select { padding: 6px; }
  button { padding: 5px 9px; margin: 1px; cursor: pointer; border: 1px solid #bbb; background: #f7f7f7; border-radius: 4px; }
  button.on { background: #222; color: #fff; border-color: #222; }
  #msg { color: #b35c00; min-height: 1em; }
  #owner { font-size: 22px; font-weight: bold; }
  .dot { display: inline-block; width: 14px; height: 14px; border-radius: 50%; vertical-align: middle; margin-right: 6px; }
  .big { width: 20px; height: 20px; }
  small { color: #666; }
  .row { margin: 6px 0; }
</style>
</head>
<body>
<div class="wrap">
  <h2>Smart Cabin - Pi</h2>

  <div class="box">
    <div class="row">Hardware buttons and LEDs are for: <select id="buttonPerson" onchange="post('/button_person', {name: this.value})"></select></div>
    <span class="dot big" id="ownerDot"></span><span id="owner">-</span> <small id="ownerReason"></small>
    <p id="msg"></p>
    <small id="info"></small>
  </div>

  <div class="box">
    <b>People</b> <small>(override buttons work only for that person; press again or Auto to clear)</small>
    <table><thead><tr><th>Name and status</th><th>How we know</th><th>Last seen</th><th>Manual override</th><th></th></tr></thead>
    <tbody id="people"></tbody></table>
  </div>

  <div class="box">
    <b>Hardware check</b>
    <table><tbody id="hardware"></tbody></table>
  </div>

  <div class="box"><img src="/stream.mjpg" alt="Live camera"><p>In view now: <span id="inview">-</span></p></div>

  <div class="box">
    <b>Register a face</b>
    <p>Only that person should face the camera, moving their head slightly.</p>
    <input id="faceName" placeholder="Name"> <button onclick="sendName('/register', 'faceName')">Register face</button>
  </div>

  <div class="box">
    <b>RFID cards</b>
    <p>Type a name, press Link card, then tap the card on the reader within 30 s.</p>
    <input id="cardName" placeholder="Name"> <button onclick="sendName('/link', 'cardName')">Link card</button>
    <table><tbody id="cards"></tbody></table>
  </div>

  <div class="box">
    <b>Bluetooth phones</b>
    <p>Type a name and press Pair phone. Then on the phone open Bluetooth settings and choose <b id="deviceName"></b> within 60 s.
       The person counts as in the cabin while their phone is near (about 10 m, so it can also be next door).</p>
    <input id="phoneName" placeholder="Name"> <button onclick="sendName('/pair', 'phoneName')">Pair phone</button>
    <p><small>If the phone doesn't find the Pi (iPhones often don't), type its Bluetooth address
       (phone Settings, About, Bluetooth address):</small><br>
    <input id="phoneName2" placeholder="Name"> <input id="phoneAddress" placeholder="AA:BB:CC:DD:EE:FF">
    <button onclick="addPhone()">Add phone</button></p>
    <table><tbody id="phones"></tbody></table>
  </div>
</div>
<script>
var COLORS = {"Available": "#1a9b3c", "Busy": "#d22", "Back soon": "#e0a000", "Away": "#999"};
var LEVEL_COLORS = {"ok": "#1a9b3c", "warn": "#e0a000", "error": "#d22", "off": "#bbb"};
var LABELS = {"camera": "Camera", "rfid": "RFID reader", "buttons": "Buttons", "leds": "LEDs",
              "bluetooth": "Bluetooth", "power": "Power and temperature"};
var drawn = {};   // only redraw a table when its data changed, so clicks are not lost

function post(url, data) {
  return fetch(url, {method: "POST", body: new URLSearchParams(data)}).then(refresh);
}
function sendName(url, inputId) {
  var name = document.getElementById(inputId).value.trim();
  if (name) post(url, {name: name});
  document.getElementById(inputId).value = "";
}
function addPhone() {
  var name = document.getElementById("phoneName2").value.trim();
  var address = document.getElementById("phoneAddress").value.trim();
  if (name && address) post("/add_phone", {name: name, address: address});
}
function dot(color) {
  var span = document.createElement("span");
  span.className = "dot";
  span.style.background = color;
  return span;
}
function button(label, active, onclick) {
  var b = document.createElement("button");
  b.textContent = label;
  if (active) b.className = "on";
  b.onclick = onclick;
  return b;
}
function deleteButton(label, url, data) {
  return button("Delete", false, function () { if (confirm("Delete " + label + "?")) post(url, data); });
}
function changed(key, data) {
  var text = JSON.stringify(data);
  if (drawn[key] === text) return false;
  drawn[key] = text;
  return true;
}

function drawPeople(people) {
  var body = document.getElementById("people");
  body.innerHTML = "";
  if (people.length === 0) body.innerHTML = "<tr><td colspan=5>No one registered yet.</td></tr>";
  people.forEach(function (p) {
    var row = body.insertRow();
    var cell = row.insertCell();
    cell.appendChild(dot(COLORS[p.status]));
    var name = document.createElement("b");
    name.textContent = p.name + " - " + p.status;
    cell.appendChild(name);
    var reason = document.createElement("div");
    reason.innerHTML = "<small></small>";
    reason.firstChild.textContent = p.reason + " | has: " + (p.has.join(", ") || "nothing yet");
    cell.appendChild(reason);
    row.insertCell().textContent = p.how;
    row.insertCell().textContent = p.last_seen;
    var buttons = row.insertCell();
    ["Available", "Busy", "Back soon", "Auto"].forEach(function (s) {
      buttons.appendChild(button(s, p.override === s, function () { post("/override", {name: p.name, status: s}); }));
    });
    row.insertCell().appendChild(deleteButton(p.name + " (face, cards and phones)", "/delete", {name: p.name}));
  });
}

function drawSimpleTable(id, items, emptyText, makeRow) {
  var body = document.getElementById(id);
  body.innerHTML = "";
  if (items.length === 0) body.innerHTML = "<tr><td>" + emptyText + "</td></tr>";
  items.forEach(function (item) { makeRow(body.insertRow(), item); });
}

function refresh() {
  fetch("/status.json").then(function (r) { return r.json(); }).then(function (s) {
    document.getElementById("owner").textContent = (s.button_person || "-") + ": " + s.owner_status;
    document.getElementById("ownerDot").style.background = COLORS[s.owner_status];
    document.getElementById("ownerReason").textContent = s.owner_reason;
    document.getElementById("deviceName").textContent = s.device_name;

    var select = document.getElementById("buttonPerson");
    var names = s.people.map(function (p) { return p.name; });
    if (changed("select", names)) {
      select.innerHTML = "";
      names.forEach(function (n) { var o = document.createElement("option"); o.textContent = n; select.appendChild(o); });
    }
    if (document.activeElement !== select && s.button_person) select.value = s.button_person;

    var msg = s.message;
    if (s.registering) msg = "Registering face of " + s.registering + "... (LEDs blue)";
    if (s.linking) msg = "Tap the card for " + s.linking + " now... (LEDs blue)";
    if (s.pairing) msg = "Waiting for " + s.pairing + "'s phone to pair... (LEDs blue)";
    document.getElementById("msg").textContent = msg;
    document.getElementById("info").textContent = "Updated " + s.time + " | camera " + s.fps + " fps";
    document.getElementById("inview").textContent = s.in_view.join(", ") || "nobody";

    if (changed("people", s.people)) drawPeople(s.people);
    if (changed("hardware", s.hardware)) drawSimpleTable("hardware", s.hardware, "", function (row, h) {
      var cell = row.insertCell();
      cell.appendChild(dot(LEVEL_COLORS[h.level]));
      cell.appendChild(document.createTextNode(LABELS[h.part]));
      row.insertCell().textContent = h.level.toUpperCase() + " - " + h.text;
    });
    if (changed("cards", s.cards)) drawSimpleTable("cards", s.cards, "No cards linked yet.", function (row, c) {
      row.insertCell().textContent = c.id;
      row.insertCell().textContent = c.name;
      row.insertCell().appendChild(deleteButton("card " + c.id, "/delete_card", {id: c.id}));
    });
    if (changed("phones", s.phones)) drawSimpleTable("phones", s.phones, "No phones linked yet.", function (row, p) {
      row.insertCell().textContent = p.address;
      row.insertCell().textContent = p.name;
      row.insertCell().appendChild(deleteButton("phone " + p.address, "/delete_phone", {address: p.address}));
    });
  }).catch(function () {
    document.getElementById("info").textContent = "Pi not reachable - is smartcabin_pi.py running?";
  });
}
refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            send(self, 200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        elif self.path == "/status.json":
            send(self, 200, "application/json", json.dumps(status()).encode("utf-8"))
        elif self.path == "/snapshot.jpg":
            with lock:
                jpeg = state["jpeg"]
            if jpeg is None:
                self.send_error(503, "Camera not ready")
            else:
                send(self, 200, "image/jpeg", jpeg)
        elif self.path == "/stream.mjpg":
            send_stream(self)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        name = form.get("name", [""])[0].strip()
        if self.path == "/override" and name:
            set_override(name, form.get("status", [""])[0], "web page")
        elif self.path == "/button_person" and name:
            with lock:
                settings["button_person"] = name
                save_json(SETTINGS_FILE, settings)
            set_message("Hardware buttons and LEDs are now for " + name + ".")
        elif self.path == "/register" and name:
            with lock:
                state["register_name"] = name
                state["register_started"] = time.time()
                state["message"] = ""
        elif self.path == "/link" and name:
            with lock:
                state["link_name"] = name
                state["link_started"] = time.time()
                state["message"] = ""
        elif self.path == "/pair" and name:
            if state["hardware"]["bluetooth"][0] not in ("ok", "warn"):
                set_message("Bluetooth is not working, see Hardware check.")
            elif not state["pairing_name"]:
                threading.Thread(target=pair_phone, args=(name,), daemon=True).start()
        elif self.path == "/add_phone" and name:
            address = form.get("address", [""])[0].strip().replace("-", ":")
            if re.fullmatch(r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}", address):
                add_phone(name, address)
            else:
                set_message("That is not a Bluetooth address. It looks like AA:BB:CC:DD:EE:FF.")
        elif self.path == "/delete" and name:
            delete_person(name)
        elif self.path == "/delete_card":
            card_id = form.get("id", [""])[0]
            with lock:
                if cards.pop(card_id, None) is not None:
                    save_json(CARDS_FILE, cards)
                    state["message"] = "Deleted card " + card_id + "."
        elif self.path == "/delete_phone":
            address = form.get("address", [""])[0]
            with lock:
                if phones.pop(address, None) is not None:
                    save_json(PHONES_FILE, phones)
                    run_command(["bluetoothctl", "remove", address])
                    state["message"] = "Deleted phone " + address + "."
        send(self, 200, "text/plain", b"ok")

    def log_message(self, format, *args):
        pass    # don't print a line for every request


def send(handler, code, content_type, body):
    handler.send_response(code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def send_stream(handler):
    # Live video (MJPEG): keep sending each new picture, separated by "--frame"
    handler.send_response(200)
    handler.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    last_id = -1
    try:
        while True:
            with lock:
                jpeg, frame_id = state["jpeg"], state["frame_id"]
            if jpeg is not None and frame_id != last_id:
                handler.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                    + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                last_id = frame_id
            time.sleep(0.05)
    except (BrokenPipeError, ConnectionResetError):
        pass    # the viewer closed the page


def my_ip():
    # The address other computers on the same Wi-Fi can use to reach this one
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))     # no data is sent, it only picks the right network card
        return s.getsockname()[0]
    except OSError:
        return "this-device-ip"
    finally:
        s.close()


def main():
    global db, cards, phones, settings
    load_models()
    db = load_db()
    cards = load_json(CARDS_FILE, {})
    phones = load_json(PHONES_FILE, {})
    settings = load_json(SETTINGS_FILE, {})
    print("Faces:", ", ".join(db) or "none yet", "| Cards:", len(cards), "| Phones:", len(phones))
    print("Hardware check:")
    start_hardware()
    threading.Thread(target=camera_loop, daemon=True).start()
    threading.Thread(target=health_loop, daemon=True).start()
    if ON_PI and USE_BLUETOOTH:
        threading.Thread(target=bluetooth_loop, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("Web page ready:  http://" + my_ip() + ":" + str(PORT) + "   (or http://localhost:" + str(PORT) + " through an SSH tunnel)")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        stop_hardware()


if __name__ == "__main__":
    main()


# ---------------- Wiring (GPIO numbers, physical pin in brackets) ----------------
# RC522 RFID reader (3.3 V only!):
#   SDA -> GPIO8 (24)   SCK -> GPIO11 (23)   MOSI -> GPIO10 (19)   MISO -> GPIO9 (21)
#   RST -> GPIO25 (22)  3.3V -> 3.3V (1)     GND -> GND (6)        IRQ -> not used
# Buttons (one leg to the GPIO pin, the other leg to any GND, no resistor needed):
#   Available -> GPIO5 (29)   Busy -> GPIO6 (31)   Back soon -> GPIO26 (37)   GND -> (39)
# NeoPixel / WS2812 LEDs:
#   DIN -> GPIO18 (12)   5V -> 5V (2)   GND -> GND (14)
#   Keep LED_BRIGHTNESS low: the Pi's 5 V pin can't power many LEDs at full white.
# Bluetooth and the camera are built in / on the ribbon cable - nothing to wire.
