# Smart Cabin cabin device - connects to the laptop by itself, no code typing (BUILD_PLAN.md step 9).
#
#   1. listen for the laptop's UDP broadcast on port 50505: it says where the server is
#      (if nothing is heard, try SERVER_URL from config.py)
#   2. say hello to that server every 3 s with this device's id, name, model and a 4-digit PIN
#   3. the admin presses "Add a new device" on the Cabins page, checks the PIN and picks the cabin
#   4. the next hello answers "approved" with this device's token: saved in data/device.json -> connected
#
# The PIN is shown on this device's page and in the terminal, so the admin can check it is the right device.

import json
import secrets
import socket
import time

import config
import server_link
import shared
import storage

BEACON_PORT = 50505
PIN = str(secrets.randbelow(10000)).zfill(4)        # a new PIN at every start


def device_id():
    # On a Pi: its hardware serial number (never changes, even after a reinstall or a new SD card),
    # so the cabin it is linked to always knows it. In simulation: a random id made once and kept.
    for path in ("/sys/firmware/devicetree/base/serial-number", "/proc/device-tree/serial-number"):
        try:
            with open(path) as f:
                serial = f.read().strip("\x00 \n").lower()
            if serial:
                return serial
        except OSError:
            pass
    saved = storage.load("device_id.json", {})
    if not saved.get("id"):
        saved = {"id": secrets.token_hex(8)}
        storage.save("device_id.json", saved)
    return saved["id"]


def board_model():
    if config.ON_PI:
        with open("/proc/device-tree/model") as f:
            return f.read().rstrip("\x00")
    return "Laptop (simulation)"


def hear_server(seconds):
    # Waits up to `seconds` for the laptop's broadcast. Returns the server address, or "".
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", BEACON_PORT))
        except OSError:
            time.sleep(seconds)                      # port busy: just try the configured address
            return ""
        s.settimeout(seconds)
        try:
            data, sender = s.recvfrom(1024)
            message = json.loads(data.decode())
            if message.get("smartcabin") == "server" and str(message.get("url", "")).startswith("http"):
                return message["url"]
        except (socket.timeout, OSError, ValueError):
            pass
    return ""


def pairing_loop():
    # Thread: runs until this device is connected (and starts again if it is ever disconnected)
    name = socket.gethostname()
    model = board_model()
    told = False
    while True:
        with shared.lock:
            connected = shared.state["connected"]
        if connected:
            told = False
            time.sleep(5)
            continue

        url = hear_server(3) or server_link.server_url()
        if not told:
            shared.set_message("Waiting to be added: on the laptop open Cabins -> Add a new device -> pick '" + name +
                               "' with PIN " + PIN + ". (If this device is already linked to a cabin, it connects by itself.)")
            print("   PIN for the admin page:", PIN, "   device:", name, "   ID (for the cabin's 'Linked device'):", device_id())
            told = True
        ok, answer = server_link.call("POST", "/api/device/hello",
                                      {"device_id": device_id(), "name": name, "model": model, "pin": PIN}, base=url)
        with shared.lock:
            shared.state["pairing_server"] = url if ok else ""
        if ok and answer.get("status") == "approved":
            storage.save("device.json", {"server": url, "token": answer["token"], "cabin": answer["cabin"]})
            with shared.lock:
                shared.state["connected"] = True
                shared.state["cabin"] = answer["cabin"]
            import actions                           # here, not at the top: actions imports a lot
            actions.sync_config()
            shared.set_message("Connected: this device is the cabin " + answer["cabin"] + ".")
            shared.add_event("device", "connected automatically (device ID linked to the cabin)")
        time.sleep(3)
