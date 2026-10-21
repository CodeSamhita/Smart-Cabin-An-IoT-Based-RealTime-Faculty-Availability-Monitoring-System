# Settings for Smart Cabin. Change values here, not inside the other files.

import os

PROJECT_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Folder where the web page lives
WEB_FOLDER = os.path.join(PROJECT_FOLDER, "web")

# Folder with the CSV files (people.csv and timetable.csv). Edit them in Excel.
DATA_FOLDER = os.path.join(PROJECT_FOLDER, "data")

# Name shown at the top of the web page
SITE_TITLE = "Smart Cabin"
COLLEGE_NAME = "Presidency University, Bengaluru"

# Demo mode: seconds between status changes, and how many people change each time
DEMO_SECONDS = 10
CHANGES_PER_CYCLE = 5
