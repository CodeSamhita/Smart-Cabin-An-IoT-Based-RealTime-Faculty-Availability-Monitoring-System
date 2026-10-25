# The registration steps: name -> face -> card -> phone -> review -> save.
# Face, card and phone can each be skipped, but at least one must be recorded before Save.
# Every function returns (ok, text); a not-ok text is shown to the user.
import threading
import time

import bluetooth
import config
import rfid
import shared
import storage

STEPS = ["name", "face", "card", "phone", "review"]


def stop_activity():
    # Called with the lock held: stop taking photos, waiting for a card, or pairing
    shared.state["face_capturing"] = False
    shared.state["card_waiting"] = False
    shared.state["pairing"] = False


def go(step):
    # Called with the lock held
    stop_activity()
    shared.draft["step"] = step


def start(name):
    name = name.strip()[:60]
    if not name:
        return False, "Type the user's name"
    if storage.name_taken(name):
        return False, name + " is already registered"
    with shared.lock:
        if shared.draft["active"]:
            return False, "Finish or cancel the registration of " + shared.draft["name"] + " first"
        shared.draft.update(shared.new_draft(name))
        go("face")
        shared.say("Registering " + name + ". Step 1: face.")
    return True, "ok"


def next_step(skip):
    # skip=True forgets what this step recorded (devices are unpaired too), then moves on
    with shared.lock:
        step = shared.draft["step"]
        if not shared.draft["active"] or step not in ("face", "card", "phone"):
            return False, "Nothing to skip here"
        if skip:
            if step == "face":
                shared.draft["face"] = []
            elif step == "card":
                shared.draft["card"] = ""
            else:
                for d in shared.draft["devices"]:
                    bluetooth.forget(d["address"])
                shared.draft["devices"] = []
        go(STEPS[STEPS.index(step) + 1])
    return True, "ok"


def back():
    with shared.lock:
        step = shared.draft["step"]
        if not shared.draft["active"] or step in ("name", "face"):
            return False, "Can't go back from here"
        go(STEPS[STEPS.index(step) - 1])
    return True, "ok"


def face_start():
    with shared.lock:
        if shared.draft["step"] != "face":
            return False, "Not on the face step"
        if not shared.state["face_ok"]:
            return False, "The camera isn't working: " + shared.state["face_text"]
        shared.draft["face"] = []
        shared.state.update(face_capturing=True, face_started=time.time(), face_text="photo 0 / " + str(config.FACE_SAMPLES))
        shared.say("Look at the camera. Only " + shared.draft["name"] + " in view.")
    return True, "ok"


def card_start():
    with shared.lock:
        if shared.draft["step"] != "card":
            return False, "Not on the card step"
        if not shared.state["card_ok"]:
            return False, "The RFID reader isn't working: " + shared.state["card_text"]
        shared.draft["card"] = ""
        shared.state.update(card_waiting=True, card_started=time.time(), card_text="waiting for a tap...")
        shared.say("Tap the card on the reader.")
    return True, "ok"


def phone_start():
    with shared.lock:
        if shared.draft["step"] != "phone":
            return False, "Not on the Bluetooth step"
        if not shared.state["phone_ok"]:
            return False, "Bluetooth isn't working: " + shared.state["phone_text"]
        if shared.state["pairing"]:
            return False, "Already adding a device"
        if len(shared.draft["devices"]) >= config.MAX_DEVICES:
            return False, "Already " + str(config.MAX_DEVICES) + " devices"
        shared.state.update(pairing=True, pairing_until=time.time() + config.PAIR_SECONDS, nearby=[])
        shared.say("Adding a device for " + shared.draft["name"] + "...")
    threading.Thread(target=bluetooth.pairing_window, daemon=True).start()
    return True, "ok"


def phone_pair(address, name):
    if not bluetooth.MAC.match(address) or not shared.state["pairing"]:
        return False, "Press Add a device first"
    threading.Thread(target=bluetooth.pair_from_pi, args=(address, name[:60] or address), daemon=True).start()
    return True, "ok"


def phone_remove(address):
    with shared.lock:
        shared.draft["devices"] = [d for d in shared.draft["devices"] if d["address"] != address]
        bluetooth.forget(address)
        shared.say("Device removed from this registration.")
    return True, "ok"


def save():
    with shared.lock:
        draft = shared.draft
        if not draft["active"] or draft["step"] != "review":
            return False, "Go through the steps first"
        if not (draft["face"] or draft["card"] or draft["devices"]):
            return False, "Register at least one: face, card or Bluetooth device"
        storage.add_user(draft["name"], draft["card"], draft["face"], draft["devices"])
        shared.say("Saved " + draft["name"] + ".")
        shared.draft.update(shared.new_draft())
    return True, "ok"


def cancel():
    with shared.lock:
        stop_activity()
        for d in shared.draft["devices"]:
            bluetooth.forget(d["address"])            # nothing of this registration stays paired
        name = shared.draft["name"]
        shared.draft.update(shared.new_draft())
        shared.say("Registration of " + name + " cancelled. Nothing was saved.")
    return True, "ok"


def delete(user_id):
    with shared.lock:
        for address in storage.delete_user(user_id):
            bluetooth.forget(address)
        shared.say("User deleted.")
    return True, "ok"


def sim_tap():
    if not config.SIM:
        return False, "Only in --sim"
    rfid.sim_tap()
    return True, "ok"
