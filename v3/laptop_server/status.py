# Smart Cabin laptop server - statuses.
#   receive_report() : a device's report (decided on the Pi) -> status_now.csv + one row in presence_log.csv
#   public_people()  : the public page's list: people + status + where / until from the timetable
#   person_detail()  : one person for the public page, with today's timetable
# A device silent for SILENT_SECONDS shows as "unknown". Only public fields leave this file.

import time

import csv_store
import devices
import logbook
import people
import registrations
import settings
import timetable
from security import UserError

STATUS_COLUMNS = ["person_id", "device", "status", "in_cabin", "confidence", "headcount", "face", "card", "face_age",
                  "arriving", "updated"]
# arriving: seconds until the Pi reports the person in (it waits 100 s after the face is seen before telling the server)
CLASS_SOON_MINUTES = 5          # a class this soon, and the face not seen for FACE_GONE_SECONDS = "Leaving for ..."
FACE_GONE_SECONDS = 120
NOT_BUSY = ("break", "lunch", "office hours", "free")   # timetable items that don't take the person out of the cabin
LOG_COLUMNS = ["time", "device", "person_id", "face", "card", "headcount", "dark", "confidence",
               "in_cabin", "status", "temperature"]
STATUSES = ("available", "meeting", "not_available")
LABELS = {"available": "Available", "meeting": "In a meeting", "not_available": "Not available",
          "unknown": "Unknown", "not_set_up": "Not set up"}


def number(value, low, high, default=0):
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def receive_report(device_row, report):
    device = device_row["device"]
    registration = registrations.current_for_device(device)
    status = report.get("status")
    if status not in STATUSES:
        raise UserError("Unknown status '" + str(status) + "'.")
    person_id = registration["person_id"] if registration else ""
    if report.get("person_id") and report.get("person_id") != person_id:
        # The Pi thinks someone else is registered here: tell it, so it can fetch the right person
        logbook.log.warning("%s reports person %s but the server has %s", device, report.get("person_id"), person_id or "nobody")
    row = {"person_id": person_id, "device": device, "status": status,
           "in_cabin": "yes" if report.get("in_cabin") else "no",
           "confidence": int(number(report.get("confidence"), 0, 100)),
           "headcount": int(number(report.get("headcount"), 0, 50)),
           "face": "yes" if report.get("face") else "no", "card": "yes" if report.get("card") else "no",
           "face_age": int(number(report.get("face_age"), 0, 86400, 86400)),
           "arriving": int(number(report.get("arriving"), 0, 3600)), "updated": time.time()}
    with csv_store.lock:
        rows = csv_store.read("status_now.csv")
        old = next((r for r in rows if r["device"] == device), None)
        rows = [r for r in rows if r["device"] != device]
        if person_id:
            rows = [r for r in rows if r["person_id"] != person_id]    # one status per person
            rows.append(row)
        csv_store.write("status_now.csv", rows, STATUS_COLUMNS)
    health = report.get("health") if isinstance(report.get("health"), dict) else {}
    csv_store.append("presence_log.csv", {
        "time": logbook.now_text(), "device": device, "person_id": person_id,
        "face": 1 if report.get("face") else 0, "card": 1 if report.get("card") else 0,
        "headcount": row["headcount"], "dark": 1 if report.get("dark") else 0, "confidence": row["confidence"],
        "in_cabin": 1 if report.get("in_cabin") else 0, "status": status,
        "temperature": health.get("temperature", "")}, LOG_COLUMNS)
    if person_id and (old is None or old["status"] != status):
        logbook.event("status", LABELS[status] + " (confidence " + str(row["confidence"]) + " %, headcount "
                      + str(row["headcount"]) + ")", device, person_id)
    return registration


def where_and_until(person_id, status):
    now_item = timetable.now_item(person_id)
    next_item = timetable.next_item(person_id)
    if status in ("available", "meeting"):
        return "In the cabin", ("until " + next_item["start"] + " (" + timetable.describe(next_item) + ")") if next_item else "rest of the day"
    if now_item:
        return timetable.describe(now_item), "back around " + now_item["end"]
    if next_item:
        return "Not in the cabin", "next: " + timetable.describe(next_item) + " at " + next_item["start"]
    return "Not in the cabin", ""


def busy_now(person_id):
    # The timetable item now if it is not a free hour (lunch / break / office hours / free are free), else None
    item = timetable.now_item(person_id)
    if not item or item.get("kind") == "lunch" or any(word in item.get("activity", "").lower() for word in NOT_BUSY):
        return None
    return item


def class_soon(person_id):
    # The next class / lab / meeting today if it starts within CLASS_SOON_MINUTES, else None
    item = timetable.next_item(person_id)
    if not item or any(word in item.get("activity", "").lower() for word in NOT_BUSY):
        return None
    hours, minutes = [int(x) for x in item["start"].split(":")]
    now = time.localtime()
    minutes_left = hours * 60 + minutes - (now.tm_hour * 60 + now.tm_min)
    return item if 0 <= minutes_left <= CLASS_SOON_MINUTES else None


