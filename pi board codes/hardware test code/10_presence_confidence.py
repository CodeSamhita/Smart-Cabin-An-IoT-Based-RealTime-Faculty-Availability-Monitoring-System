# Presence confidence on a web page: how sure are we that the owner is in the cabin?
# Three signals, each 1 or 0:
#   F = face      : the owner's face was seen in the last FACE_HOLD_SECONDS      (camera, YuNet + SFace)
#   R = RFID      : the owner's card was tapped in (tap = in, tap again = out)   (RC522)
#   B = Bluetooth : one of the owner's devices answered in the last NEAR_SECONDS (l2ping)
# Together they make one of 8 combinations, 000 to 111. Each has its own confidence in CONFIDENCE below.
#
# Everything is set up on the page, for one owner:
#   - type the owner's name
#   - Register my face : 10 photos of the one face in view       -> known_faces.json (same file as test 8)
#   - Add a device     : pair the phone / laptop / watch once     -> bluetooth_devices.json (same file as test 9)
#                        Only the identity is kept: not trusted, disconnected, never used as a keyboard etc.
#   - Link my card     : the next card tapped is the owner's      -> presence_confidence.json
#
# Bluetooth is only used to DETECT the device, never as an input or output device:
#   - each check opens a link with l2ping (one "are you there?", no service) and disconnects straight after
#   - a guard drops (and untrusts) any other connection to the Pi every GUARD_SECONDS, so a phone can't
#     use the Pi as a speaker, headset, keyboard or for file transfer
#   - saved devices are untrusted and no pairing agent runs outside the 60 s "Add a device" window,
#     so BlueZ refuses every service the device asks for
#
# Run on the Pi:   sudo python3 10_presence_confidence.py           then open the address it prints (port 8086)
# Run anywhere:    python3 10_presence_confidence.py --sim          no hardware: buttons switch each signal,
#                                                                   registering and pairing are pretended (not saved)
# sudo is needed for l2ping and the RC522. Stop the other tests first: only one program can use the camera.
#
# Libraries (once):  sudo apt install -y python3-picamera2 python3-opencv python3-spidev python3-rpi-lgpio bluez bluez-tools
#                    sudo pip3 install mfrc522 --break-system-packages --no-deps

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8086
SIM = "--sim" in sys.argv

FACE_HOLD_SECONDS = 10        # face = 1 if the owner was seen within this time
PICTURE_SECONDS = 2           # time between pictures
RESOLUTION = (1296, 972)      # faces need the pixels (none found at 640x480 in a test photo)
FACE_THRESHOLD = 0.36         # same as 8_face_recognition.py
SAMPLES = 10                  # photos taken when registering a face
REGISTER_SECONDS = 30         # give up registering after this long
NEAR_SECONDS = 60             # Bluetooth = 1 if a device answered within this time
PING_SECONDS = 10             # time between Bluetooth rounds
MAX_DEVICES = 5               # Bluetooth devices per owner
PAIR_SECONDS = 60             # how long the Pi is visible and pairable when adding a device
GUARD_SECONDS = 3             # how often other connections to the Pi are looked for and dropped
RST_PIN = 25                  # RC522 RST on GPIO25 (pin 22)
TAP_GAP_SECONDS = 2           # the card must be away this long before the next tap counts

# Face, RFID, Bluetooth -> (confidence %, what it most likely means)
CONFIDENCE = {
    "000": (2,  "Not in the cabin. No signal at all"),
    "001": (25, "Phone is near, but not seen and no card. Could be in the next room (Bluetooth goes through walls)"),
    "010": (35, "Card tapped in, but not seen and no phone. May have left without tapping out"),
    "011": (55, "Card and phone, but not seen. Probably in, outside the camera's view"),
    "100": (70, "Seen, but no card and no phone. In the cabin, forgot to tap"),
    "101": (85, "Seen and phone near. In the cabin"),
    "110": (90, "Seen and tapped in. In the cabin"),
    "111": (99, "Seen, tapped in and phone near. In the cabin, confirmed"),
}
# Confidence % from -> level name (checked top down)
LEVELS = [(90, "Very high"), (70, "High"), (40, "Medium"), (15, "Low"), (0, "Very low")]

FOLDER = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(FOLDER, "presence_confidence.json")
FACES_FILE = os.path.join(FOLDER, "known_faces.json")
DEVICES_FILE = os.path.join(FOLDER, "bluetooth_devices.json")
MODEL_FOLDER = os.path.join(FOLDER, "models")
YUNET_NEW = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_OLD = "https://github.com/opencv/opencv_zoo/raw/4fb591053ba1201c07c68929cc324787d5afaa6c/models/face_detection_yunet/face_detection_yunet_2022mar.onnx"
SFACE = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")

