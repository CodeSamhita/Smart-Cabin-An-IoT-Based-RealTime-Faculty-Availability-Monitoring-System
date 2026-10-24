# Smart Cabin cabin device - what the setup page can do. Each function returns (ok, message).
# Setup needs the owner (or admin) to log in with their server username and password first; the login
# gives this browser a page token, and setup stays open for 10 minutes (same as the server).

import secrets
import threading
import time

import bluetooth
import buttons
import config
import faces
import leds
import people
import presence
import server_link
import shared
import storage

page_token = ""                # the logged-in browser's token (one at a time)


def logged_in(token):
    with shared.lock:
        return bool(page_token) and token == page_token and time.time() < shared.state["enrol_until"]


# ---------- Connect this device to a cabin ----------
def connect(code, server):
    # The result is also kept as the page message and printed in the terminal, so it is never missed
    shared.set_message("Connecting to " + (server.strip() or server_link.server_url()) + " with code " + code.strip() + " ...")
    ok, answer = server_link.claim(code.strip(), server.strip() or None)
    if not ok:
        message = "Connect failed: " + answer.get("detail", "no answer")
        shared.set_message(message)
        return False, message
    with shared.lock:
        shared.state["connected"] = True
        shared.state["cabin"] = answer["cabin"]
    sync_config()
    message = "Connected to the cabin " + answer["cabin"] + "."
    shared.set_message(message)
    return True, message


def sync_config():
    # Owner, cards and phones from the server; kept in data/cache.json for when the laptop is off
    ok, cfg = server_link.get_config()
    if not ok:
        return False
    storage.save("cache.json", cfg)
    owner = cfg.get("owner")
    if owner and faces.forget_if_new_owner(owner["id"]):
        shared.set_message("New cabin owner: the old face data was deleted.")
    bluetooth.forget_removed([p["address"] for p in cfg.get("phones", [])])
    with shared.lock:
        shared.state["owner"] = owner
        shared.state["cabin"] = cfg.get("cabin", "")
    return True


# ---------- Setup login ----------
def login(username, password):
    global page_token
    ok, answer = server_link.enrol(username, password)
    if not ok:
        return False, answer.get("detail", "failed"), ""
    page_token = secrets.token_urlsafe(24)
    with shared.lock:
        shared.state["enrol_until"] = time.time() + 10 * 60
        shared.state["enrol_name"] = answer["name"]
    sync_config()
    return True, "Hello " + answer["name"] + ". Setup is open for 10 minutes.", page_token


def logout():
    global page_token
    page_token = ""
    server_link.end_enrol()
    with shared.lock:
        shared.state.update(enrol_until=0, enrol_name="", register_face=False, link_card=False, pairing=False)
    return True, "Logged out."


# ---------- Face ----------
def start_face():
    with shared.lock:
        if not shared.state["owner"]:
            return False, "No owner for this cabin yet (admin page, Cabins)."
        shared.state["register_face"] = True
        shared.state["face_progress"] = 0
    shared.go_fast()
    return True, "Look at the camera, alone, and turn your head a little. Taking " + str(config.FACE_SAMPLES) + " photos..."


def delete_face():
    storage.delete("faces.json")
    shared.add_event("face_deleted")
    return True, "Your face data was deleted from this device."


# ---------- Card ----------
def start_card_link():
    with shared.lock:
        shared.state["link_card"] = True
    return True, "Tap your card on the reader now."


def card_tapped(uid):
    # Called by the RFID thread (and the simulation button) for every tap
    with shared.lock:
        linking = shared.state["link_card"]
        shared.state["last_card"] = uid
    if linking:
        ok, answer = server_link.link_card(uid)
        with shared.lock:
            shared.state["link_card"] = False
        sync_config()
        shared.set_message("Card " + uid + " linked." if ok else "Card not linked: " + answer.get("detail", ""))
        threading.Thread(target=leds.flash, args=("white" if ok else "purple",), daemon=True).start()
        return
    if uid in storage.load("cache.json", {}).get("cards", []):
        action = presence.card_tap()
        shared.set_message("Card: " + ("welcome in" if action == "login" else "logged out") + ".")
        threading.Thread(target=leds.flash, args=("white",), daemon=True).start()
    else:
        shared.add_event("card_unknown", uid)
        shared.set_message("Unknown card " + uid + ". Log in on this page and press 'Link my card' to link it.")
        threading.Thread(target=leds.flash, args=("purple", 1.0), daemon=True).start()


# ---------- Phones ----------
def phone_paired(address, name):
    bluetooth.keep_identity_only(address)
    ok, answer = server_link.add_phone(address, name)
    with shared.lock:
        shared.state["pairing"] = False
    sync_config()
    shared.set_message("Saved " + name + "." if ok else "Not saved: " + answer.get("detail", ""))


def start_pairing():
    with shared.lock:
        if shared.state["pairing"]:
            return False, "Already pairing."
        shared.state["pairing"] = True
        shared.state["nearby"] = []
    threading.Thread(target=bluetooth.pairing_window, args=(phone_paired,), daemon=True).start()
    return True, "On your phone, open the Bluetooth settings screen and keep it open."


def pair_device(address, name):
    shared.set_message("Asking " + name + " to pair - accept on the device...")
    if bluetooth.pair_from_pi(address):
        phone_paired(address, name)
        return True, "Paired " + name + "."
    return False, "Pairing with " + name + " failed or wasn't accepted. Try again."


# ---------- Photos / posters on the wall ----------
def zones_from_picture():
    with shared.lock:
        labelled, size = shared.state.get("last_boxes", []), shared.state.get("last_size", (1, 1))
    total = people.zones_from_boxes(labelled, size[0], size[1])
    return True, str(total) + " ignore zone(s). Use this only when the room is empty."


def clear_zones():
    storage.delete("zones.json")
    return True, "Ignore zones cleared."


# ---------- Buttons on the page / simulation ----------
def press_button(name):
    if name not in config.BUTTON_PINS:
        return False, "Unknown button."
    buttons.press(name)
    return True, "Sent."


def sim_phone(near):
    addresses = [p["address"] for p in storage.load("cache.json", {}).get("phones", [])]
    bluetooth.sim_near.clear()
    if near:
        bluetooth.sim_near.update(addresses)
    return True, "Simulated phone " + ("near" if near else "away") + " (" + str(len(addresses)) + " linked)."
