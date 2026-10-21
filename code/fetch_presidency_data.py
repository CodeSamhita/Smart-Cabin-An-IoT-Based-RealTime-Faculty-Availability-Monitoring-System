# Downloads the faculty list and programmes from the Presidency University website
# and saves them as CSV files in the data folder.
#
# Run:  python fetch_presidency_data.py
#
# It writes:
#   data/people.csv     - every faculty member (name, designation, role, school, department)
#   data/programs.csv   - every programme offered by each school, with its degree (B.Tech, MBA, ...) and level
#   data/timetable.csv  - a made-up DEMO timetable (the website has no timetables)

import csv
import html
import os
import random
import re
import urllib.request

import config

BASE = "https://presidencyuniversity.in/school/"

# Official school names (as on the university website) -> faculty page.
# Engineering and Liberal Arts also have department pages, listed further down.
CSE = "Presidency School of Computer Science and Engineering"
ENG = "Presidency School of Engineering"
ISC = "Presidency School of Information Science"
MGT = "Presidency School of Management"
COM = "Presidency School of Commerce"
LAW = "Presidency School of Law"
DES = "Presidency School of Design"
MED = "Presidency School of Media Studies"
LAS = "Presidency School of Liberal Arts and Sciences"
AHP = "Presidency School of Allied and Healthcare Professions"
AI = "Presidency School of Artificial Intelligence and Advanced Computing"

SCHOOL_PAGES = [
    (CSE, "school-of-computer-science-engineering"),
    (ENG, "school-of-engineering"),
    (ISC, "school-of-information-science"),
    (MGT, "school-of-management"),
    (COM, "school-of-commerce"),
    (LAW, "school-of-law"),
    (DES, "school-of-design"),
    (MED, "school-of-media-studies"),
    (LAS, "presidency-school-of-liberal-arts-and-sciences"),
    (AHP, "presidency-school-of-allied-and-healthcare-professions"),
    (AI, "presidency-school-of-artificial-intelligence-and-advanced-computing"),
]

# Departments inside a school: (school, official department name, page)
DEPARTMENT_PAGES = [
    (ENG, "Department of Civil Engineering", "school-of-engineering/faculty/department-of-civil-engineering"),
    (ENG, "Department of Electrical and Electronics Engineering", "school-of-engineering/faculty/department-of-electrical-electronics-engineering"),
    (ENG, "Department of Electronics and Communication Engineering", "school-of-engineering/faculty/department-of-electronics-and-communication-engineering"),
    (ENG, "Department of Mechanical Engineering", "school-of-engineering/faculty/department-of-mechanical-engineering"),
    (ENG, "Department of Petroleum Engineering", "school-of-engineering/faculty/department-of-petroleum-engineering"),
    (ENG, "Department of Physics", "school-of-engineering/faculty/department-of-physics"),
    (ENG, "Department of Chemistry", "school-of-engineering/faculty/department-of-chemistry"),
    (ENG, "Department of Mathematics", "school-of-engineering/faculty/department-of-mathematics"),
    (ENG, "Department of Learning & Development", "school-of-engineering/faculty/department-of-learning-development"),
    (LAS, "Department of Languages", "presidency-school-of-liberal-arts-and-sciences/faculty/department-of-languages"),
]


def download(path):
    # Get one page from the website as text
    request = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0 (Smart Cabin student project)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def clean(text):
    # Remove HTML tags like <br> and <span>, codes like &amp;, and extra spaces
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def read_faculty(path):
    # Each faculty card looks like: <div class="fac_details"> <h4>Name</h4> <p>Designation</p>
    page = download(path)
    found = re.findall(r'class="fac_details">\s*<h4>(.*?)</h4>\s*<p>(.*?)</p>', page, re.S)
    return [(clean(name), clean(designation)) for name, designation in found]


def read_programs(path):
    # Each programme looks like: <h4>Name</h4> <h3>School</h3> <h5>Duration - 4 Years</h5>
    page = download(path)
    found = re.findall(r'<h4[^>]*>(.*?)</h4>\s*<h3>(.*?)</h3>\s*<h5>(.*?)</h5>', page, re.S)
    return [(clean(name), clean(duration).replace("Duration - ", "")) for name, school, duration in found]


