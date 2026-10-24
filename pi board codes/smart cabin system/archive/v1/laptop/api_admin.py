# Smart Cabin server - admin only: register faculty, set up cabins, export the event log.

import csv
import io
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import config
import database
import security
import status_engine
from api_account import clean_username
from models import Approve, Cabin, Faculty

router = APIRouter()


# ---------- Faculty ----------
@router.get("/api/admin/faculty")
def list_faculty(admin=Depends(security.need_admin)):
    people = database.rows(
        "SELECT a.id, a.username, a.name, a.position, a.designation, a.school, a.department, a.email, a.active, "
        "c.name AS cabin, "
        "(SELECT COUNT(*) FROM cards WHERE account_id = a.id) AS cards, "
        "(SELECT COUNT(*) FROM bt_devices WHERE account_id = a.id) AS phones, "
        "COALESCE(s.face_photos, 0) AS face_photos "
        "FROM accounts a LEFT JOIN cabins c ON c.owner_id = a.id LEFT JOIN cabin_state s ON s.cabin_id = c.id "
        "WHERE a.role = 'faculty' ORDER BY a.name")
    return {"faculty": people, "positions": config.POSITIONS}


def check_faculty(data, adding):
    if not clean_username(data.username) or not data.name.strip():
        raise HTTPException(400, "Username and name are needed.")
    if data.position not in config.POSITIONS:
        raise HTTPException(400, "Position must be one of: " + ", ".join(config.POSITIONS))
    if adding or data.password:
        problem = security.password_problem(data.password)
        if problem:
            raise HTTPException(400, problem)


@router.post("/api/admin/faculty")
def add_faculty(data: Faculty, admin=Depends(security.need_admin)):
    check_faculty(data, adding=True)
    username = clean_username(data.username)
    if database.row("SELECT 1 FROM accounts WHERE username = ?", (username,)):
        raise HTTPException(400, "The username '" + username + "' is already taken.")
    new_id = database.run(
        "INSERT INTO accounts (username, password_hash, role, name, position, designation, school, department, "
        "email, active, created) VALUES (?, ?, 'faculty', ?, ?, ?, ?, ?, ?, 1, ?)",
        (username, security.hash_password(data.password), data.name.strip(), data.position, data.designation.strip(),
         data.school.strip(), data.department.strip(), data.email.strip(), time.time()))
    status_engine.log_event(new_id, None, "account", "registered by " + admin["username"])
    return {"ok": True, "id": new_id}


@router.put("/api/admin/faculty/{account_id}")
def edit_faculty(account_id: int, data: Faculty, admin=Depends(security.need_admin)):
    check_faculty(data, adding=False)
    username = clean_username(data.username)
    if database.row("SELECT 1 FROM accounts WHERE username = ? AND id != ?", (username, account_id)):
        raise HTTPException(400, "The username '" + username + "' is already taken.")
    database.run("UPDATE accounts SET username = ?, name = ?, position = ?, designation = ?, school = ?, "
                 "department = ?, email = ?, active = ? WHERE id = ? AND role = 'faculty'",
                 (username, data.name.strip(), data.position, data.designation.strip(), data.school.strip(),
                  data.department.strip(), data.email.strip(), int(data.active), account_id))
    if data.password:
        database.run("UPDATE accounts SET password_hash = ? WHERE id = ?", (security.hash_password(data.password), account_id))
    if not data.active:
        database.run("DELETE FROM sessions WHERE account_id = ?", (account_id,))    # logs them out everywhere
    return {"ok": True}


# ---------- Starter list: the AI School ----------
def username_for(name, taken):
    # "Dr. Shakkeera L" -> "shakkeeral" (titles dropped, letters only). Adds 2, 3 ... if it is taken.
    words = [w for w in name.replace(".", " ").split() if w.lower() not in ("dr", "mr", "ms", "mrs", "prof")]
    base = "".join(c for c in "".join(words).lower() if c.isalnum()) or "faculty"
    username, n = base, 1
    while username in taken:
        n += 1
        username = base + str(n)
    taken.add(username)
    return username


