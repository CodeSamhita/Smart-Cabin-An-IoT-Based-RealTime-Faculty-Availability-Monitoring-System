# Smart Cabin server - a faculty member's own page: status buttons and devices (the timetable is in api_timetable.py).
# Also "notify me when available" watches, for anyone logged in.

import time

from fastapi import APIRouter, Depends, HTTPException

import config
import database
import security
import status_engine
from models import StatusButton

router = APIRouter()

BUTTONS = {"available": "green", "meeting": "yellow", "away": "red"}


# ---------- Status buttons ----------
def press_button(account_id, mode, reason, minutes, source):
    # Used by the web page and by the hardware buttons on the cabin device
    if mode == "auto":
        status_engine.clear_override(account_id, "Auto pressed (" + source + ")")
        status_engine.refresh(account_id)
        return
    if mode not in BUTTONS:
        raise HTTPException(400, "Unknown button: " + mode)
    if mode == "away":
        reason = reason if reason in config.AWAY_REASONS else config.AWAY_REASONS[0]
        minutes = min(max(minutes, 5), 24 * 60)
    else:
        reason, minutes = "", config.OVERRIDE_MINUTES     # Available / In a meeting end by themselves (plan section 4)
    status_engine.set_override(account_id, BUTTONS[mode], reason, minutes, source)


@router.get("/api/my/status")
def my_status(account=Depends(security.need_faculty)):
    shown = status_engine.refresh(account["id"])
    override = database.row("SELECT * FROM overrides WHERE account_id = ?", (account["id"],))
    return {"status": shown["status"], "label": status_engine.LABELS[shown["status"]], "reason": shown["reason"],
            "until": shown["until_text"], "manual": bool(shown["manual"]),
            "button": override["status"] if override else "", "away_reasons": config.AWAY_REASONS}


@router.post("/api/my/status")
def set_my_status(data: StatusButton, account=Depends(security.need_faculty)):
    press_button(account["id"], data.mode, data.reason, data.minutes, "web")
    return my_status(account)


# ---------- Devices (cards, phones, face) ----------
@router.get("/api/my/devices")
def my_devices(account=Depends(security.need_faculty)):
    cabin = status_engine.cabin_of(account["id"])
    state = status_engine.state_of(cabin)
    cards = database.rows("SELECT uid, added FROM cards WHERE account_id = ? ORDER BY added", (account["id"],))
    phones = database.rows("SELECT address, name, added FROM bt_devices WHERE account_id = ? ORDER BY added", (account["id"],))
    for item in cards + phones:
        item["added"] = time.strftime("%d %b %Y", time.localtime(item["added"]))
    return {"cabin": cabin["name"] if cabin else "", "cards": cards, "phones": phones,
            "face_photos": state["face_photos"] if state else 0, "max_phones": config.MAX_BT_DEVICES,
            "device_online": bool(cabin) and time.time() - cabin["last_report"] < config.OFFLINE_SECONDS}


@router.delete("/api/my/cards/{uid}")
def remove_card(uid: str, account=Depends(security.need_faculty)):
    database.run("DELETE FROM cards WHERE uid = ? AND account_id = ?", (uid.upper(), account["id"]))
    status_engine.log_event(account["id"], None, "card_removed", uid.upper())
    return my_devices(account)


@router.delete("/api/my/phones/{address}")
def remove_phone(address: str, account=Depends(security.need_faculty)):
    # The cabin device also forgets the pairing the next time it syncs (within a minute)
    database.run("DELETE FROM bt_devices WHERE address = ? AND account_id = ?", (address.upper(), account["id"]))
    status_engine.log_event(account["id"], None, "phone_removed", address.upper())
    return my_devices(account)


# ---------- "Notify me when available" (anyone logged in) ----------
@router.get("/api/watches")
def my_watches(account=Depends(security.need_login)):
    # Active watches, and alerts that fired but were not shown yet
    watches = database.rows(
        "SELECT w.target_id, w.fired, w.shown, a.name FROM watches w JOIN accounts a ON a.id = w.target_id "
        "WHERE w.watcher_id = ? AND (w.fired = 0 OR w.shown = 0) ORDER BY w.created", (account["id"],))
    alerts = [w for w in watches if w["fired"] and not w["shown"]]
    return {"watching": [w for w in watches if not w["fired"]], "alerts": alerts}


# (This route must come before /api/watches/{target_id}, or "shown" would be read as a person's id)
@router.post("/api/watches/shown")
def alerts_shown(account=Depends(security.need_login)):
    database.run("UPDATE watches SET shown = 1 WHERE watcher_id = ? AND fired > 0", (account["id"],))
    return {"ok": True}


@router.post("/api/watches/{target_id}")
def watch(target_id: int, account=Depends(security.need_login)):
    if target_id == account["id"]:
        raise HTTPException(400, "That's you.")
    if not database.row("SELECT 1 FROM accounts WHERE id = ? AND role = 'faculty'", (target_id,)):
        raise HTTPException(404, "Person not found.")
    database.run("DELETE FROM watches WHERE watcher_id = ? AND target_id = ?", (account["id"], target_id))
    database.run("INSERT INTO watches (watcher_id, target_id, created) VALUES (?, ?, ?)",
                 (account["id"], target_id, time.time()))
    return my_watches(account)


@router.delete("/api/watches/{target_id}")
def unwatch(target_id: int, account=Depends(security.need_login)):
    database.run("DELETE FROM watches WHERE watcher_id = ? AND target_id = ?", (account["id"], target_id))
    return my_watches(account)


def end_old_watches():
    # Watches end at the end of the day (called by the status timer)
    start_of_day = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    database.run("DELETE FROM watches WHERE created < ?", (start_of_day,))
