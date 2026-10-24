# Smart Cabin server - timetables (BUILD_PLAN.md section 2b).
#   - make_slots(): the day's times from a template (Hour 1, Hour 2, Tea, ...) and a start time
#   - save_grid():  turns the filled-in grid into entries (a Lab takes 2 hours, breaks are added)
#   - current_item(), next_item(), back_at(): what is on now / next / when they are back
# Days are 0 = Monday ... 5 = Saturday. Times are "HH:MM" text, compared as minutes since midnight.

import json
import re
import time

import config
import database

# How each activity reads on the status page when the person is away
AWAY_TEXT = {"Class": "In class", "Lab": "In the lab", "Meeting": "In a meeting", "Break": "On a break",
             "Office hours": "Office hours (not in the cabin)", "Other": "Busy"}


# ---------- Times ----------
def to_minutes(hhmm):
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_hhmm(minutes):
    return "%02d:%02d" % (minutes // 60 % 24, minutes % 60)


def is_time(text):
    return bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text or ""))


def day_and_minutes(now=None):
    # (weekday 0 - 6, minutes since midnight) in the laptop's local time
    t = time.localtime(now if now is not None else time.time())
    return t.tm_wday, t.tm_hour * 60 + t.tm_min


# ---------- Day times from a template ----------
def make_slots(template="A", start=config.DAY_START, class_minutes=config.CLASS_MINUTES,
               tea_minutes=config.TEA_MINUTES, lunch_minutes=config.LUNCH_MINUTES):
    # [{"kind": "hour", "label": "Hour 1", ...}, {"kind": "tea", "label": "Tea break", ...},
    #  {"kind": "lunch", "label": "Hour 5 (lunch)", ...}, ...]   The lunch hour has a number too.
    lengths = {"hour": class_minutes, "tea": tea_minutes, "lunch": lunch_minutes}
    slots, minute, hour_number = [], to_minutes(start), 0
    for kind in config.TEMPLATES[template]:
        if kind in config.NUMBERED:
            hour_number += 1
        label = {"hour": "Hour " + str(hour_number), "lunch": "Hour " + str(hour_number) + " (lunch)",
                 "tea": "Tea break"}[kind]
        slots.append({"kind": kind, "label": label, "start": to_hhmm(minute), "end": to_hhmm(minute + lengths[kind])})
        minute += lengths[kind]
    return slots


def check_slots(slots):
    # Returns a message if the day times are wrong, else ""
    previous_end = 0
    for s in slots:
        if s["kind"] not in ("hour", "tea", "lunch") or not is_time(s["start"]) or not is_time(s["end"]):
            return "Every time must look like 09:00."
        if to_minutes(s["end"]) <= to_minutes(s["start"]):
            return s["label"] + ": the end must be after the start."
        if to_minutes(s["start"]) < previous_end:
            return s["label"] + " starts before the one above it ends."
        previous_end = to_minutes(s["end"])
    return ""


# ---------- Locations ----------
def floor_text(floor):
    if floor == 0:
        return "Ground floor"
    ending = {1: "st", 2: "nd", 3: "rd"}.get(floor if floor < 20 else floor % 10, "th")
    return str(floor) + ending + " floor"


def place_text(cell):
    # "J block, 4th floor, Room 3" (Lab for labs). Empty when no block was picked.
    if not cell.get("building"):
        return ""
    kind = "Lab" if cell.get("activity") == "Lab" else "Room"
    text = cell["building"] + " block, " + floor_text(int(cell.get("floor") or 0))
    if cell.get("number"):
        text += ", " + kind + " " + str(cell["number"])
    return text


# ---------- The timetables of one person (one per school / branch) ----------
def sheets(account_id):
    found = database.rows("SELECT * FROM timetable_sheets WHERE account_id = ? ORDER BY id", (account_id,))
    for s in found:
        s["saturday"] = bool(s["saturday"])
        s["slots"] = json.loads(s["slots"])
        s["cells"] = json.loads(s["cells"])
    return found


def new_sheet(account_id, name):
    return database.run("INSERT INTO timetable_sheets (account_id, name, template, saturday, slots, cells, updated) "
                        "VALUES (?, ?, 'A', 0, ?, '{}', ?)", (account_id, name, json.dumps(make_slots("A")), time.time()))


def save_sheet(sheet_id, name, template, saturday, slots, cells):
    # cells: {"day-slot": {"activity": "Class", "title": "CSE301", "building": "J", "floor": 4, "number": 3}}
    # "day-slot" = day 0 - 5 and the position of the hour in the list of slots.
    database.run("UPDATE timetable_sheets SET name = ?, template = ?, saturday = ?, slots = ?, cells = ?, updated = ? "
                 "WHERE id = ?", (name, template, int(saturday), json.dumps(slots), json.dumps(cells), time.time(), sheet_id))