def how_in(row):
    # How the device knows the person is in: face seen (in the last 2 min) and / or card tapped. A card tap alone
    # is not "in": the Pi is still looking for the face (the status stays Not available).
    if row.get("in_cabin") != "yes":
        if number(row.get("arriving"), 0, 3600) > 0:
            return "Seen in the cabin, confirming (" + str(int(number(row.get("arriving"), 0, 3600))) + " s)"
        return "Card tapped, checking the camera" if row.get("card") == "yes" else ""
    face, card = row.get("face") == "yes", row.get("card") == "yes"
    if face and card:
        return "Seen and tapped in"
    if face:
        return "Seen, not tapped in"
    if card:
        return "Tapped in, not seen yet"
    return "Someone counted in the cabin"


def status_for(person, registration, status_rows, device_rows):
    # The public view of one person
    result = {"id": person["id"], "name": person["name"], "designation": person["designation"],
              "school": person["school"], "department": person["department"],
              "location": registration["location"] if registration else "", "status": "not_set_up",
              "where": "", "until": "", "how": "", "updated": ""}
    if registration is None:
        return result
    row = next((r for r in status_rows if r["person_id"] == person["id"]), None)
    device = next((d for d in device_rows if d["device"] == registration["device"]), None)
    last = float(device["last_seen"]) if device and device["last_seen"] else 0
    if row is None or time.time() - last > settings.SILENT_SECONDS:
        result["status"] = "unknown"
        item = timetable.now_item(person["id"])
        result["where"] = timetable.describe(item) + " (timetable)" if item else "Cabin device not reporting"
    else:
        result["status"] = row["status"]
        result["where"], result["until"] = where_and_until(person["id"], row["status"])
        result["how"] = how_in(row)
        busy = busy_now(person["id"])
        if busy and row["status"] in ("available", "meeting"):
            # In the cabin, but the timetable has a class / lab / meeting now (not a free hour): not available
            result["status"], result["how"] = "not_available", "In the cabin, but busy (timetable)"
            result["where"], result["until"] = timetable.describe(busy) + " now", "until " + busy["end"]
        soon = class_soon(person["id"])
        if soon and row["status"] in ("available", "meeting") and number(row.get("face_age"), 0, 86400, 86400) > FACE_GONE_SECONDS:
            # A class in a few minutes and the face not seen for 2 minutes: on the way to it
            result["status"], result["how"] = "not_available", ""
            result["where"], result["until"] = "Leaving for " + timetable.describe(soon), "at " + soon["start"]
    result["updated"] = time.strftime("%H:%M:%S", time.localtime(last)) if last else ""
    return result


def public_people(text="", school="", department="", degree=""):
    found = people.search(text, school, department, degree)
    regs = {r["person_id"]: r for r in csv_store.read("registrations.csv") if not r["to_time"]}
    status_rows = csv_store.read("status_now.csv")
    device_rows = devices.all_devices()
    found.sort(key=lambda p: (p["id"] not in regs, p["name"]))       # people with a device first
    shown = [status_for(p, regs.get(p["id"]), status_rows, device_rows) for p in found[:settings.PUBLIC_LIMIT]]
    return {"people": shown, "total": len(found), "shown": len(shown), "labels": LABELS}


def everyone():
    # Every faculty member with their status (public fields + role), for the pages that group and filter on the
    # phone / browser. Also: which schools offer which programme, for the programme filter.
    regs = {r["person_id"]: r for r in csv_store.read("registrations.csv") if not r["to_time"]}
    status_rows = csv_store.read("status_now.csv")
    device_rows = devices.all_devices()
    shown = []
    for person in people.all_people():
        row = status_for(person, regs.get(person["id"]), status_rows, device_rows)
        row["role"] = person.get("role", "")
        shown.append(row)
    degree_schools = {}
    for program in people.load("programs.csv"):
        if program.get("degree"):
            degree_schools.setdefault(program["degree"], set()).add(program["school"])
    return {"people": shown, "labels": LABELS,
            "degree_schools": {d: sorted(s) for d, s in degree_schools.items()}}


def recent_presence(device, count=60):
    # The device's last `count` rows of presence_log.csv (read from the end, the file only grows)
    import collections
    import csv
    path = csv_store.path("presence_log.csv")
    try:
        with csv_store.lock, open(path, newline="", encoding="utf-8-sig") as f:
            header = next(csv.reader(f))
            last = collections.deque((line for line in f if (',' + device + ',') in line), maxlen=count)
    except (OSError, StopIteration):
        return []
    return [dict(zip(header, row)) for row in csv.reader(last)]


def person_detail(person_id):
    person = people.get(person_id)
    if person is None:
        raise UserError("No such person.")
    result = status_for(person, registrations.current_for_person(person_id),
                        csv_store.read("status_now.csv"), devices.all_devices())
    result["today"] = timetable.public_items(person_id)
    result["week"] = timetable.public_week(person_id)
    result["day"] = time.strftime("%A")
    return result
