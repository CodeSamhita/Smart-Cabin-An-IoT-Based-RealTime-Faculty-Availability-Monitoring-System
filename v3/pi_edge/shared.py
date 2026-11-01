# Smart Cabin edge device - what every part shares: one dictionary "state" and one lock.
#   set_part()   : a part (camera, rfid, led, ...) reports OK or PROBLEM with a reason
#   error()      : logs an error and keeps it as "last error" (sent to the server, shown on the page)
#   snapshot()   : a copy of the state, safe to read while other threads change it

import copy
import threading
import time

from logbook import log

lock = threading.RLock()
changed = threading.Event()        # set when something changed, so the report goes out straight away

state = {
    "parts": {},                   # name -> {"ok": True/False, "message": "..."}
    "last_error": "",
    "device": "", "location": "", "server_ok": False, "server_message": "not contacted yet",
    "person": None,                # {"id", "name", "designation"} registered at this device
    "headcount": 0, "headcount_raw": 0, "dark": False, "brightness": 0,
    "face_seen_at": 0.0, "face_score": -1.0, "last_picture_at": 0.0, "picture_ms": 0,
    "in_cabin": False, "card_in": False, "status": "not_available", "confidence": 2,
    "led": "off", "vision_paused": "", "card_warning": "", "presence_reason": "", "page_https": False,
    "setup_allowed": False, "setup_message": "", "registered_at": "", "known_tap_at": 0.0,
    "deactivated": "",             # the server's message when this device was deactivated (replaced / broken)
}


def set_part(name, ok, message="", present=True):
    # present=False: this computer simply has no such hardware (e.g. Windows) - shown as NOT PRESENT, not as an error
    with lock:
        old = state["parts"].get(name)
        state["parts"][name] = {"ok": bool(ok) and present, "message": str(message)[:200], "present": present}
    if old is None or old["ok"] != (bool(ok) and present) or old.get("present", True) != present:
        if not present:
            log.info("part %s: NOT PRESENT on this computer - %s", name, message)
        else:
            (log.info if ok else log.error)("part %s: %s %s", name, "OK" if ok else "PROBLEM", message)


def error(where, problem):
    text = time.strftime("%H:%M:%S") + " " + where + ": " + str(problem)
    with lock:
        state["last_error"] = text[:300]
    log.error("%s: %s", where, problem)


def update(**values):
    with lock:
        state.update(values)


def get(name):
    with lock:
        return state[name]


def snapshot():
    with lock:
        return copy.deepcopy(state)
