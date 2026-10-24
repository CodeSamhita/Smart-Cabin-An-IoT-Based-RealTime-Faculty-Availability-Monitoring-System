# Smart Cabin server - what the cabin device (Pi) calls. Every call except "claim" needs the
# X-Device-Token header. All of them are listed, and can be tried, on http://<laptop>:8080/docs
#
#   hello   : a new Pi says hello and waits; once the admin picks it, the next hello returns its token
#   claim   : 6-digit code from the admin page -> the device's secret token (fallback)
#   config  : who owns this cabin, their cards and phones (the Pi keeps a copy for when the laptop is off)
#   report  : evidence every few seconds (faculty in, headcount, phone near, events) -> the status to show
#   enrol   : the faculty member logs in on the Pi's setup page -> link a card, add a phone

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request

import config
import database
import security
import status_engine
from api_account import clean_username
from api_admin import clean_device_id
from api_faculty import press_button
from models import BluetoothDevice, CardLink, Claim, EnrolLogin, Hello, Report

router = APIRouter()

LED = {"green": "green", "yellow": "yellow", "red": "red", "grey": "red"}   # grey can't happen while reporting


def owner_of(cabin):
    if not cabin["owner_id"]:
        return None
    return database.row("SELECT id, name FROM accounts WHERE id = ? AND active = 1", (cabin["owner_id"],))


@router.post("/api/device/claim")
def claim(data: Claim):
    cabin = database.row("SELECT * FROM cabins WHERE setup_code = ? AND code_expires > ?", (data.code.strip(), time.time()))
    if cabin is None:
        time.sleep(1)                                    # slows down guessing
        raise HTTPException(400, "Wrong or expired code. Make a new one on the admin page (Cabins).")
    token = security.new_token()
    database.run("UPDATE cabins SET token_hash = ?, setup_code = NULL WHERE id = ?", (security.token_hash(token), cabin["id"]))
    status_engine.log_event(cabin["owner_id"], cabin["id"], "device", "cabin device connected")
    return {"token": token, "cabin": cabin["name"]}


@router.post("/api/device/hello")
def hello(data: Hello, request: Request):
    # A Pi without a key says hello every few seconds. If its device ID is linked to a cabin (picked by the admin,
    # or typed in advance from the box label), it gets a new key straight away. Otherwise it waits in the list.
    device_id = clean_device_id(data.device_id)             # same form as an ID typed on the Cabins page
    if not device_id:
        raise HTTPException(400, "device_id missing")
    now = time.time()
    # A device already linked to a cabin connects straight away (installed in its room, or reset)
    linked = database.row("SELECT * FROM cabins WHERE device_id = ?", (device_id,))
    if linked:
        token = security.new_token()
        database.run("UPDATE cabins SET token_hash = ?, device_name = ? WHERE id = ?",
                     (security.token_hash(token), data.name[:60] or linked["device_name"], linked["id"]))
        database.run("DELETE FROM device_requests WHERE device_id = ?", (device_id,))
        status_engine.log_event(linked["owner_id"], linked["id"], "device", "linked device " + (data.name or device_id) +
                                " connected by itself")
        return {"status": "approved", "token": token, "cabin": linked["name"]}
    # Not linked yet: wait in the admin's "Add a new device" list
    waiting = database.row("SELECT * FROM device_requests WHERE device_id = ?", (device_id,))
    ip = request.client.host if request.client else ""
    if waiting:
        database.run("UPDATE device_requests SET name = ?, model = ?, ip = ?, pin = ?, last_seen = ? WHERE device_id = ?",
                     (data.name[:60], data.model[:80], ip, data.pin[:8], now, device_id))
    else:
        database.run("INSERT INTO device_requests (device_id, name, model, ip, pin, first_seen, last_seen) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", (device_id, data.name[:60], data.model[:80], ip, data.pin[:8], now, now))
    return {"status": "waiting"}


@router.get("/api/device/config")
def device_config(cabin=Depends(security.need_device)):
    owner = owner_of(cabin)
    if owner is None:
        return {"cabin": cabin["name"], "owner": None, "cards": [], "phones": [], "enrol_active": False}
    cards = [c["uid"] for c in database.rows("SELECT uid FROM cards WHERE account_id = ?", (owner["id"],))]
    phones = database.rows("SELECT address, name FROM bt_devices WHERE account_id = ?", (owner["id"],))
    return {"cabin": cabin["name"], "owner": owner, "cards": cards, "phones": phones,
            "enrol_active": cabin["enrol_until"] > time.time(), "max_phones": config.MAX_BT_DEVICES}


