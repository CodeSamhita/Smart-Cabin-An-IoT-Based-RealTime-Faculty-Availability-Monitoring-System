# Smart Cabin laptop server - imports the university's section timetable (aSc Timetables PDF) as each faculty
# member's own timetable. Run it once a semester:
#   python import_timetable.py "<timetable>.pdf"                         import into data/
#   python import_timetable.py "<timetable>.pdf" --dry-run               only say what would happen
#   python import_timetable.py "<timetable>.pdf" --name "Even semester 2026-27" --data <folder>
#
# The PDF has one page per student section: days down the side, periods 1-8 across, and in each cell the course,
# the teacher and the room. The text positions on the page tell which day and period a cell is in. The classes are
# then regrouped per teacher (the same course in the same period for several sections = one combined class), the
# teacher is matched to people.csv by name (title dropped, any word order, only a
# unique match), and the person gets a timetable with that name, set in use, saved with timetables.save() (the same
# checks as on the website). Teachers that don't match anyone are listed in data/timetable_import_unmatched.csv.
# Lunch: each section page has its "Lunch Break" column (period 4 or 5). A teacher keeps one lunch period all week:
# the one most of their classes' sections have (a tie: period 5, the more common one). On a day they teach in it,
# they get the other of 4 / 5 if that is free, else no lunch that day.
# Needs the pypdf package (pip install pypdf).

import collections
import csv
import os
import re
import sys

import settings

if "--data" in sys.argv and sys.argv.index("--data") + 1 < len(sys.argv):
    settings.DATA_FOLDER = os.path.abspath(sys.argv[sys.argv.index("--data") + 1])

import csv_store
import people
import timetables
from security import UserError

DAYS = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday"}
COURSE = re.compile(r"[A-Z]{3}\d{4}(_P)?")
BATCH_TEXT = re.compile(r"a?B\d")                       # a lab batch, written after the room: B1, B2 (or aB2)