lock = threading.Lock()
state = {"face_seen": 0, "face_text": "starting...", "face_ok": False,
         "register": False, "register_count": 0, "register_started": 0,
         "card_in": False, "card_text": "starting...", "card_ok": False, "linking": False,
         "phone_seen": 0, "phone_text": "starting...", "phone_ok": False,
         "pairing": False, "pairing_until": 0, "nearby": [], "seen": {},
         "checking": "", "connected": [], "dropped": 0, "last_drop": "",
         "message": "", "history": []}
sim = {"face": False, "card": False, "phone": False}
sim_files = {"faces": {}, "devices": {}}      # in --sim nothing is written to the real files
latest_jpeg = None


# ---------- Saved files ----------
def load_json(path, empty):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return empty


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=1)


def load_faces():
    # {name: [[128 numbers], ...]}
    return sim_files["faces"] if SIM else load_json(FACES_FILE, {})


def save_faces(faces):
    if SIM:
        sim_files["faces"] = faces
    else:
        save_json(FACES_FILE, faces)


def load_devices():
    # {name: [{"address": "AA:BB:..", "name": "Pixel 7", "added": "2026-10-25 14:02"}, ...]}
    return sim_files["devices"] if SIM else load_json(DEVICES_FILE, {})


def save_devices(devices):
    if SIM:
        sim_files["devices"] = devices
    else:
        save_json(DEVICES_FILE, devices)


settings = load_json(SETTINGS_FILE, {})
settings.setdefault("owner", settings.get("owner_face") or settings.get("owner_phone") or "")
settings.setdefault("card", "")


def save_settings():
    save_json(SETTINGS_FILE, {"owner": settings["owner"], "card": settings["card"]})


def run_command(args, timeout=10):
    # Run a command and return what it printed ("" if it failed or took too long)
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def start_process(args):
    # Start a command that keeps running in the background (scan, pairing agent)
    try:
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None


# ---------- F: face ----------
def download(url):
    os.makedirs(MODEL_FOLDER, exist_ok=True)
    path = os.path.join(MODEL_FOLDER, url.split("/")[-1])
    if not os.path.exists(path):
        print("Downloading", os.path.basename(path), "...")
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)          # only keep the file once it is complete
    return path


def finish_register(samples):
    # Called with the lock held. Saves the photos once there are enough, or gives up after REGISTER_SECONDS.
    owner = settings["owner"]
    state["register_count"] = len(samples)
    if len(samples) >= SAMPLES:
        faces = load_faces()
        faces[owner] = faces.get(owner, []) + samples          # registering again adds photos
        save_faces(faces)
        state["register"] = False
        state["message"] = "Face saved for " + owner + " (" + str(len(faces[owner])) + " photos)."
        return True
    if time.time() - state["register_started"] > REGISTER_SECONDS:
        state["register"] = False
        state["message"] = "Registering timed out with " + str(len(samples)) + " photos - not saved. " \
                           "Only one face, well lit, close to the camera."
        return True
    return False


def face_loop():
    global latest_jpeg
    try:
        import cv2
        import numpy as np
        from picamera2 import Picamera2
        if not Picamera2.global_camera_info():
            raise RuntimeError("no camera found - check the ribbon cable")
        camera = Picamera2()
        camera.configure(camera.create_still_configuration(main={"size": RESOLUTION, "format": "RGB888"}))
        camera.start()
        major, minor = [int(n) for n in cv2.__version__.split(".")[:2]]
        detector = cv2.FaceDetectorYN.create(download(YUNET_NEW if (major, minor) >= (4, 8) else YUNET_OLD),
                                             "", (640, 480), 0.9)
        recognizer = cv2.FaceRecognizerSF.create(download(SFACE), "")
    except Exception as error:
        with lock:
            state["face_text"] = "camera not working: " + str(error)
        return
    with lock:
        state["face_ok"] = True

    samples = []
    while True:
        with lock:
            owner = settings["owner"]
            registering = state["register"]
        if not registering:
            samples = []
        known = load_faces()                          # read again, so a face registered meanwhile counts
        frame = camera.capture_array()
        detector.setInputSize((frame.shape[1], frame.shape[0]))
        faces = detector.detect(frame)[1]
        faces = [] if faces is None else faces
        best = -1.0
        for face in faces:
            vector = recognizer.feature(recognizer.alignCrop(frame, face)).flatten()
            vector = vector / np.linalg.norm(vector)  # length 1, so dot product = cosine similarity
            if registering and len(faces) == 1:
                samples.append(vector.tolist())
            elif owner in known:
                best = max(best, float(np.max(np.array(known[owner], dtype=np.float32) @ vector)))
            x, y, w, h = [int(v) for v in face[:4]]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 255) if registering else (0, 200, 0), 3)
        ok, jpeg = cv2.imencode(".jpg", cv2.resize(frame, (640, 480)), [cv2.IMWRITE_JPEG_QUALITY, 70])
        with lock:
            latest_jpeg = jpeg.tobytes()
            if registering:
                state["face_text"] = "registering: " + str(len(samples)) + " / " + str(SAMPLES) + \
                                     (" - only one face, please" if len(faces) > 1 else "")
                finish_register(samples)
            elif not owner or owner not in known:
                state["face_text"] = "no face registered yet - press Register my face"
            elif best >= FACE_THRESHOLD:
                state["face_seen"] = time.time()
                state["face_text"] = owner + " seen (score " + format(best, ".2f") + ")"
            else:
                state["face_text"] = str(len(faces)) + " face(s), not " + owner + \
                                     ("" if best < 0 else " (best " + format(best, ".2f") + ")")
        time.sleep(0.3 if registering else PICTURE_SECONDS)