# Programme name start -> (degree, level). Checked from top to bottom, so longer names come first
# (e.g. "BBALLB" before "BBA", and "BACHELOROF..." before "BA").
DEGREES = [
    ("PHD", "Ph.D", "Doctoral"),
    ("POSTGRADUATEDIPLOMA", "PG Diploma", "Diploma"),
    ("PGDIPLOMA", "PG Diploma", "Diploma"),
    ("DIPLOMA", "Diploma", "Diploma"),
    ("MTECH", "M.Tech", "Master's"),
    ("MBA", "MBA", "Master's"),
    ("MCOM", "M.Com", "Master's"),
    ("MCA", "MCA", "Master's"),
    ("MASTEROFCOMPUTERAPPLICATIONS", "MCA", "Master's"),
    ("MASTEROFSCIENCE", "M.Sc", "Master's"),
    ("MSC", "M.Sc", "Master's"),
    ("MA", "M.A.", "Master's"),
    ("LLM", "LL.M.", "Master's"),
    ("BTECH", "B.Tech", "Bachelor's"),
    ("BBALLB", "BBA LL.B", "Bachelor's"),
    ("BALLB", "BA LL.B", "Bachelor's"),
    ("BBA", "BBA", "Bachelor's"),
    ("BACHELOROFBUSINESSADMINISTRATION", "BBA", "Bachelor's"),
    ("BCA", "BCA", "Bachelor's"),
    ("BACHELOROFCOMPUTERAPPLICATIONS", "BCA", "Bachelor's"),
    ("BCOM", "B.Com", "Bachelor's"),
    ("BDES", "B.Des", "Bachelor's"),
    ("BSC", "B.Sc", "Bachelor's"),
    ("BACHELOROFSCIENCE", "B.Sc", "Bachelor's"),
    ("BFA", "BFA", "Bachelor's"),
    ("BACHELOROFFINEARTS", "BFA", "Bachelor's"),
]


def degree_of(program):
    # Work out the degree (B.Tech, MBA, ...) and level (Bachelor's, Master's, ...) from the name
    short = program.upper().replace(" ", "").replace(".", "")
    for start, degree, level in DEGREES:
        if short.startswith(start):
            return degree, level

    # Health science degrees have the short name in brackets, e.g. "Bachelor of Physiotherapy (B.PT)"
    found = re.search(r"\((B\.\s?[A-Z]+)\)", program)
    if found:
        return found.group(1).replace(" ", ""), "Bachelor's"

    if short.startswith("BA"):
        return "B.A.", "Bachelor's"
    return "Other", "Other"


def role_from(designation):
    # Short role used for search and filters
    text = designation.lower()
    if "dean" in text:
        return "Dean"
    if "hod" in text or "head" in text:
        return "HOD"
    return "Faculty"


def get_people():
    people = []
    seen = set()

    # 1. Departments first, so those people get their department name
    for school, department, path in DEPARTMENT_PAGES:
        for name, designation in read_faculty(path):
            seen.add((school, name))
            people.append([name, designation, role_from(designation), school, department])
        print("  ", department, "- done")

    # 2. Then whole schools (skipping people already added from a department page).
    #    These people have no department on the website, so the department is the school itself.
    for school, slug in SCHOOL_PAGES:
        count = 0
        for name, designation in read_faculty(slug + "/faculty"):
            if (school, name) in seen:
                continue
            seen.add((school, name))
            people.append([name, designation, role_from(designation), school, school])
            count += 1
        print("  ", school, "-", count, "more")

    # Put people in the same school order as the website
    school_order = [school for school, slug in SCHOOL_PAGES]
    people.sort(key=lambda person: school_order.index(person[3]))

    # Give everyone a simple id: f001, f002, ...
    rows = []
    for i, person in enumerate(people, start=1):
        rows.append(["f%03d" % i] + person + [""])     # cabin is not on the website, left empty
    return rows


def get_programs():
    rows = []
    for school, slug in SCHOOL_PAGES:
        for name, duration in read_programs(slug + "/program"):
            degree, level = degree_of(name)
            rows.append([school, name, degree, level, duration])
        print("  ", school, "- done")
    return rows


def make_demo_timetable(people_rows):
    # The website has no timetables, so make a random one for the demo.
    # Replace data/timetable.csv with the real timetable when you have it.
    random.seed(1)                                   # same timetable every time
    slots = [("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00"),
             ("14:00", "15:00"), ("15:00", "16:00")]
    rows = []
    for person in people_rows:
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            for start, end in sorted(random.sample(slots, 2)):    # 2 classes a day, in time order
                rows.append([person[0], day, start, end, "Class (demo)"])
    return rows


def save_csv(file_name, header, rows):
    path = os.path.join(config.DATA_FOLDER, file_name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print("Saved", len(rows), "rows to", path)


def main():
    print("Reading faculty pages...")
    people_rows = get_people()
    save_csv("people.csv", ["id", "name", "designation", "role", "school", "department", "cabin"], people_rows)

    print("Reading programme pages...")
    save_csv("programs.csv", ["school", "program", "degree", "level", "duration"], get_programs())

    print("Making demo timetable...")
    save_csv("timetable.csv", ["person_id", "day", "start", "end", "activity"], make_demo_timetable(people_rows))


if __name__ == "__main__":
    main()