def option(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else default


def read_pdf(path):
    # [{section, day, period, course, teacher, room}] for every class cell in the PDF, and {section: lunch period}
    from pypdf import PdfReader
    classes, lunch = [], {}
    for page in PdfReader(path).pages:
        items, placed = [], []
        def visit(text, cm, tm, font, size):
            if text.strip():
                items.append((text.strip(), tm[4], tm[5]))
                # The same text on the page itself (cm applied): the rotated "Lunch Break" is only placed right this way
                placed.append((text.strip(), tm[4] * cm[0] + tm[5] * cm[2] + cm[4]))
        page.extract_text(visitor_text=visit)
        section = items[-1][0] if items else "?"              # the section's name is the last text on the page
        days = [(DAYS[t], y) for t, x, y in items if t in DAYS]
        periods = [(int(t), x) for t, x, y in items if re.fullmatch(r"[1-8]", t)]
        if not days or not periods:
            continue
        column = lambda x: min(periods, key=lambda p: abs(p[1] - x))[0]
        on_page = [(int(t), x) for t, x in placed if re.fullmatch(r"[1-8]", t)]
        for t, x in placed:
            if t.startswith("Lunch"):
                lunch[section] = min(on_page, key=lambda p: abs(p[1] - x))[0]
        for i, (t, x, y) in enumerate(items):
            if COURSE.fullmatch(t) and i + 2 < len(items):
                # A cell: course (left), teacher, room (right), and for a lab batch its batch ("B1", "B2").
                # The course starts in the first period's column and the room ends in the last one's, so a
                # two-period lab gives two different columns.
                first, last = column(x), column(items[i + 2][1])
                after = items[i + 3][0] if i + 3 < len(items) else ""
                classes.append({"section": section, "course": t, "teacher": items[i + 1][0], "room": items[i + 2][0],
                                "batch": after.lstrip("a") if BATCH_TEXT.fullmatch(after) else "",
                                "day": min(days, key=lambda d: abs(d[1] - y))[0],
                                "period": first, "to": max(first, last)})
    return classes, lunch


def name_key(name):
    name = re.sub(r"^(dr|prof|mr|ms|mrs)\.?\s+", "", name.lower().strip())
    return tuple(sorted(re.findall(r"[a-z]+", name)))


def without_initials(key):
    return tuple(w for w in key if len(w) > 1)


def match_teachers(teachers):
    # teacher name -> person id, only when exactly one person has that name. Initials may differ between the PDF and
    # people.csv ("S Pravinthraja" / "Dr. Pravinthraja"), so without initials as a second try, again only if unique.
    by_key, by_name = collections.defaultdict(list), collections.defaultdict(list)
    for p in people.all_people():
        by_key[name_key(p["name"])].append(p["id"])
        by_name[without_initials(name_key(p["name"]))].append(p["id"])
    found = {}
    for t in teachers:
        exact, loose = by_key.get(name_key(t), []), by_name.get(without_initials(name_key(t)), [])
        if len(exact) == 1:
            found[t] = exact[0]
        elif not exact and len(loose) == 1 and without_initials(name_key(t)):
            found[t] = loose[0]
    return found


def short_sections(sections):
    # "5CIT01", "5CIT02", "5CIT03" -> "5CIT01/02/03" (several sections taught together fit in the 30-letter field)
    sections = sorted(set(sections))
    if len(sections) > 1 and len({s[:-2] for s in sections}) == 1:
        return sections[0] + "/" + "/".join(s[-2:] for s in sections[1:])
    return ", ".join(sections)


def combined(rows):
    # The same course in the same period for several sections = one class taught to them together
    groups = collections.OrderedDict()
    for r in rows:
        key = (r["period"], r["to"], r["course"], r["room"], r["batch"])
        if key in groups:
            groups[key]["sections"].append(r["section"])
        else:
            groups[key] = dict(r, sections=[r["section"]])
    return [dict(g, section=short_sections(g["sections"])) for g in groups.values()]


def entries_for(rows):
    # One teacher's classes on one day -> timetable entries (a lab cell already spans its periods)
    entries = []
    for r in sorted(combined(rows), key=lambda r: r["period"]):
        entries.append({"kind": "class", "from": r["period"], "to": r["to"], "course": r["course"], "room": r["room"],
                        "section": r["section"], "batch": r["batch"]})
    return entries


def lunch_period(sections_week, lunch):
    # One teacher's lunch period for the whole week (see the top of this file), or None
    votes = collections.Counter(lunch[s] for s in sections_week if s in lunch)
    if not votes:
        return None
    return max(votes, key=lambda period: (votes[period], period == 5))


def lunch_for(entries, first):
    # That period on one day, the other of 4 / 5 if they teach in it, or None if they teach in both
    if not first:
        return None
    busy = {n for e in entries for n in range(e["from"], e["to"] + 1)}
    for period in (first, 9 - first if first in (4, 5) else first):
        if period not in busy:
            return period
    return None


def main():
    if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
        sys.exit("Usage: python import_timetable.py <timetable.pdf> [--name \"Odd semester 2026-27\"] [--dry-run] [--data <folder>]")
    name, dry = option("--name", "Odd semester 2026-27"), "--dry-run" in sys.argv
    try:
        classes, lunch = read_pdf(sys.argv[1])
    except ImportError:
        sys.exit("The pypdf package is missing: pip install pypdf")
    teachers = collections.Counter(c["teacher"] for c in classes)
    ids = match_teachers(teachers)
    print("%d classes in %d sections, %d teachers, %d matched to people.csv"
          % (len(classes), len({c["section"] for c in classes}), len(teachers), len(ids)))

    per_person = collections.defaultdict(lambda: collections.defaultdict(list))
    for c in classes:
        if c["teacher"] in ids:
            per_person[ids[c["teacher"]]][c["day"]].append(c)
    print("lunch break found for %d of %d sections" % (len(lunch), len({c["section"] for c in classes})))
    saved, skipped, lunches = 0, [], 0
    for person_id, days in sorted(per_person.items()):
        week = {d: [] for d in settings.DAYS}
        for day, rows in days.items():
            for e in entries_for(rows):
                try:                                          # keep an entry only if the day still passes the checks
                    timetables.check_week(dict(week, **{day: week[day] + [e]}))
                    week[day].append(e)
                except UserError as problem:
                    skipped.append((person_id, day, e["from"], e["course"], e["section"], str(problem)))
        own = lunch_period([c["section"] for rows in days.values() for c in rows], lunch)
        for day in [d for d in settings.DAYS if d != "Saturday"]:
            period = lunch_for(week[day], own)
            if period:
                week[day].append({"kind": "lunch", "from": period, "to": period, "course": "", "room": "",
                                  "section": "", "batch": ""})
                week[day].sort(key=lambda e: e["from"])
                lunches += 1
        if not dry:
            timetables.save(person_id, name, name, week)
            timetables.use(person_id, name)
        saved += 1
    unmatched = sorted(t for t in teachers if t not in ids)
    if not dry:
        csv_store.write("timetable_import_unmatched.csv", [{"teacher": t, "classes": teachers[t]} for t in unmatched],
                        ["teacher", "classes"])
    print(("would save" if dry else "saved") + " \"%s\" (in use) for %d faculty members" % (name, saved))
    print("lunch breaks added: %d" % lunches)
    print("left out (a different class at the same time, a clash in the PDF): %d" % len(skipped))
    for s in skipped[:12]:
        print("    %s %s period %s: %s %s" % s[:5])
    print("teachers not matched: %d%s" % (len(unmatched), "" if dry else " (data/timetable_import_unmatched.csv)"))


if __name__ == "__main__":
    main()