def sim_register():
    # --sim: pretend to take the 10 photos
    samples = []
    while True:
        time.sleep(0.3)
        samples.append([0.0])
        with lock:
            if not state["register"] or finish_register(samples):
                return


# ---------- R: RFID card ----------
def read_uid(reader):
    # Restart the card (antenna off/on) and read its UID. Returns text like "04 A2 1B 3C", or "".
    reader.AntennaOff()
    time.sleep(0.02)
    reader.AntennaOn()
    time.sleep(0.02)
    status, _ = reader.MFRC522_Request(reader.PICC_REQIDL)
    if status != reader.MI_OK:
        return ""
    status, uid = reader.MFRC522_Anticoll()
    if status != reader.MI_OK:
        return ""
    return " ".join(format(n, "02X") for n in uid[:4])


def card_loop():
    try:
        if not os.path.exists("/dev/spidev0.0"):
            raise RuntimeError("SPI is off (sudo raspi-config nonint do_spi 0, then reboot)")
        import RPi.GPIO as GPIO
        from mfrc522 import MFRC522
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        reader = MFRC522(pin_rst=RST_PIN)
        if reader.Read_MFRC522(0x37) in (0x00, 0xFF):    # version register: no answer = not connected
            raise RuntimeError("RC522 doesn't answer - check the wiring")
    except Exception as error:
        with lock:
            state["card_text"] = "RFID not working: " + str(error)
        return
    with lock:
        state["card_ok"] = True
        state["card_text"] = "link the owner's card below" if not settings["card"] else "waiting for a tap"

    last_read = 0.0
    while True:
        uid = read_uid(reader)
        now = time.time()
        if uid:
            new_tap = now - last_read > TAP_GAP_SECONDS      # a card lying on the reader is one tap, not many
            last_read = now
            if new_tap:
                with lock:
                    if state["linking"]:
                        settings["card"] = uid
                        save_settings()
                        state["linking"] = False
                        state["card_in"] = False
                        state["card_text"] = "card " + uid + " linked. Tap it to come in"
                        state["message"] = "Card " + uid + " linked."
                    elif uid == settings["card"]:
                        state["card_in"] = not state["card_in"]
                        state["card_text"] = ("tapped IN" if state["card_in"] else "tapped OUT") + \
                                             " at " + time.strftime("%H:%M:%S")
                    else:
                        state["card_text"] = "unknown card " + uid + " (not the owner's)"
        time.sleep(0.2)


# ---------- B: Bluetooth ----------
def known_devices(kind=""):
    # [(address, name)] that bluetoothctl knows. kind "Paired" = only paired ones, "" = also just discovered.
    text = run_command(["bluetoothctl", "devices"] + ([kind] if kind else []))
    found = []
    for line in text.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2 and parts[0] == "Device" and MAC.match(parts[1].upper()):
            found.append((parts[1].upper(), parts[2] if len(parts) == 3 else parts[1]))
    return found


def is_saved(address):
    return any(d["address"] == address for devices in load_devices().values() for d in devices)


def save_identity(address, name):
    # Keep the address and keys only: not trusted, and disconnected, so it can't be used as any device
    if not SIM:
        run_command(["bluetoothctl", "untrust", address])
        run_command(["bluetoothctl", "disconnect", address])
    with lock:
        owner = settings["owner"]
        devices = load_devices()
        devices.setdefault(owner, []).append({"address": address, "name": name,
                                              "added": time.strftime("%Y-%m-%d %H:%M")})
        save_devices(devices)
        state["message"] = "Saved " + name + " (" + address + ") for " + owner + "."
        state["pairing"] = False


