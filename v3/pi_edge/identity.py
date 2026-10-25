# Smart Cabin edge device - who this device is.
#   serial()  : the Pi's hardware serial number (never changes, not even with a new SD card) = its identity
#   model()   : "Raspberry Pi Zero 2 W Rev 1.0", "Raspberry Pi 4 Model B ..." or "Laptop (simulation)"
#   load() / save() : data/device.json = the device number and secret key from the server, and the
#                     fingerprint of the server's certificate (remembered the first time)

import json
import os
import secrets
import threading
import time

import settings

DEVICE_FILE = os.path.join(settings.DATA_FOLDER, "device.json")
save_lock = threading.Lock()


def serial():
    if settings.SIMULATE:
        if settings.SIM_SERIAL:
            return settings.SIM_SERIAL
        saved = load().get("sim_serial")
        if not saved:
            saved = "SIM-" + secrets.token_hex(4).upper()
            save({"sim_serial": saved})
        return saved
    for path in ("/sys/firmware/devicetree/base/serial-number", "/proc/device-tree/serial-number"):
        try:
            with open(path) as f:
                value = f.read().strip("\x00 \n")
            if value:
                return value
        except OSError:
            pass
    with open("/proc/cpuinfo") as f:                     # older systems
        for line in f:
            if line.startswith("Serial"):
                return line.split(":")[1].strip()
    raise RuntimeError("could not read the Pi's serial number")


def model():
    if settings.SIMULATE:
        return settings.COMPUTER + " computer (no Pi hardware)"
    try:
        with open("/proc/device-tree/model") as f:
            return f.read().strip("\x00 \n")
    except OSError:
        return "Raspberry Pi (unknown model)"


def is_pi4_or_newer():
    text = model()
    return "Pi 4" in text or "Pi 5" in text


def load():
    try:
        with open(DEVICE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def replace_file(temporary, target):
    # Swap the new file in. Windows can lock a just-written file for a moment (e.g. a virus scan): try again.
    for _ in range(30):
        try:
            os.replace(temporary, target)
            return
        except PermissionError:
            time.sleep(0.1)
    raise RuntimeError("could not save " + target + " - it stays locked by another program")


def save(values):
    # Adds / changes keys in device.json. Written to a temporary file first, then swapped in. One save at a time.
    with save_lock:
        data = load()
        data.update(values)
        os.makedirs(settings.DATA_FOLDER, exist_ok=True)
        temporary = DEVICE_FILE + ".tmp"
        with open(temporary, "w") as f:
            json.dump(data, f, indent=1)
        replace_file(temporary, DEVICE_FILE)
        if not settings.SIMULATE:
            os.chmod(DEVICE_FILE, 0o600)                 # the key: readable by root only
