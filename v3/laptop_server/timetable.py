# Smart Cabin laptop server - what a person's timetable says today.
# The person's own timetable in use (timetables.py) comes first; people without one still use the old
# timetable.csv (person_id, day, start, end, activity, room).
#   today()    : a person's items for today, in time order
#   now_item() : what the timetable says they are doing right now (or None)
#   next_item(): their next item today (or None)
# Times are "HH:MM", days are "Monday" ... "Saturday".

import time

import people
import timetables


def today(person_id):
    own = timetables.today(person_id)
    if own is not None:
        return own
    day = time.strftime("%A")
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


def public_items(person_id):
    # Today's timetable in the form the public page shows
    return [{"start": i["start"], "end": i["end"], "activity": describe(i)} for i in today(person_id)]
