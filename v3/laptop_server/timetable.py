# Smart Cabin laptop server - what a person's timetable says today.
# The person's own timetable in use (timetables.py) comes first; people without one still use the old
# timetable.csv (person_id, day, start, end, activity, room).
#   today()    : a person's items for today, in time order (on_day(): any day)
#   public_items(), public_week(): today's / the week's items as the public page shows them
#   public_grid(): the week as a period grid, like the university's section timetable
#   now_item() : what the timetable says they are doing right now (or None)
#   next_item(): their next item today (or None)
# Times are "HH:MM", days are "Monday" ... "Saturday".

import time

import people
import settings
import timetables

WEEK = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def today(person_id):
    return on_day(person_id, time.strftime("%A"))


def on_day(person_id, day):
    own = timetables.on_day(person_id, day)
    if own is not None:
        return own
    items = [row for row in people.load("timetable.csv") if row["person_id"] == person_id and row["day"] == day]
    return sorted(items, key=lambda row: row["start"])


def now_item(person_id, clock=None):
    clock = clock or time.strftime("%H:%M")
    for item in today(person_id):
        if item["start"] <= clock < item["end"]:
            return item
    return None


def next_item(person_id, clock=None):
    clock = clock or time.strftime("%H:%M")
    for item in today(person_id):
        if item["start"] > clock:
            return item
    return None


def describe(item):
    text = item.get("activity", "") or "Busy"
    if item.get("room"):
        text += ", " + item["room"]
    return text


def public_items(person_id, day=None):
    # One day's timetable (today if no day is given) in the form the public page shows
    items = on_day(person_id, day) if day else today(person_id)
    return [{"start": i["start"], "end": i["end"], "activity": describe(i)} for i in items]


def public_week(person_id):
    # The whole week for the public page: Monday - Friday, and Saturday only if it has something
    week = [{"day": d, "items": public_items(person_id, d)} for d in WEEK]
    return [w for w in week if w["items"] or w["day"] != "Saturday"]


def public_grid(person_id):
    # The week laid out like the university's section timetable: periods as columns (with the short breaks),
    # days as rows. None when the person has no timetable of their own (then the page shows the list).
    if not timetables.in_use(person_id):
        return None
    fields = ("kind", "from", "to", "course", "section", "batch", "room")
    days = [{"day": d, "items": [{k: i.get(k, "") for k in fields} for i in timetables.on_day(person_id, d) or []]}
            for d in WEEK]
    return {"periods": [{"n": n, "start": s, "end": e} for n, (s, e) in sorted(settings.PERIODS.items())],
            "breaks": [{"start": s, "end": e} for s, e in settings.BREAKS],
            "days": [d for d in days if d["items"] or d["day"] != "Saturday"]}
