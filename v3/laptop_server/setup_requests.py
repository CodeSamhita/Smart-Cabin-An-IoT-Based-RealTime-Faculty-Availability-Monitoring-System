# Smart Cabin laptop server - registration requests from the devices (setup_requests.csv).
# A faculty member registers at a device without waiting for the admin: name, face, card, cabin.
#   submit()  : the device sends the registration. The server checks it against its records: the name is in the
#               people list, nobody is registered at this device and the person is not registered at another one
#               -> registered at once, after the person confirmed the details shown (name, school, cabin ...).
#               Otherwise (registered elsewhere, "Replace my old device" ticked, or "these details are wrong" with a
#               note) it waits here as "pending" for the admin. The cabin is never typed: see cabin_for().
#   decide()  : the admin approves (registered now; a device the person had before is deactivated) or rejects
#               a pending request
#   pending(), latest_for_device()

import time

import csv_store
import devices
import logbook
import people
import registrations
import security
from security import UserError

COLUMNS = ["id", "time", "device", "person_id", "name", "cabin", "card_hash", "face_photos", "state", "reason", "decided"]


def all_requests():
    return csv_store.read("setup_requests.csv")


def latest_for_device(device):
    rows = [r for r in all_requests() if r["device"] == device]
    return rows[-1] if rows else None


def pending():
    return [r for r in all_requests() if r["state"] == "pending"]


def cabin_for(device_row, person):
    # The cabin comes from the server, never typed at the device: the device's location (set by the admin), else the
    # person's cabin in people.csv, else where they are registered now
    if device_row["location"]:
        return device_row["location"]
    if person.get("cabin"):
        return person["cabin"]
    elsewhere = registrations.current_for_person(person["id"])
    return elsewhere["location"] if elsewhere else ""


def register_now(device_row, person_id, card_hash, face_photos, cabin):
    # Links the person to the device; the cabin becomes the device's location if it has none yet
    location = device_row["location"]
    if not location and cabin:
        devices.set_location(device_row["device"], cabin)
        location = " ".join(cabin.split())
    return registrations.register(device_row["device"], location, person_id, "", face_photos, card_hash=card_hash)


def submit(device_row, person_id, card_id, face_photos, replace=False, update_note=""):
    # Returns (state, message): state "registered" or "pending". Raises UserError for something to fix now.
    # replace: the person ticked "Replace my old device": the admin confirms it (approving deactivates the old device).
    # update_note: the person said the details shown are wrong and what to change: the admin updates them, then approves.
    device = device_row["device"]
    current = registrations.current_for_device(device)
    if current:
        raise UserError(current["name"] + " is already registered at this device. The admin must remove them first.")
    person = people.get(person_id)
    if person is None:
        raise UserError("Person " + str(person_id) + " is not in the university list.")
    face_photos = int(face_photos or 0)
    if not card_id and face_photos <= 0:
        raise UserError("Register at least the face or a card.")
    cabin = cabin_for(device_row, person)
    card_hash = security.sha256(str(card_id).upper()) if card_id else ""
    update_note = " ".join(str(update_note or "").split())[:200]

    elsewhere = registrations.current_for_person(person_id)
    if not elsewhere and not update_note:                 # the records agree and the person confirmed them
        register_now(device_row, person_id, card_hash, face_photos, cabin)
        logbook.event("registered", person["name"] + " registered at " + device + " (details confirmed at the device)",
                      device, person_id)
        return "registered", person["name"] + " is registered at " + device + "."
    if update_note:
        reason = "asks to update the details: " + update_note
    else:
        reason = ("wants to replace " if replace else "already registered at ") + elsewhere["device"] + \
                 " (" + (elsewhere["location"] or "no location") + ")"

    with csv_store.lock:
        rows = all_requests()
        for r in rows:
            if r["device"] == device and r["state"] == "pending":
                r["state"] = "replaced"                     # a newer request from the same device wins
        rows.append({"id": security.new_token()[:10], "time": logbook.now_text(), "device": device,
                     "person_id": person_id, "name": person["name"], "cabin": cabin, "card_hash": card_hash,
                     "face_photos": face_photos, "state": "pending", "reason": reason, "decided": ""})
        csv_store.write("setup_requests.csv", rows, COLUMNS)
    logbook.event("request", person["name"] + " at " + device + " waits for the admin: " + reason, device, person_id)
    return "pending", "Sent. It waits for the admin's approval (" + reason + ")."


def decide(request_id, approve):
    with csv_store.lock:
        rows = all_requests()
        request = next((r for r in rows if r["id"] == request_id), None)
        if request is None or request["state"] != "pending":
            raise UserError("That request is no longer waiting.")
        device_row = devices.find(devices.all_devices(), "device", request["device"])
        if approve:
            if device_row is None:
                raise UserError("Device " + request["device"] + " is not known any more.")
            current = registrations.current_for_device(request["device"])
            if current:
                raise UserError(current["name"] + " is already registered at " + request["device"] + ". Remove them first.")
            elsewhere = registrations.current_for_person(request["person_id"])
            if elsewhere:                                 # approving = the new device replaces the old one
                devices.deactivate(elsewhere["device"], "by the admin, replaced by " + request["device"])
            person = people.get(request["person_id"]) or {"id": request["person_id"]}
            fresh = devices.find(devices.all_devices(), "device", request["device"])       # the admin may have fixed it
            register_now(fresh, request["person_id"], request["card_hash"], request["face_photos"],
                         cabin_for(fresh, person) or request["cabin"])
        request["state"] = "approved" if approve else "rejected"
        request["decided"] = logbook.now_text()
        csv_store.write("setup_requests.csv", rows, COLUMNS)
    logbook.event("request", request["name"] + " at " + request["device"] + ": " + request["state"] + " by the admin",
                  request["device"], request["person_id"])
    return request["name"] + (" is registered at " if approve else " was not registered at ") + request["device"] + "."