def pairing_window():
    # 60 s: the Pi is visible and pairable, lists visible devices, and accepts one pairing for the owner
    if SIM:
        with lock:
            state["nearby"] = [{"address": "AA:BB:CC:00:00:0" + str(n), "name": name + " (simulated)"}
                               for n, name in enumerate(["Pixel 7", "iPhone 13", "Galaxy Watch"], 1)]
        while time.time() < state["pairing_until"] and state["pairing"]:
            time.sleep(0.5)
        with lock:
            state["pairing"] = False
            state["nearby"] = []
        return

    before = {address for address, _ in known_devices("Paired")}
    run_command(["bluetoothctl", "pairable", "on"])
    run_command(["bluetoothctl", "discoverable", "on"])
    agent = start_process(["bt-agent", "--capability=NoInputNoOutput"])     # answers "pair?" with yes
    scan = start_process(["bluetoothctl", "--timeout", str(PAIR_SECONDS), "scan", "on"])
    try:
        while time.time() < state["pairing_until"]:
            with lock:
                if not state["pairing"]:                # cancelled, or a device was saved
                    return
            # the device paired by itself (picked the Pi in its own list)
            new = [(a, n) for a, n in known_devices("Paired") if a not in before and not is_saved(a)]
            if new:
                save_identity(new[0][0], new[0][1])
                return
            # list the visible devices, so the page can offer "Pair"
            nearby = [{"address": a, "name": n} for a, n in known_devices()
                      if a not in before and n != a and not MAC.match(n.replace("-", ":").upper())]
            with lock:
                state["nearby"] = nearby[:20]
            time.sleep(2)
        with lock:
            if state["pairing"]:
                state["message"] = "No device paired within " + str(PAIR_SECONDS) + " s."
    finally:
        for process in (scan, agent):
            if process:
                process.terminate()
        run_command(["bluetoothctl", "discoverable", "off"])
        run_command(["bluetoothctl", "pairable", "off"])
        with lock:
            state["pairing"] = False
            state["nearby"] = []


def pair_from_pi(address, name):
    # The Pi asks the device to pair. The device shows a "Pair?" question: accept it there.
    with lock:
        state["message"] = "Asking " + name + " to pair - accept on the device..."
    if SIM:
        time.sleep(1)
        return save_identity(address, name)
    run_command(["bluetoothctl", "--timeout", "30", "pair", address], 35)
    if "Paired: yes" in run_command(["bluetoothctl", "info", address]):
        save_identity(address, name)
    else:
        with lock:
            state["message"] = "Pairing with " + name + " failed or wasn't accepted. Try again."


def check_device(address):
    # Connect once, check, disconnect: l2ping opens a link and sends one echo (no service, no data),
    # then the link is closed straight away instead of waiting for it to time out.
    with lock:
        state["checking"] = address               # the guard leaves this one link alone
    try:
        return "bytes from" in run_command(["l2ping", "-c", "1", "-t", "3", address], 8)
    finally:
        run_command(["bluetoothctl", "disconnect", address])
        with lock:
            state["checking"] = ""


def connected_now():
    # [(address, name)] connected to the Pi right now (checked one by one, so an older bluetoothctl
    # that ignores the "Connected" filter can't cause wrong answers)
    return [(a, n) for a, n in known_devices("Connected")
            if "Connected: yes" in run_command(["bluetoothctl", "info", a])]


def guard_loop():
    # The Pi must never be used as an input or output device: drop every connection except a check
    while True:
        time.sleep(GUARD_SECONDS)
        with lock:
            pairing = state["pairing"]
            checking = state["checking"]
        if pairing:                                   # pairing needs its connection for a few seconds
            continue
        found = connected_now()
        for address, name in found:
            if address == checking:
                continue
            run_command(["bluetoothctl", "untrust", address])
            run_command(["bluetoothctl", "disconnect", address])
            with lock:
                state["dropped"] += 1
                state["last_drop"] = name + " at " + time.strftime("%H:%M:%S")
        with lock:
            state["connected"] = [n for a, n in found if a == checking]


def phone_loop():
    if not run_command(["which", "l2ping"]) or not run_command(["which", "bluetoothctl"]):
        with lock:
            state["phone_text"] = "Bluetooth not working: sudo apt install -y bluez bluez-tools"
        return
    run_command(["rfkill", "unblock", "bluetooth"])
    run_command(["bluetoothctl", "power", "on"])
    run_command(["bluetoothctl", "discoverable", "off"])   # only visible while adding a device
    run_command(["bluetoothctl", "pairable", "off"])
    for devices in load_devices().values():                 # untrusted = every service needs permission,
        for d in devices:                                   # and with no agent running it is refused
            run_command(["bluetoothctl", "untrust", d["address"]])
            run_command(["bluetoothctl", "disconnect", d["address"]])
    threading.Thread(target=guard_loop, daemon=True).start()
    with lock:
        state["phone_ok"] = True
    while True:
        with lock:
            owner = settings["owner"]
            pairing = state["pairing"]
        devices = load_devices().get(owner, [])
        if pairing:
            time.sleep(2)                             # pinging during pairing would disturb it
            continue
        if not devices:
            text = "no device yet - press Add a device"
        else:
            text = "no device answered"
            for d in devices:
                if check_device(d["address"]):
                    text = d["name"] + " answered at " + time.strftime("%H:%M:%S")
                    with lock:
                        state["phone_seen"] = time.time()
                        state["seen"][d["address"]] = time.time()
                    break                             # one device is enough
        with lock:
            if text != "no device answered" or time.time() - state["phone_seen"] >= NEAR_SECONDS:
                state["phone_text"] = text
        time.sleep(PING_SECONDS)


