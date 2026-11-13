# Smart Cabin laptop server - each faculty member's own timetables (timetables.csv, timetable_in_use.csv).
# A person may keep several named timetables; one is "in use" (the one the status rules and the public page read).
# One row per entry: kind (class / lunch), day, first and last period (settings.PERIODS), course, room, section, batch,
# plus one row of kind "name" per timetable (so an empty timetable still exists).
#   of_person() : all their timetables + which one is in use
#   save()      : replace one timetable after the checks below
#   use(), delete()
#   today()     : today's entries of the timetable in use, with start and end times from the periods
#   on_day()    : the same for any day (the public page's week view)

import time

import csv_store
import logbook
import settings
from security import UserError

COLUMNS = ["person_id", "timetable", "day", "kind", "period_from", "period_to", "course", "room", "section", "batch"]
IN_USE_COLUMNS = ["person_id", "timetable"]
TEXT_LIMIT = 30


def in_use(person_id):
    row = next((r for r in csv_store.read("timetable_in_use.csv") if r["person_id"] == person_id), None)
    return row["timetable"] if row else ""


def set_in_use(person_id, name):
    with csv_store.lock:
        rows = [r for r in csv_store.read("timetable_in_use.csv") if r["person_id"] != person_id]
        if name:
            rows.append({"person_id": person_id, "timetable": name})
        csv_store.write("timetable_in_use.csv", rows, IN_USE_COLUMNS)


def of_person(person_id):
    tables = {}
    for r in csv_store.read("timetables.csv"):
        if r["person_id"] != person_id:
            continue
        week = tables.setdefault(r["timetable"], {d: [] for d in settings.DAYS})
        if r["kind"] != "name" and r["day"] in week:
            week[r["day"]].append({"kind": r["kind"], "from": int(r["period_from"]), "to": int(r["period_to"]),
                                   "course": r["course"], "room": r["room"], "section": r["section"], "batch": r["batch"]})
    return {"tables": [{"name": name, "week": week} for name, week in tables.items()], "in_use": in_use(person_id)}


def clean_entry(entry):
    try:
        first, last = int(entry.get("from")), int(entry.get("to"))
    except (TypeError, ValueError):
        raise UserError("Every entry needs its first and last period.")
    kind = "lunch" if entry.get("kind") == "lunch" else "class"
    text = lambda name: " ".join(str(entry.get(name, "")).split())[:TEXT_LIMIT]
    return {"kind": kind, "from": first, "to": last, "course": text("course") if kind == "class" else "",
            "room": text("room") if kind == "class" else "", "section": text("section") if kind == "class" else "",
            "batch": text("batch") if kind == "class" else ""}


def check_week(week):
    # Periods in order and not across a break, one lunch a day, a course for every class, and two entries in the
    # same periods only when they are batches (B1 / B2) of the same lab
    for day in settings.DAYS:
        entries = week[day]
        if sum(1 for e in entries if e["kind"] == "lunch") > 1:
            raise UserError(day + ": only one lunch break a day.")
        for i, e in enumerate(entries):
            name = day + " period " + str(e["from"])
            if e["from"] not in settings.PERIODS or e["to"] not in settings.PERIODS:
                raise UserError(name + ": periods are 1 to 8.")
            if e["to"] < e["from"]:
                raise UserError(name + ": the last period must not be before the first.")
            if (e["from"] <= 2 < e["to"]) or (e["from"] <= 6 < e["to"]):
                raise UserError(name + ": a class cannot run across a break.")
            if e["kind"] == "lunch" and e["to"] != e["from"]:
                raise UserError(name + ": lunch is one period.")
            if e["kind"] == "class" and not e["course"]:
                raise UserError(name + ": write the course (e.g. DSC4002).")
            for o in entries[:i]:
                if e["from"] <= o["to"] and o["from"] <= e["to"]:
                    batches = (e["kind"] == o["kind"] == "class" and (e["from"], e["to"]) == (o["from"], o["to"])
                               and e["batch"] and o["batch"] and e["batch"] != o["batch"])
                    if not batches:
                        raise UserError(day + ": periods %d-%d and %d-%d overlap (only lab batches B1 / B2 may share "
                                        "periods)." % (o["from"], o["to"], e["from"], e["to"]))


