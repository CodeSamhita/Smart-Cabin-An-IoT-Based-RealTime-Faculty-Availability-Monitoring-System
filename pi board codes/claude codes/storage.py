# Saving users on the Pi:
#   data/users.csv        user_id, name, card_uid, face_photos, registered
#   data/devices.csv      user_id, address, device_name, added
#   data/faces/<id>.npy   the face as numbers (photos x 128). No photos are kept.
import csv
import os
import time

import numpy as np

import config

USER_COLUMNS = ["user_id", "name", "card_uid", "face_photos", "registered"]
DEVICE_COLUMNS = ["user_id", "address", "device_name", "added"]


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, columns, rows):
    os.makedirs(config.DATA_FOLDER, exist_ok=True)
    with open(path + ".part", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(path + ".part", path)          # the file is never left half written


def load_users():
    # [{"user_id": "1", "name": .., "card_uid": .., "face_photos": "10", "registered": ..,
    #   "devices": [{"address": .., "device_name": .., "added": ..}]}]
    users = read_csv(config.USERS_CSV)
    devices = read_csv(config.DEVICES_CSV)
    for user in users:
        user["devices"] = [d for d in devices if d["user_id"] == user["user_id"]]
    return users


def face_path(user_id):
    return os.path.join(config.FACES_FOLDER, str(user_id) + ".npy")


def load_faces():
    # {user_id: array (photos x 128)} for every user with a face
    faces = {}
    for user in read_csv(config.USERS_CSV):
        if os.path.exists(face_path(user["user_id"])):
            faces[user["user_id"]] = np.load(face_path(user["user_id"]))
    return faces


def add_user(name, card, face, devices):
    # Saves one new user. face = list of 128-number lists (or []), devices = [{"address", "name"}]
    users = read_csv(config.USERS_CSV)
    user_id = str(max([int(u["user_id"]) for u in users] + [0]) + 1)
    now = time.strftime("%Y-%m-%d %H:%M")
    if face:
        os.makedirs(config.FACES_FOLDER, exist_ok=True)
        np.save(face_path(user_id), np.array(face, dtype=np.float32))
    users.append({"user_id": user_id, "name": name, "card_uid": card, "face_photos": len(face), "registered": now})
    write_csv(config.USERS_CSV, USER_COLUMNS, users)
    rows = read_csv(config.DEVICES_CSV)
    rows += [{"user_id": user_id, "address": d["address"], "device_name": d["name"], "added": now} for d in devices]
    write_csv(config.DEVICES_CSV, DEVICE_COLUMNS, rows)
    return user_id


def delete_user(user_id):
    # Returns the user's device addresses, so they can be unpaired too
    users = [u for u in read_csv(config.USERS_CSV) if u["user_id"] != user_id]
    write_csv(config.USERS_CSV, USER_COLUMNS, users)
    rows = read_csv(config.DEVICES_CSV)
    gone = [d["address"] for d in rows if d["user_id"] == user_id]
    write_csv(config.DEVICES_CSV, DEVICE_COLUMNS, [d for d in rows if d["user_id"] != user_id])
    if os.path.exists(face_path(user_id)):
        os.remove(face_path(user_id))
    return gone


def card_owner(card):
    for user in read_csv(config.USERS_CSV):
        if card and user["card_uid"] == card:
            return user["name"]
    return None


def device_owner(address):
    names = {u["user_id"]: u["name"] for u in read_csv(config.USERS_CSV)}
    for d in read_csv(config.DEVICES_CSV):
        if d["address"] == address:
            return names.get(d["user_id"], "another user")
    return None


def name_taken(name):
    return any(u["name"].strip().lower() == name.strip().lower() for u in read_csv(config.USERS_CSV))


def all_device_addresses():
    return [d["address"] for d in read_csv(config.DEVICES_CSV)]
