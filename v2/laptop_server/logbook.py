# Smart Cabin laptop server - the log.
#   log        : every message goes to logs/server.log and to the terminal
#   event()    : something worth keeping (arrive, leave, registration, error) also goes to events_log.csv
#   recent()   : the newest lines of server.log, for the Devices page

import logging
import os
import time

import csv_store
import settings

EVENT_COLUMNS = ["time", "kind", "device", "person_id", "message"]

os.makedirs(settings.LOG_FOLDER, exist_ok=True)
LOG_FILE = os.path.join(settings.LOG_FOLDER, "server.log")

log = logging.getLogger("smartcabin")
log.setLevel(logging.INFO)
if not log.handlers:
    form = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(form)
        log.addHandler(handler)


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def event(kind, message, device="", person_id=""):
    log.info("%s: %s %s %s", kind, message, device, person_id)
    try:
        csv_store.append("events_log.csv", {"time": now_text(), "kind": kind, "device": device,
                                            "person_id": person_id, "message": message}, EVENT_COLUMNS)
    except Exception as error:
        log.error("could not write events_log.csv: %s", error)


def recent(count=150):
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            return f.readlines()[-count:]
    except OSError as error:
        return ["could not read the log: " + str(error)]
