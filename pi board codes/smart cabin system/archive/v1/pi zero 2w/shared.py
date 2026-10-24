# Smart Cabin cabin device - the state every thread shares. Always change it inside "with lock:".

import threading
import time

import config

lock = threading.RLock()

state = {
    # what the sensors say (written by the sensor threads)
    "headcount": 0,               # steady people count from the camera
    "face_seen_at": 0.0,          # last time the owner's face was matched
    "face_streak": 0,             # owner matched in this many pictures in a row
    "phone_seen_at": 0.0,         # last time one of the owner's phones answered
    "phone_near": False,
    "card_login_at": 0.0,         # last card login tap
    "logged_out_at": 0.0,         # last card logout tap
    "fast_until": 0.0,            # take pictures quickly until then

    # what presence.py decided
    "faculty_in": False,

    # from / to the server
    "connected": False,           # has a device token
    "pairing_server": "",         # while not connected: the laptop found by its broadcast (pairing.py)
    "server_ok": False,           # the last report reached the server
    "status": "",                 # green / yellow / red / grey, as the server decided
    "reason": "",
    "until": "",
    "owner": None,                # {"id": .., "name": ..}
    "cabin": "",
    "events": [],                 # events waiting to be sent: [{"kind", "detail", "time"}]
    "button": "",                 # hardware button waiting to be sent
    "report_now": False,          # send a report straight away

    # setup page
    "enrol_until": 0.0,           # the owner logged in on this page: setup allowed until then
    "enrol_name": "",
    "register_face": False,       # take face photos now
    "face_progress": 0,
    "link_card": False,           # the next card tapped gets linked to the owner
    "pairing": False,
    "nearby": [],                 # Bluetooth devices seen during pairing
    "message": "starting...",
    "last_card": "",
    "last_jpeg": None,            # last picture with boxes (only shown on this device's page, while logged in)
    "last_boxes": [],             # people boxes of the last picture (for "ignore what is seen now")
    "last_size": (1, 1),
    "led": "off",

    # health of each part: name -> "ok" / "error: ..." / "off"
    "sensors": {},
}


def add_event(kind, detail=""):
    with lock:
        state["events"].append({"kind": kind, "detail": detail, "time": time.time()})
        state["report_now"] = True
    print(time.strftime("%H:%M:%S"), kind, detail)


def set_sensor(name, text):
    with lock:
        if state["sensors"].get(name) != text:
            state["sensors"][name] = text
            print("  " + name + ": " + text)


def set_message(text):
    with lock:
        state["message"] = text
    print(text)


def go_fast():
    # Something happened: take pictures quickly for a while
    with lock:
        state["fast_until"] = time.time() + config.FAST_SECONDS