@router.post("/api/admin/import-ai-school")
def import_ai_school(admin=Depends(security.need_admin)):
    # Adds the AI School's faculty once. Returns a CSV with their usernames and temporary passwords:
    # the only time the passwords can be seen (only their hashes are stored).
    try:
        with open(config.STARTER_CSV, newline="", encoding="utf-8") as f:
            people = [p for p in csv.DictReader(f) if p["school"] == config.STARTER_SCHOOL]
    except OSError:
        raise HTTPException(400, "The list " + config.STARTER_CSV + " was not found.")
    existing = {a["name"] for a in database.rows("SELECT name FROM accounts")}
    taken = {a["username"] for a in database.rows("SELECT username FROM accounts")}

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["name", "position", "designation", "username", "temporary_password"])
    added = 0
    for p in people:
        if p["name"] in existing:
            continue                                   # already registered: skip
        position = "Dean" if p["name"] == config.STARTER_DEAN else p["role"] if p["role"] in config.POSITIONS else "Faculty"
        username = username_for(p["name"], taken)
        password = security.new_token()[:10]
        database.run("INSERT INTO accounts (username, password_hash, role, name, position, designation, school, "
                     "department, email, active, created) VALUES (?, ?, 'faculty', ?, ?, ?, ?, ?, '', 1, ?)",
                     (username, security.hash_password(password), p["name"], position, p["designation"],
                      config.STARTER_SCHOOL, p["department"] if p["department"] != p["school"] else "", time.time()))
        writer.writerow([p["name"], position, p["designation"], username, password])
        added += 1
    status_engine.log_event(None, None, "import", str(added) + " AI School faculty added by " + admin["username"])
    return Response(out.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=ai_school_logins.csv", "X-Added": str(added)})


# ---------- Cabins ----------
@router.get("/api/admin/cabins")
def list_cabins(admin=Depends(security.need_admin)):
    cabins = database.rows(
        "SELECT c.id, c.name, c.owner_id, a.name AS owner, c.token_hash IS NOT NULL AS connected, c.setup_code, "
        "c.device_id, c.device_name, "
        "c.code_expires, c.last_report, s.sensors, s.faculty_in, s.headcount "
        "FROM cabins c LEFT JOIN accounts a ON a.id = c.owner_id LEFT JOIN cabin_state s ON s.cabin_id = c.id "
        "ORDER BY c.name")
    now = time.time()
    for c in cabins:
        if not c["setup_code"] or c["code_expires"] < now:
            c["setup_code"] = ""                       # don't show an expired code
        c["online"] = now - (c["last_report"] or 0) < config.OFFLINE_SECONDS
        c["sensors"] = json.loads(c["sensors"]) if c["sensors"] else {}
        del c["code_expires"]
    return {"cabins": cabins}


def check_owner(owner_id, cabin_id):
    if owner_id is None:
        return
    if not database.row("SELECT 1 FROM accounts WHERE id = ? AND role = 'faculty'", (owner_id,)):
        raise HTTPException(400, "That faculty member doesn't exist.")
    taken = database.row("SELECT name FROM cabins WHERE owner_id = ? AND id != ?", (owner_id, cabin_id or 0))
    if taken:
        raise HTTPException(400, "That faculty member already has a cabin: " + taken["name"])


@router.post("/api/admin/cabins")
def add_cabin(data: Cabin, admin=Depends(security.need_admin)):
    if not data.name.strip():
        raise HTTPException(400, "Give the cabin a name, e.g. Block A, Room 204.")
    check_owner(data.owner_id, None)
    code = security.new_setup_code()
    new_id = database.run("INSERT INTO cabins (name, owner_id, setup_code, code_expires, created) VALUES (?, ?, ?, ?, ?)",
                          (data.name.strip(), data.owner_id, code, time.time() + config.SETUP_CODE_MINUTES * 60, time.time()))
    return {"ok": True, "id": new_id, "code": code}


def clean_device_id(text):
    # Pi serials look like "10000000a1b2c3d4": keep letters and digits only, lower case
    return "".join(c for c in (text or "").lower() if c.isalnum())[:64]


@router.put("/api/admin/cabins/{cabin_id}")
def edit_cabin(cabin_id: int, data: Cabin, admin=Depends(security.need_admin)):
    check_owner(data.owner_id, cabin_id)
    database.run("UPDATE cabins SET name = ?, owner_id = ? WHERE id = ?", (data.name.strip(), data.owner_id, cabin_id))
    if data.device_id is not None:
        # Link a device typed in advance (from the box label), or unlink with an empty value
        device_id = clean_device_id(data.device_id)
        old = database.row("SELECT device_id FROM cabins WHERE id = ?", (cabin_id,))
        if device_id != (old["device_id"] or ""):
            if device_id and database.row("SELECT name FROM cabins WHERE device_id = ? AND id != ?", (device_id, cabin_id)):
                raise HTTPException(400, "That device is already linked to another cabin.")
            database.run("UPDATE cabins SET device_id = ?, device_name = NULL, token_hash = NULL WHERE id = ?",
                         (device_id or None, cabin_id))
    return {"ok": True}


# ---------- Add a new device (automatic pairing) ----------
@router.get("/api/admin/device-requests")
def waiting_devices(admin=Depends(security.need_admin)):
    # Pis that said hello in the last minute and wait to be added
    now = time.time()
    database.run("DELETE FROM device_requests WHERE last_seen < ?", (now - config.REQUEST_FORGET_SECONDS,))
    found = database.rows("SELECT device_id, name, model, ip, pin, first_seen, last_seen FROM device_requests ORDER BY first_seen")
    for d in found:
        d["seen_ago"] = round(now - d["last_seen"])
        del d["first_seen"], d["last_seen"]
    return {"devices": found}


@router.post("/api/admin/device-requests/{device_id}/approve")
def approve_device(device_id: str, data: Approve, admin=Depends(security.need_admin)):
    # The admin only says which cabin this is (an existing one, or a new name) and who sits there.
    # The device's ID is linked to the cabin from now on: it will connect by itself in the future.
    waiting = database.row("SELECT * FROM device_requests WHERE device_id = ?", (device_id,))
    if waiting is None:
        raise HTTPException(404, "That device is no longer waiting. Is it still switched on?")
    if data.new_cabin.strip():
        check_owner(data.owner_id, None)
        cabin_id = database.run("INSERT INTO cabins (name, owner_id, created) VALUES (?, ?, ?)",
                                (data.new_cabin.strip()[:80], data.owner_id, time.time()))
    elif data.cabin_id:
        cabin_id = data.cabin_id
        if database.row("SELECT 1 FROM cabins WHERE id = ?", (cabin_id,)) is None:
            raise HTTPException(400, "That cabin doesn't exist.")
        if data.owner_id:
            check_owner(data.owner_id, cabin_id)
            database.run("UPDATE cabins SET owner_id = ? WHERE id = ?", (data.owner_id, cabin_id))
    else:
        raise HTTPException(400, "Pick the cabin, or type the name of a new one.")
    # This device belongs to this cabin only: unlink it from any other cabin
    database.run("UPDATE cabins SET device_id = NULL, device_name = NULL, token_hash = NULL WHERE device_id = ? AND id != ?",
                 (device_id, cabin_id))
    # Link the device. Its key is made on its next hello (a few seconds); an old device of this cabin stops working now.
    database.run("UPDATE cabins SET device_id = ?, device_name = ?, token_hash = NULL, setup_code = NULL WHERE id = ?",
                 (device_id, waiting["name"], cabin_id))
    database.run("DELETE FROM device_requests WHERE device_id = ?", (device_id,))
    cabin = database.row("SELECT * FROM cabins WHERE id = ?", (cabin_id,))
    status_engine.log_event(cabin["owner_id"], cabin_id, "device",
                            "device " + (waiting["name"] or device_id) + " linked to " + cabin["name"] + " by " + admin["username"])
    return {"ok": True, "cabin": cabin["name"], "cabin_id": cabin_id}


@router.delete("/api/admin/device-requests/{device_id}")
def ignore_device(device_id: str, admin=Depends(security.need_admin)):
    database.run("DELETE FROM device_requests WHERE device_id = ?", (device_id,))
    return {"ok": True}


@router.post("/api/admin/cabins/{cabin_id}/code")
def new_cabin_code(cabin_id: int, admin=Depends(security.need_admin)):
    # A new 6-digit code, to connect (or re-connect) a Pi to this cabin
    code = security.new_setup_code()
    database.run("UPDATE cabins SET setup_code = ?, code_expires = ? WHERE id = ?",
                 (code, time.time() + config.SETUP_CODE_MINUTES * 60, cabin_id))
    return {"ok": True, "code": code, "minutes": config.SETUP_CODE_MINUTES}


@router.delete("/api/admin/cabins/{cabin_id}")
def delete_cabin(cabin_id: int, admin=Depends(security.need_admin)):
    database.run("DELETE FROM cabin_state WHERE cabin_id = ?", (cabin_id,))
    database.run("DELETE FROM cabins WHERE id = ?", (cabin_id,))
    return {"ok": True}


# ---------- Event log ----------
@router.get("/api/admin/events")
def recent_events(admin=Depends(security.need_admin)):
    events = database.rows("SELECT e.time, e.kind, e.detail, a.name FROM events e "
                           "LEFT JOIN accounts a ON a.id = e.account_id ORDER BY e.id DESC LIMIT 100")
    for e in events:
        e["time"] = time.strftime("%d %b %H:%M:%S", time.localtime(e["time"]))
    return {"events": events}


@router.get("/api/admin/events.csv")
def export_events(admin=Depends(security.need_admin)):
    # The whole log as a CSV file (opens in Excel or pandas) for evaluation and the report
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["time", "date_time", "person", "cabin", "kind", "detail"])
    for e in database.rows("SELECT e.*, a.name AS person, c.name AS cabin FROM events e "
                           "LEFT JOIN accounts a ON a.id = e.account_id LEFT JOIN cabins c ON c.id = e.cabin_id "
                           "ORDER BY e.id"):
        writer.writerow([round(e["time"], 1), time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e["time"])),
                         e["person"] or "", e["cabin"] or "", e["kind"], e["detail"]])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=smart_cabin_events.csv"})