def save(person_id, old_name, name, week):
    name = " ".join(str(name).split())[:40]
    if not name:
        raise UserError("Give the timetable a name.")
    if not isinstance(week, dict):
        raise UserError("The timetable came without days.")
    clean = {d: [clean_entry(e) for e in (week.get(d) or [])[:20] if isinstance(e, dict)] for d in settings.DAYS}
    check_week(clean)
    with csv_store.lock:
        rows = csv_store.read("timetables.csv")
        names = {r["timetable"] for r in rows if r["person_id"] == person_id}
        if name.lower() != old_name.lower() and name.lower() in {n.lower() for n in names}:
            raise UserError("You already have a timetable called \"" + name + "\".")
        rows = [r for r in rows if not (r["person_id"] == person_id and r["timetable"] in (old_name, name))]
        # One "name" row per timetable, so a timetable with no entries yet still exists
        rows.append({"person_id": person_id, "timetable": name, "day": "", "kind": "name", "period_from": "",
                     "period_to": "", "course": "", "room": "", "section": "", "batch": ""})
        for day in settings.DAYS:
            for e in clean[day]:
                rows.append({"person_id": person_id, "timetable": name, "day": day, "kind": e["kind"],
                             "period_from": e["from"], "period_to": e["to"], "course": e["course"], "room": e["room"],
                             "section": e["section"], "batch": e["batch"]})
        csv_store.write("timetables.csv", rows, COLUMNS)
        if not in_use(person_id) or in_use(person_id) == old_name:
            set_in_use(person_id, name)
    logbook.event("timetable", "\"" + name + "\" saved", "", person_id)


def use(person_id, name):
    if name not in {t["name"] for t in of_person(person_id)["tables"]}:
        raise UserError("No timetable called \"" + name + "\".")
    set_in_use(person_id, name)
    logbook.event("timetable", "\"" + name + "\" is now in use", "", person_id)


def delete(person_id, name):
    if name == in_use(person_id):
        raise UserError("This timetable is in use. Put another one in use first.")
    with csv_store.lock:
        rows = [r for r in csv_store.read("timetables.csv") if not (r["person_id"] == person_id and r["timetable"] == name)]
        csv_store.write("timetables.csv", rows, COLUMNS)
    logbook.event("timetable", "\"" + name + "\" deleted", "", person_id)


def today(person_id):
    # Today's entries of the timetable in use, in the old timetable.csv form (start, end, activity, room) plus kind,
    # or None if the person has no timetable of their own yet
    return on_day(person_id, time.strftime("%A"))


def on_day(person_id, day):
    # One day's entries of the timetable in use (as today()), or None without a timetable of their own
    name = in_use(person_id)
    if not name:
        return None
    items = []
    for r in csv_store.read("timetables.csv"):
        if r["person_id"] == person_id and r["timetable"] == name and r["day"] == day and r["kind"] != "name":
            start, end = settings.PERIODS[int(r["period_from"])][0], settings.PERIODS[int(r["period_to"])][1]
            if r["kind"] == "lunch":
                items.append({"start": start, "end": end, "activity": "Lunch break", "room": "", "kind": "lunch",
                              "from": int(r["period_from"]), "to": int(r["period_to"])})
            else:
                what = r["course"] + (" " + r["batch"] if r["batch"] else "") + (" (" + r["section"] + ")" if r["section"] else "")
                items.append({"start": start, "end": end, "activity": what, "room": r["room"], "kind": "class",
                              "from": int(r["period_from"]), "to": int(r["period_to"]),
                              "course": r["course"], "section": r["section"], "batch": r["batch"]})
    return sorted(items, key=lambda i: i["start"])
