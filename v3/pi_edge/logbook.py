# Smart Cabin edge device - the log: every message goes to logs/edge.log and to the terminal.
# recent() gives the newest lines for the device's own page.

import logging
import os

import settings

os.makedirs(settings.LOG_FOLDER, exist_ok=True)
LOG_FILE = os.path.join(settings.LOG_FOLDER, "edge.log")

log = logging.getLogger("edge")
log.setLevel(logging.INFO)
if not log.handlers:
    form = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(form)
        log.addHandler(handler)


def recent(count=60):
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            return f.readlines()[-count:]
    except OSError as error:
        return ["could not read the log: " + str(error)]