def sheet_entries(sheet):
    # One timetable -> (busy entries, break entries); each is (day, start, end, activity, title, place, sheet name)
    # The lunch hour is a numbered hour: empty = Lunch break, but it can hold a class like any hour.
    # A lab takes 2 numbered hours in a row (lunch counts, tea doesn't); each hour becomes its own entry.
    slots, cells = sheet["slots"], sheet["cells"]
    numbered = [i for i, s in enumerate(slots) if s["kind"] in config.NUMBERED]
    busy, breaks = [], []
    for day in range(6 if sheet["saturday"] else 5):
        lab_hours = {}                                                     # 2nd lab hour -> the lab's cell
        lab_spans = []                                                     # (start of 1st hour, end of 2nd hour)
        for n, i in enumerate(numbered):
            cell = lab_hours.get(i) or cells.get(str(day) + "-" + str(i))
            if cell and cell.get("activity") in config.ACTIVITIES and not cell.get("continues"):
                first_lab_hour = cell["activity"] == "Lab" and i not in lab_hours and n + 1 < len(numbered)
                # The 1st lab hour runs on to the start of the 2nd, so a tea break in between is part of the lab
                end = slots[numbered[n + 1]]["start"] if first_lab_hour else slots[i]["end"]
                busy.append((day, slots[i]["start"], end, cell["activity"],
                             (cell.get("title") or "").strip()[:40], place_text(cell), sheet["name"]))
                if first_lab_hour:
                    lab_hours[numbered[n + 1]] = cell                     # the lab goes on in the next hour
                    lab_spans.append((to_minutes(slots[i]["start"]), to_minutes(slots[numbered[n + 1]]["end"])))
            elif slots[i]["kind"] == "lunch":
                breaks.append((day, slots[i]["start"], slots[i]["end"], "Break", "Lunch break", "", sheet["name"]))
        for s in slots:
            inside_lab = any(a <= to_minutes(s["start"]) < b for a, b in lab_spans)
            if s["kind"] == "tea" and not inside_lab:                      # a tea break inside a lab: the lab goes on
                breaks.append((day, s["start"], s["end"], "Break", s["label"], "", sheet["name"]))
    return busy, breaks


def overlaps(a, b):
    return a[0] == b[0] and to_minutes(a[1]) < to_minutes(b[2]) and to_minutes(b[1]) < to_minutes(a[2])


def rebuild(account_id):
    # Merges all of a person's timetables into the entries the status rules use. Returns clash warnings.
    busy, breaks = [], []
    for sheet in sheets(account_id):
        b, br = sheet_entries(sheet)
        busy += b
        breaks += br

    clashes = []
    for i, a in enumerate(busy):
        for b in busy[i + 1:]:
            if overlaps(a, b):
                clashes.append(config.DAYS[a[0]] + " " + a[1] + ": " + a[3] + " " + a[4] + " (" + a[6] + ") and "
                               + b[3] + " " + b[4] + " (" + b[6] + ") at the same time")

    # A break is kept only where no timetable has something busy, and only once
    kept_breaks = []
    for br in breaks:
        if not any(overlaps(br, b) for b in busy) and not any(overlaps(br, k) for k in kept_breaks):
            kept_breaks.append(br)

    database.run("DELETE FROM timetable WHERE account_id = ?", (account_id,))
    for day, start, end, activity, title, place, sheet_name in busy + kept_breaks:
        database.run("INSERT INTO timetable (account_id, sheet, day, start, end, activity, title, place) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (account_id, sheet_name, day, start, end, activity, title, place))
    return clashes


# ---------- Reading the timetable ----------
def week(account_id):
    # Every entry, sorted by day then start time
    return database.rows("SELECT * FROM timetable WHERE account_id = ? ORDER BY day, start", (account_id,))


def today(account_id, now=None):
    day, _ = day_and_minutes(now)
    return [e for e in week(account_id) if e["day"] == day]


def current_item(account_id, now=None):
    # The entry happening right now, or None
    _, minute = day_and_minutes(now)
    for e in today(account_id, now):
        if to_minutes(e["start"]) <= minute < to_minutes(e["end"]):
            return e
    return None


def next_item(account_id, now=None):
    # The next entry later today that is not a break, or None
    _, minute = day_and_minutes(now)
    for e in today(account_id, now):
        if to_minutes(e["start"]) > minute and e["activity"] != "Break":
            return e
    return None


def back_at(account_id, now=None):
    # When the current entry ends. Entries that follow straight on (within 10 min) are joined,
    # e.g. Class 9:00-9:50 then Lab 9:50-11:40 -> back around 11:40. Breaks don't join. Returns "HH:MM" or "".
    current = current_item(account_id, now)
    if current is None:
        return ""
    end = to_minutes(current["end"])
    if current["activity"] == "Break":
        return to_hhmm(end)
    for e in today(account_id, now):
        if end <= to_minutes(e["start"]) <= end + 10 and e["activity"] not in ("Office hours", "Break"):
            end = max(end, to_minutes(e["end"]))
    return to_hhmm(end)


def describe(entry):
    # "Class CSE301, J block, 4th floor, Room 3" for timetable lists
    if entry["activity"] == "Break":
        return entry["title"] or "Break"
    text = entry["activity"] + (" " + entry["title"] if entry["title"] else "")
    return text + (", " + entry["place"] if entry["place"] else "")


def away_text(entry):
    # "In class CSE301, J block, 4th floor, Room 3" for the status page
    if entry["activity"] == "Break":
        return "On a " + (entry["title"] or "break").lower()
    text = AWAY_TEXT.get(entry["activity"], entry["activity"]) + (" " + entry["title"] if entry["title"] else "")
    return text + (", " + entry["place"] if entry["place"] else "")
