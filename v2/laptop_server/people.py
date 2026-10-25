# Smart Cabin laptop server - the university faculty list (people.csv) and programmes (programs.csv).
#   search()  : people matching a name and the school / department / programme filters
#   get()     : one person by id
#   filters() : the choices for the drop-downs on the public page
# The files are read again only when they change, so editing them in Excel works while the server runs.

import os

import csv_store

cache = {}


def load(name):
    # Read a CSV, but only again if the file changed since last time
    try:
        changed = os.path.getmtime(csv_store.path(name))
    except OSError:
        return []
    if name not in cache or cache[name][0] != changed:
        cache[name] = (changed, csv_store.read(name))
    return cache[name][1]


def all_people():
    return load("people.csv")


def get(person_id):
    for person in all_people():
        if person["id"] == person_id:
            return person
    return None


def schools_with_degree(degree):
    return {p["school"] for p in load("programs.csv") if p.get("degree") == degree}


def search(text="", school="", department="", degree=""):
    words = text.lower().split()
    allowed_schools = schools_with_degree(degree) if degree else None
    found = []
    for person in all_people():
        name = person["name"].lower()
        if words and not all(w in name for w in words):
            continue
        if school and person["school"] != school:
            continue
        if department and person["department"] != department:
            continue
        if allowed_schools is not None and person["school"] not in allowed_schools:
            continue
        found.append(person)
    return found


def filters():
    people = all_people()
    order = ["B.Tech", "M.Tech", "Ph.D", "BCA", "MCA", "B.Sc", "M.Sc", "BBA", "MBA", "B.Com", "M.Com", "B.Des"]
    degrees = sorted({p["degree"] for p in load("programs.csv") if p.get("degree")},
                     key=lambda d: (order.index(d) if d in order else len(order), d))
    return {"schools": sorted({p["school"] for p in people if p["school"]}),
            "departments": sorted({p["department"] for p in people if p["department"]}),
            "degrees": degrees}
