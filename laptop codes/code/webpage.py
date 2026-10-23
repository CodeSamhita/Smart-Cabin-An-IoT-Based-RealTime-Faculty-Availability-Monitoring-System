# Connects Python to the web page.
# Python writes web/data.js, and the page reads it. No web server is needed.

import json
import os
import time
import webbrowser

import config
import people


def build_site_data(people_list, timetable, statuses, sensors, history, programs):
    # Put everything the web page needs into one dictionary
    everyone = []
    for person in people_list:
        entry = dict(person)                                   # id, name, designation, role, school, department, cabin
        entry.update(statuses[person["id"]])                   # status, reason, expected_back, ...
        entry["timetable"] = people.timetable_for(person["id"], timetable)
        everyone.append(entry)

    return {
        "title": config.SITE_TITLE,
        "subtitle": config.COLLEGE_NAME,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "people": everyone,
        "sensors": sensors,
        "history": history,
        "programs": programs,
    }


def write_status(data):
    # Save the data as a JavaScript variable so the pages can load it with <script src="data.js">
    # No extra spaces or new lines, to keep the file small (about 840 people)
    text = "var SMART_CABIN = " + json.dumps(data, indent=None) + ";\n"

    # Write to a temporary file first, then swap it in, so the page never reads a half-written file
    path = os.path.join(config.WEB_FOLDER, "data.js")
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(text)

    # On Windows the swap fails if the browser is reading data.js at that moment, so try a few times
    for attempt in range(10):
        try:
            os.replace(temp_path, path)
            return
        except PermissionError:
            time.sleep(0.2)
    print("Could not update data.js this time (file busy). Will try again next cycle.")


def open_dashboard():
    # Open the home page in the default browser
    page = os.path.join(config.WEB_FOLDER, "index.html")
    webbrowser.open("file:///" + page.replace("\\", "/"))
