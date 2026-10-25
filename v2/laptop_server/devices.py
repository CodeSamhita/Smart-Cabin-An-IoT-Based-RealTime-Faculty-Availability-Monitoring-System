# Smart Cabin laptop server - the register of edge devices (devices.csv), like a registrar's roll list.
#   hello()       : a Pi introduces itself with its hardware serial. A new serial gets the next device
#                   number (SC-001, SC-002, ...) and a secret key. Only the key's hash is stored.
#   check_key()   : every later call from a Pi must carry its serial and key
#   set_location(): the admin writes where the device is (set once, changed only if it is moved)
#   reset_key()   : the admin lets a device get a new key (e.g. after its SD card was rewritten)
#   save_health() : the latest health report per device (device_health.csv)

import json
import time

import csv_store
import logbook
import security
from security import UserError

DEVICE_COLUMNS = ["device", "serial", "model", "location", "key_hash", "ip", "first_seen", "last_seen"]
HEALTH_COLUMNS = ["device", "time", "temperature", "cpu_percent", "memory_free_mb", "throttled",
                  "parts", "last_error", "page_url"]


def all_devices():
    return csv_store.read("devices.csv")


def find(rows, field, value):
    for row in rows:
        if row[field] == value:
            return row
    return None


def next_number(rows):
    used = [int(r["device"][3:]) for r in rows if r["device"].startswith("SC-") and r["device"][3:].isdigit()]
    return "SC-%03d" % (max(used, default=0) + 1)


def hello(serial, model, ip, key):
    # Returns (device row, new key or ""). A new key is only ever sent once.
    serial = str(serial).strip()
    if not serial or len(serial) > 64:
        raise UserError("The device sent no serial number.")
    with csv_store.lock:
        rows = all_devices()
        row = find(rows, "serial", serial)
        new_key = ""
        if row is None:
            new_key = security.new_token()
            row = {"device": next_number(rows), "serial": serial, "model": str(model)[:60], "location": "",
                   "key_hash": security.sha256(new_key), "ip": ip, "first_seen": logbook.now_text(), "last_seen": time.time()}
            rows.append(row)
            logbook.event("new device", "serial " + serial + " registered as " + row["device"], row["device"])
        elif not row["key_hash"]:                         # the admin reset this device's key
            new_key = security.new_token()
            row["key_hash"] = security.sha256(new_key)
            logbook.event("device key", "new key given after a reset", row["device"])
        elif not security.same(row["key_hash"], security.sha256(key or "")):
            logbook.event("refused", "hello with a wrong key from " + ip + " (serial " + serial + ")", row["device"])
            raise UserError("This device's key is wrong. If its SD card was rewritten, the admin must press "
                            "'Reset key' for " + row["device"] + " on the Devices page.")
        row["model"], row["ip"], row["last_seen"] = str(model)[:60], ip, time.time()
        csv_store.write("devices.csv", rows, DEVICE_COLUMNS)
        return row, new_key


def check_key(serial, key, ip=""):
    # The device row if the serial and key match, else UserError
    row = find(all_devices(), "serial", str(serial or ""))
    if row is None or not row["key_hash"] or not security.same(row["key_hash"], security.sha256(key or "")):
        raise UserError("Unknown device or wrong device key. The device must say hello again.")
    return row


def touch(device, ip):
    # Remember when we last heard from a device
    with csv_store.lock:
        rows = all_devices()
        row = find(rows, "device", device)
        if row:
            row["last_seen"], row["ip"] = time.time(), ip
            csv_store.write("devices.csv", rows, DEVICE_COLUMNS)


def set_location(device, location):
    location = " ".join(str(location).split())[:80]
    if not location:
        raise UserError("Type the location, for example: J block, 4th floor, cabin 412")
    with csv_store.lock:
        rows = all_devices()
        row = find(rows, "device", device)
        if row is None:
            raise UserError("No device " + device)
        old = row["location"]
        row["location"] = location
        csv_store.write("devices.csv", rows, DEVICE_COLUMNS)
    logbook.event("location", device + ": '" + old + "' -> '" + location + "'", device)


def reset_key(device):
    with csv_store.lock:
        rows = all_devices()
        row = find(rows, "device", device)
        if row is None:
            raise UserError("No device " + device)
        row["key_hash"] = ""
        csv_store.write("devices.csv", rows, DEVICE_COLUMNS)
    logbook.event("device key", "key reset by the admin; the device gets a new one at its next hello", device)


def save_health(device, health, page_url=""):
    health = health if isinstance(health, dict) else {}
    with csv_store.lock:
        rows = [r for r in csv_store.read("device_health.csv") if r["device"] != device]
        rows.append({"device": device, "time": time.time(), "temperature": health.get("temperature", ""),
                     "cpu_percent": health.get("cpu_percent", ""), "memory_free_mb": health.get("memory_free_mb", ""),
                     "throttled": health.get("throttled", ""), "parts": json.dumps(health.get("parts", {}))[:2000],
                     "last_error": str(health.get("last_error", ""))[:300], "page_url": str(page_url)[:100]})
        csv_store.write("device_health.csv", rows, HEALTH_COLUMNS)


def health_of(device):
    return find(csv_store.read("device_health.csv"), "device", device) or {}
