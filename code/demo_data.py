# Fake statuses so the web page can be shown without a camera.
# Later, the real camera + status logic will make the same kind of dictionary.

import random
import time

import people


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def make_status(state, reason="", expected_back="", people_count=0, evidence=None):
    # One person's status, in the shape the web page expects
    return {
        "status": state,
        "reason": reason,
        "expected_back": expected_back,
        "people_count": people_count,
        "evidence": evidence or [],
        "last_checked": now_text(),
    }


def random_status(person, timetable):
    # If the timetable says they are in class now, show that. Otherwise pick a random status.
    row = people.current_class(person["id"], timetable)
    if row:
        return make_status("red", row["activity"], "around " + row["end"], 0,
                           ["Timetable: " + row["activity"] + " " + row["start"] + " - " + row["end"],
                            "Camera: cabin empty"])

    # Mostly available, sometimes busy or away, rarely unknown
    state = random.choice(["green"] * 5 + ["yellow"] + ["red"] * 2 + ["grey"])

    if state == "green":
        return make_status("green", "", "", 1,
                           ["Camera: person seen, nobody else in the cabin", "Timetable: free slot"])
    if state == "yellow":
        return make_status("yellow", "", "", 3,
                           ["Camera: person seen with 2 visitors", "Timetable: free slot"])
    if state == "red":
        return make_status("red", "In a meeting", "in about 30 minutes", 0,
                           ["Camera: cabin empty", "Timetable: free slot, so reason is a guess"])
    return make_status("grey", "Camera could not confirm", "", 0,
                       ["Camera: no usable snapshot", "Showing time of last good check"])


def sample_sensors():
    # state can be: active, offline, planned, optional
    return [
        {"name": "Camera", "state": "active", "note": "Laptop webcam (snapshots only)"},
        {"name": "Timetable", "state": "active", "note": "From data/timetable.csv"},
        {"name": "Face recognition", "state": "planned", "note": "Only enrolled staff are matched"},
        {"name": "Hardware buttons", "state": "planned", "note": "Available / Busy / Back soon at the desk or door"},
        {"name": "RFID card tap", "state": "planned", "note": "Quick login at the door"},
        {"name": "Fingerprint", "state": "planned", "note": "Optional biometric check"},
        {"name": "BLE tag", "state": "planned", "note": "Hint only, never decides alone"},
        {"name": "Thermal liveness", "state": "optional", "note": "Stops photo spoofing"},
    ]
