# Smart Cabin laptop server - who is registered at which device (registrations.csv).
# One person per device. A row with an empty "to_time" is the current registration; older rows stay as
# history, so a person who moves cabin keeps their old location in the file.
#   register()   : a person registered at a device (closes their old registration and the device's old one)
#   unregister() : nobody at this device any more
#   current_for_device(), current_for_person()

import csv_store
import logbook
import people
import security
from security import UserError

COLUMNS = ["person_id", "name", "device", "location", "card_hash", "face_photos", "from_time", "to_time"]


def current_for_device(device):
    for row in csv_store.read("registrations.csv"):
        if row["device"] == device and not row["to_time"]:
            return row
    return None


def current_for_person(person_id):
    for row in csv_store.read("registrations.csv"):
        if row["person_id"] == person_id and not row["to_time"]:
            return row
    return None


def register(device, location, person_id, card_id, face_photos):
    person = people.get(person_id)
    if person is None:
        raise UserError("Person " + str(person_id) + " is not in the university list.")
    face_photos = int(face_photos or 0)
    if not card_id and face_photos <= 0:
        raise UserError("Register at least the face or a card.")
    card_hash = security.sha256(str(card_id).upper()) if card_id else ""
    now = logbook.now_text()
    with csv_store.lock:
        rows = csv_store.read("registrations.csv")
        for row in rows:
            if card_hash and card_hash in row["card_hash"].split(";") and not row["to_time"] and row["person_id"] != person_id:
                raise UserError("This card is already registered to " + row["name"] + ".")
        for row in rows:
            if not row["to_time"] and (row["device"] == device or row["person_id"] == person_id):
                row["to_time"] = now                    # keep the old row as history
                if row["person_id"] == person_id and row["device"] != device:
                    logbook.event("moved", person["name"] + " moved from " + row["location"] + " to " + location,
                                  device, person_id)
        rows.append({"person_id": person_id, "name": person["name"], "device": device, "location": location,
                     "card_hash": card_hash, "face_photos": face_photos, "from_time": now, "to_time": ""})
        csv_store.write("registrations.csv", rows, COLUMNS)
    logbook.event("registered", person["name"] + " at " + device + " (" + (location or "location not set") + "), face photos: "
                  + str(face_photos) + ", card: " + ("yes" if card_id else "no"), device, person_id)
    return person


def update_credentials(device, person_id, card_ids, face_photos):
    # The person at this device added / deleted a face set or a card: keep the card hashes (";"-separated) and
    # the number of face photos. A card already linked to someone else is refused.
    hashes = [security.sha256(str(c).upper()) for c in card_ids if c]
    with csv_store.lock:
        rows = csv_store.read("registrations.csv")
        mine = None
        for row in rows:
            if row["to_time"]:
                continue
            if row["device"] == device and row["person_id"] == person_id:
                mine = row
            elif any(h in row["card_hash"].split(";") for h in hashes):
                raise UserError("One of these cards is already registered to " + row["name"] + ".")
        if mine is None:
            raise UserError("This person is not registered at this device on the server.")
        mine["card_hash"] = ";".join(hashes)
        mine["face_photos"] = int(face_photos or 0)
        csv_store.write("registrations.csv", rows, COLUMNS)
    logbook.event("credentials", mine["name"] + ": %d card(s), %d face photos" % (len(hashes), int(face_photos or 0)),
                  device, person_id)


def unregister(device):
    with csv_store.lock:
        rows = csv_store.read("registrations.csv")
        removed = ""
        for row in rows:
            if row["device"] == device and not row["to_time"]:
                row["to_time"] = logbook.now_text()
                removed = row["name"]
        csv_store.write("registrations.csv", rows, COLUMNS)
    if removed:
        logbook.event("unregistered", removed + " removed from " + device, device)
    return removed


def update_location(device, location):
    # The admin changed the device's location: the current registration follows it
    with csv_store.lock:
        rows = csv_store.read("registrations.csv")
        for row in rows:
            if row["device"] == device and not row["to_time"]:
                row["location"] = location
        csv_store.write("registrations.csv", rows, COLUMNS)
