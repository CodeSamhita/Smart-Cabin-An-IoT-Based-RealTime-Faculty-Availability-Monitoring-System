# What the threads and the web page share. Always change it inside "with lock:".
import threading
import time

lock = threading.Lock()

# The registration being filled in right now (nothing is saved until "Save")
draft = {}

# What each part is doing, for the page
state = {
    "face_ok": False, "face_text": "starting...", "face_capturing": False, "face_started": 0,
    "card_ok": False, "card_text": "starting...", "card_waiting": False, "card_started": 0,
    "phone_ok": False, "phone_text": "starting...", "pairing": False, "pairing_until": 0, "nearby": [],
    "checking": "", "dropped": 0, "message": "",
}
latest_jpeg = None                 # last camera picture, shown during the face step


def new_draft(name=""):
    return {"active": bool(name), "name": name, "step": "name",
            "face": [],            # list of 128-number lists, one per photo
            "card": "",            # card UID, e.g. "04 A2 1B 3C 5D 6E 7F"
            "devices": []}         # [{"address": "AA:BB:..", "name": "Pixel 7"}]


def say(text):
    # Message shown on the page (call with the lock held)
    state["message"] = time.strftime("%H:%M:%S") + "  " + text


draft.update(new_draft())