@router.post("/api/device/report")
def report(data: Report, cabin=Depends(security.need_device)):
    now = time.time()
    owner = owner_of(cabin)
    owner_id = owner["id"] if owner else None
    database.run("UPDATE cabins SET last_report = ? WHERE id = ?", (now, cabin["id"]))
    database.run("INSERT OR REPLACE INTO cabin_state (cabin_id, faculty_in, headcount, phone_near, face_photos, sensors, "
                 "updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (cabin["id"], int(data.faculty_in), max(0, data.headcount), int(data.phone_near), data.face_photos,
                  json.dumps(data.sensors), now))

    # Everything that happened since the last report goes into the event log
    for e in data.events:
        status_engine.log_event(owner_id, cabin["id"], e.kind, e.detail)
        if e.kind == "card_login" and owner_id:
            # Tapping in ends a "Not available" button (plan section 4)
            o = database.row("SELECT status FROM overrides WHERE account_id = ?", (owner_id,))
            if o and o["status"] == "red":
                status_engine.clear_override(owner_id, "card tapped in")

    if owner_id is None:
        return {"status": "grey", "led": "off", "reason": "No faculty member assigned to this cabin", "until": "",
                "owner": None}
    if data.button:
        press_button(owner_id, data.button, "", 60, "button")
    shown = status_engine.refresh(owner_id, now)
    return {"status": shown["status"], "led": LED[shown["status"]], "reason": shown["reason"],
            "until": shown["until_text"], "manual": bool(shown["manual"]), "owner": owner}


# ---------- Setup on the Pi (the faculty member logs in there) ----------
def need_enrol(cabin):
    if cabin["enrol_until"] < time.time():
        raise HTTPException(403, "Log in on the cabin device first (setup is open for "
                            + str(config.ENROL_MINUTES) + " minutes after logging in).")
    owner = owner_of(cabin)
    if owner is None:
        raise HTTPException(400, "No faculty member is assigned to this cabin yet (admin page, Cabins).")
    return owner


@router.post("/api/device/enrol")
def enrol_login(data: EnrolLogin, cabin=Depends(security.need_device)):
    account = database.row("SELECT * FROM accounts WHERE username = ? AND active = 1", (clean_username(data.username),))
    if account is None or not security.check_password(data.password, account["password_hash"]):
        time.sleep(1)
        raise HTTPException(401, "Wrong username or password.")
    if account["role"] != "admin" and account["id"] != cabin["owner_id"]:
        raise HTTPException(403, "This is not your cabin. It belongs to: " + (owner_of(cabin) or {"name": "nobody"})["name"])
    database.run("UPDATE cabins SET enrol_until = ? WHERE id = ?", (time.time() + config.ENROL_MINUTES * 60, cabin["id"]))
    status_engine.log_event(cabin["owner_id"], cabin["id"], "setup", "setup opened on the cabin device by " + account["username"])
    return {"ok": True, "name": account["name"], "minutes": config.ENROL_MINUTES}


@router.post("/api/device/enrol/end")
def enrol_end(cabin=Depends(security.need_device)):
    database.run("UPDATE cabins SET enrol_until = 0 WHERE id = ?", (cabin["id"],))
    return {"ok": True}


@router.post("/api/device/enrol/card")
def link_card(data: CardLink, cabin=Depends(security.need_device)):
    owner = need_enrol(cabin)
    uid = data.uid.strip().upper()
    used = database.row("SELECT a.name, a.id FROM cards c JOIN accounts a ON a.id = c.account_id WHERE c.uid = ?", (uid,))
    if used and used["id"] != owner["id"]:
        raise HTTPException(400, "This card already belongs to " + used["name"] + ".")
    if not used:
        database.run("INSERT INTO cards (uid, account_id, added) VALUES (?, ?, ?)", (uid, owner["id"], time.time()))
        status_engine.log_event(owner["id"], cabin["id"], "card_linked", uid)
    return {"ok": True, "uid": uid, "name": owner["name"]}


@router.post("/api/device/enrol/phone")
def add_phone(data: BluetoothDevice, cabin=Depends(security.need_device)):
    owner = need_enrol(cabin)
    address = data.address.strip().upper()
    used = database.row("SELECT account_id FROM bt_devices WHERE address = ?", (address,))
    if used and used["account_id"] != owner["id"]:
        raise HTTPException(400, "This device already belongs to someone else.")
    count = database.row("SELECT COUNT(*) AS n FROM bt_devices WHERE account_id = ?", (owner["id"],))["n"]
    if not used and count >= config.MAX_BT_DEVICES:
        raise HTTPException(400, "You already have " + str(config.MAX_BT_DEVICES) + " devices. Remove one on your page first.")
    if not used:
        database.run("INSERT INTO bt_devices (address, account_id, name, added) VALUES (?, ?, ?, ?)",
                     (address, owner["id"], data.name.strip() or address, time.time()))
        status_engine.log_event(owner["id"], cabin["id"], "phone_linked", data.name + " " + address)
    return {"ok": True}