# ---------- Combining the three ----------
def level_of(percent):
    for start, name in LEVELS:
        if percent >= start:
            return name
    return LEVELS[-1][1]


def current():
    # Returns the three bits and the combination code, e.g. (True, False, True, "101")
    now = time.time()
    if SIM:
        face, card, phone = sim["face"], sim["card"], sim["phone"]
    else:
        face = now - state["face_seen"] < FACE_HOLD_SECONDS
        card = state["card_in"]
        phone = now - state["phone_seen"] < NEAR_SECONDS
    code = "".join("1" if bit else "0" for bit in (face, card, phone))
    return face, card, phone, code


def status():
    now = time.time()
    with lock:
        face, card, phone, code = current()
        history = state["history"]
        if not history or history[0]["code"] != code:        # remember changes only
            history.insert(0, {"code": code, "at": time.strftime("%H:%M:%S")})
            del history[12:]
        percent, meaning = CONFIDENCE[code]
        owner = settings["owner"]
        devices = []
        for d in load_devices().get(owner, []):
            seen = state["seen"].get(d["address"])
            devices.append({"address": d["address"], "name": d["name"],
                            "seen_ago": None if seen is None else round(now - seen)})
        return {
            "sim": SIM, "code": code, "percent": percent, "level": level_of(percent), "meaning": meaning,
            "signals": [
                {"key": "face", "name": "Face", "on": face,
                 "text": "simulated" if SIM else state["face_text"], "works": SIM or state["face_ok"]},
                {"key": "card", "name": "RFID card", "on": card,
                 "text": "simulated" if SIM else state["card_text"], "works": SIM or state["card_ok"]},
                {"key": "phone", "name": "Bluetooth", "on": phone,
                 "text": "simulated" if SIM else state["phone_text"], "works": SIM or state["phone_ok"]},
            ],
            "table": [{"code": c, "percent": p, "level": level_of(p), "meaning": m} for c, (p, m) in CONFIDENCE.items()],
            "history": history, "owner": owner, "card": settings["card"], "linking": state["linking"],
            "face_photos": len(load_faces().get(owner, [])),
            "register": {"on": state["register"], "count": state["register_count"], "of": SAMPLES},
            "devices": devices, "max_devices": MAX_DEVICES,
            "guard": {"connected": state["connected"], "dropped": state["dropped"], "last_drop": state["last_drop"]},
            "pairing": {"on": state["pairing"], "seconds_left": max(0, round(state["pairing_until"] - now)),
                        "nearby": state["nearby"]},
            "pi_name": socket.gethostname(), "message": state["message"],
            "holds": {"face": FACE_HOLD_SECONDS, "phone": NEAR_SECONDS},
        }


# ---------- Web page ----------
PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Presence Confidence</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f5f7; color: #222; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  h2 { font-size: 15px; margin: 0 0 8px; }
  h3 { font-size: 14px; margin: 14px 0 6px; padding-top: 10px; border-top: 1px solid #eee; }
  .top { color: #555; margin: 0 0 14px; font-size: 14px; }
  .wrap { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); max-width: 1100px; }
  .card { background: #fff; border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  .signals { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .sig { border-radius: 8px; padding: 10px 8px; text-align: center; background: #eee; color: #555; }
  .sig.on { background: #1a8f3c; color: #fff; }
  .sig b { display: block; font-size: 30px; }
  .sig small { display: block; font-size: 12px; margin-top: 4px; overflow-wrap: anywhere; }
  .sig.broken { outline: 2px dashed #c62828; }
  .sig button { margin-top: 6px; }
  .code { font-family: monospace; font-size: 15px; white-space: nowrap; }
  th:first-child { white-space: nowrap; }
  .big { font-size: 44px; font-weight: 700; margin: 6px 0 0; }
  .bar { height: 12px; background: #eee; border-radius: 6px; overflow: hidden; margin: 8px 0; }
  .bar div { height: 100%; border-radius: 6px; transition: width .4s; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  td, th { text-align: left; padding: 6px 4px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
  th { color: #555; font-weight: 600; font-size: 13px; }
  tr.now td { background: #fff4c2; font-weight: 600; }
  .pill { display: inline-block; padding: 1px 8px; border-radius: 10px; color: #fff; font-size: 12px; white-space: nowrap; }
  input[type=text], button { font-size: 14px; padding: 5px 8px; border: 1px solid #ccc; border-radius: 5px; background: #fff; }
  input[type=text] { width: 100%; box-sizing: border-box; }
  button { cursor: pointer; margin: 4px 4px 0 0; } button:hover { background: #eee; }
  button:disabled { color: #aaa; cursor: default; }
  .row { display: flex; gap: 6px; } .row input { flex: 1; } .row button { margin: 0; }
  .device { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 5px 0;
            border-top: 1px solid #f0f0f0; font-size: 14px; }
  .device small { color: #777; display: block; font-family: monospace; }
  .device button { margin: 0; }
  .pairbox { background: #fff8e6; border: 1px solid #f0c36d; border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
  .pairbox ol { margin: 6px 0 8px 18px; padding: 0; font-size: 14px; }
  img { width: 100%; border-radius: 6px; background: #000; display: block; margin-top: 10px; }
  .small { color: #555; font-size: 13px; }
  .msg { background: #eef4ff; border-radius: 6px; padding: 6px 8px; font-size: 13px; margin-top: 10px; }
  .msg:empty { display: none; }
  .history span { display: inline-block; font-family: monospace; background: #f0f0f0; border-radius: 4px; padding: 2px 6px; margin: 2px; font-size: 13px; }
</style></head>
<body>
<h1>Presence Confidence</h1>
<p class="top" id="top"></p>
<div class="wrap">
  <div class="card">
    <h2>Signals <span class="small">(F R B)</span></h2>
    <div class="signals" id="signals"></div>
    <div class="small" style="margin-top:8px" id="holds"></div>
  </div>
  <div class="card">
    <h2>Confidence the owner is in the cabin</h2>
    <div class="code" id="code"></div>
    <div class="big" id="percent"></div>
    <div class="bar"><div id="bar"></div></div>
    <div id="level"></div>
    <p id="meaning" style="margin:8px 0 0"></p>
    <div class="small" style="margin-top:10px">Changes: <span class="history" id="history"></span></div>
  </div>
  <div class="card">
    <h2>Owner setup</h2>
    <div class="row"><input type="text" id="owner" placeholder="Owner's name, e.g. Dr. Rao">
      <button onclick="post('/owner?name=' + encodeURIComponent(document.getElementById('owner').value.trim()))">Save</button></div>

    <h3>Face</h3>
    <div class="small" id="face-info"></div>
    <button id="register" onclick="post('/face/register')">Register my face</button>
    <button id="face-delete" onclick="if (confirm('Delete the registered face?')) post('/face/delete')">Delete face</button>
    <div class="small">Only the owner in view, facing the camera. It takes 10 photos (a few seconds).</div>

    <h3>Bluetooth devices <span class="small" id="dev-count"></span></h3>
    <div id="devices"></div>
    <div class="small" id="guard" style="margin-top:6px"></div>
    <button id="add-device" onclick="post('/bt/start')">Add a device</button>
    <div id="pairing"></div>

    <h3>RFID card</h3>
    <span id="cardid" class="small"></span> <button id="link" onclick="post('/link')">Link my card</button>
    <div class="msg" id="message"></div>
  </div>
  <div class="card" id="picture-card">
    <h2>Last picture</h2>
    <img id="picture" alt="last picture">
  </div>
  <div class="card" style="grid-column: 1 / -1">
    <h2>All 8 combinations</h2>
    <table><thead><tr><th>F R B</th><th>Confidence</th><th>Meaning</th></tr></thead><tbody id="table"></tbody></table>
  </div>
</div>
<script>
const COLOURS = {"Very high": "#1a8f3c", "High": "#5aa832", "Medium": "#e0a100", "Low": "#e06a00", "Very low": "#c62828"};
const esc = t => String(t).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const q = encodeURIComponent;
let first = true, picture = 0;

async function post(url) {
  const r = await fetch(url, {method: "POST"});
  if (!r.ok) alert(await r.text());
  refresh();
}

function ago(seconds) {
  if (seconds === null) return "not seen yet";
  if (seconds < 60) return "seen " + seconds + " s ago";
  if (seconds < 3600) return "seen " + Math.round(seconds / 60) + " min ago";
  return "seen " + Math.round(seconds / 3600) + " h ago";
}

async function refresh() {
  let s;
  try { s = await (await fetch("/status.json")).json(); }
  catch (e) { document.getElementById("top").textContent = "Can't reach the Pi"; return; }

  document.getElementById("top").textContent = s.sim
    ? "Simulation: no hardware. Switch buttons change each signal; registering and pairing are pretended."
    : "Face, RFID card and Bluetooth together. Updates every second.";
  document.getElementById("signals").innerHTML = s.signals.map(g =>
    "<div class='sig" + (g.on ? " on" : "") + (g.works ? "" : " broken") + "'>" + esc(g.name) +
    "<b>" + (g.on ? 1 : 0) + "</b><small>" + esc(g.text) + "</small>" +
    (s.sim ? "<button onclick=\"post('/sim?signal=" + g.key + "')\">Switch</button>" : "") + "</div>").join("");
  document.getElementById("holds").textContent = "Face counts for " + s.holds.face + " s after it is seen, " +
    "Bluetooth for " + s.holds.phone + " s after a device answers, the card until it is tapped out.";

  const colour = COLOURS[s.level];
  document.getElementById("code").textContent = "F R B = " + s.code.split("").join(" ");
  document.getElementById("percent").textContent = s.percent + " %";
  document.getElementById("percent").style.color = colour;
  document.getElementById("bar").style.width = s.percent + "%";
  document.getElementById("bar").style.background = colour;
  document.getElementById("level").innerHTML = "<span class='pill' style='background:" + colour + "'>" + s.level + "</span>";
  document.getElementById("meaning").textContent = s.meaning;
  document.getElementById("history").innerHTML = s.history.map(h => "<span>" + h.code + " " + h.at + "</span>").join("");
  document.getElementById("table").innerHTML = s.table.map(r =>
    "<tr" + (r.code === s.code ? " class='now'" : "") + "><td class='code'>" + r.code.split("").join(" ") + "</td>" +
    "<td>" + r.percent + " % <span class='pill' style='background:" + COLOURS[r.level] + "'>" + r.level + "</span></td>" +
    "<td>" + esc(r.meaning) + "</td></tr>").join("");

  // Owner setup
  const noOwner = !s.owner;
  if (first) document.getElementById("owner").value = s.owner;
  document.getElementById("face-info").textContent = noOwner ? "Save the owner's name first." :
    s.register.on ? "Registering: " + s.register.count + " / " + s.register.of + " photos..." :
    s.face_photos ? "Registered: " + s.face_photos + " photos of " + s.owner + " (register again to add more)" :
    "No face registered yet.";
  document.getElementById("register").disabled = noOwner || s.register.on;
  document.getElementById("face-delete").disabled = !s.face_photos || s.register.on;

  document.getElementById("dev-count").textContent = "(" + s.devices.length + " / " + s.max_devices + ")";
  document.getElementById("devices").innerHTML = s.devices.length ? s.devices.map(d =>
    "<div class='device'><span>" + esc(d.name) + "<small>" + d.address + " - " + ago(d.seen_ago) + "</small></span>" +
    "<button data-a='" + d.address + "' data-n='" + esc(d.name) + "' onclick='if (confirm(\"Remove \" + this.dataset.n + \"?\")) " +
    "post(\"/bt/remove?address=\" + this.dataset.a)'>Remove</button></div>").join("")
    : "<div class='small'>No devices yet.</div>";
  const g = s.guard;
  document.getElementById("guard").textContent = "Only detected, never used: the Pi connects for each check " +
    "(about 1 s) and disconnects. Connected now: " + (g.connected.length ? g.connected.join(", ") + " (checking)" : "none") +
    ". Other connections dropped: " + g.dropped + (g.last_drop ? " (last: " + g.last_drop + ")" : "") + ".";
  document.getElementById("add-device").disabled = noOwner || s.pairing.on || s.devices.length >= s.max_devices;

  const p = s.pairing;
  document.getElementById("pairing").innerHTML = !p.on ? "" :
    "<div class='pairbox'><b>Adding a device</b> (" + p.seconds_left + " s left) " +
    "<button onclick=\"post('/bt/cancel')\">Cancel</button><ol>" +
    "<li>On the phone, open the <b>Bluetooth settings</b> screen and keep it open.</li>" +
    "<li>Press <b>Pair</b> next to it below, then accept on the phone. " +
    "<i>Or</i> choose <b>" + esc(s.pi_name) + "</b> in the phone's own list.</li></ol>" +
    (p.nearby.length ? p.nearby.map(d => "<div class='device'><span>" + esc(d.name) + "<small>" + d.address +
       "</small></span><button data-a='" + d.address + "' data-n='" + esc(d.name) +
       "' onclick='post(\"/bt/pair?address=\" + this.dataset.a + \"&name=\" + q(this.dataset.n))'>Pair</button></div>").join("")
     : "<div class='small'>Looking for visible devices...</div>") + "</div>";

  document.getElementById("cardid").textContent = s.linking ? "Tap the card now..." :
    (s.card ? "Linked: " + s.card : "No card linked");
  document.getElementById("message").textContent = s.message;
  if (first) {
    document.getElementById("picture-card").style.display = s.sim ? "none" : "";
    first = false;
  }
  if (!s.sim) {
    picture++;
    document.getElementById("picture").src = "/latest.jpg?n=" + picture;
  }
}

refresh();
setInterval(refresh, 1000);
</script>
</body></html>
"""


def handle_action(path, query):
    # Returns (ok, text)
    address = query.get("address", [""])[0].upper()
    with lock:
        owner = settings["owner"]
        if path == "/sim" and SIM and query.get("signal", [""])[0] in sim:
            key = query["signal"][0]
            sim[key] = not sim[key]
            return True, "ok"
        if path == "/owner":
            name = query.get("name", [""])[0].strip()[:60]
            if not name:
                return False, "Type the owner's name"
            settings["owner"] = name
            save_settings()
            state["message"] = "Owner: " + name + "."
            return True, "ok"
        if path.startswith(("/face/", "/bt/")) and not owner:
            return False, "Save the owner's name first"
        if path == "/face/register":
            if state["register"]:
                return False, "Already registering"
            if not SIM and not state["face_ok"]:
                return False, "The camera isn't working: " + state["face_text"]
            state.update(register=True, register_count=0, register_started=time.time(),
                         message="Registering " + owner + "'s face - look at the camera...")
            if SIM:
                threading.Thread(target=sim_register, daemon=True).start()
            return True, "ok"
        if path == "/face/delete":
            faces = load_faces()
            faces.pop(owner, None)
            save_faces(faces)
            state["message"] = "Deleted " + owner + "'s face."
            return True, "ok"
        if path == "/bt/start":
            if state["pairing"]:
                return False, "Already adding a device"
            if not SIM and not state["phone_ok"]:
                return False, "Bluetooth isn't working: " + state["phone_text"]
            if len(load_devices().get(owner, [])) >= MAX_DEVICES:
                return False, owner + " already has " + str(MAX_DEVICES) + " devices"
            state.update(pairing=True, pairing_until=time.time() + PAIR_SECONDS, nearby=[],
                         message="Adding a device for " + owner + "...")
            threading.Thread(target=pairing_window, daemon=True).start()
            return True, "ok"
        if path == "/bt/pair" and MAC.match(address) and state["pairing"]:
            name = query.get("name", [address])[0][:60]
            threading.Thread(target=pair_from_pi, args=(address, name), daemon=True).start()
            return True, "ok"
        if path == "/bt/cancel":
            state["pairing"] = False
            state["message"] = "Adding a device was cancelled."
            return True, "ok"
        if path == "/bt/remove" and MAC.match(address):
            devices = load_devices()
            devices[owner] = [d for d in devices.get(owner, []) if d["address"] != address]
            save_devices(devices)
            if not SIM:
                run_command(["bluetoothctl", "remove", address])          # forget the pairing too
            state["message"] = "Device removed."
            return True, "ok"
        if path == "/link":
            if SIM:
                return False, "No RFID reader in simulation"
            if not state["card_ok"]:
                return False, "The RFID reader isn't working: " + state["card_text"]
            state["linking"] = True
            state["message"] = "Tap the owner's card on the reader."
            return True, "ok"
    return False, "bad request"


class Handler(BaseHTTPRequestHandler):
    def send(self, body, content_type, code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send(PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/status.json":
            self.send(json.dumps(status()).encode(), "application/json")
        elif path == "/latest.jpg":
            with lock:
                jpeg = latest_jpeg
            if jpeg is None:
                self.send(b"no picture yet", "text/plain", 503)
            else:
                self.send(jpeg, "image/jpeg")
        else:
            self.send(b"not found", "text/plain", 404)

    def do_POST(self):
        url = urlparse(self.path)
        ok, text = handle_action(url.path, parse_qs(url.query))
        self.send(text.encode(), "text/plain", 200 if ok else 400)

    def log_message(self, *args):
        pass                                          # keep the terminal quiet


def my_address():
    # The IP address other devices on the network use to reach this Pi
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))                    # nothing is sent, this only picks the network
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def main():
    if not SIM:
        if sys.platform != "linux":
            sys.exit("Run this on the Raspberry Pi, or add --sim to try the page without hardware.")
        if os.geteuid() != 0:
            print("Note: not running with sudo, so the RC522 and l2ping may not work. Use: sudo python3 " +
                  os.path.basename(__file__))
        for loop in (face_loop, card_loop, phone_loop):     # each one says on the page if its part isn't working
            threading.Thread(target=loop, daemon=True).start()

    server = ThreadingHTTPServer(("", PORT), Handler)
    print("Presence confidence page" + (" (simulation)" if SIM else "") + ":")
    print("  http://" + my_address() + ":" + str(PORT))
    print("  http://" + socket.gethostname() + ".local:" + str(PORT))
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
