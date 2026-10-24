# Smart Cabin server - settings. Change values here, not in the code.
import os

FOLDER = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(FOLDER, "smart_cabin.db")

SITE_TITLE = "Smart Cabin"
SITE_SUBTITLE = "Presidency University, Bengaluru"

HOST = "0.0.0.0"              # 0.0.0.0 = reachable from phones and Pis on the same Wi-Fi / hotspot
PORT = 8080

# Logins
SESSION_HOURS = 12            # a browser login lasts this long
PASSWORD_ROUNDS = 200_000     # pbkdf2 rounds: slower = harder to guess, 200 000 takes ~0.1 s
MIN_PASSWORD_LENGTH = 6
SETUP_CODE_MINUTES = 15       # a cabin's 6-digit device code works for this long (fallback way to connect a Pi)

# Automatic device pairing (BUILD_PLAN.md step 9)
BEACON_PORT = 50505           # the server tells Pis where it is with a UDP broadcast on this port ...
BEACON_SECONDS = 2            # ... this often
REQUEST_FORGET_SECONDS = 60   # a waiting Pi that stops saying hello is dropped from the list after this long
ENROL_MINUTES = 10            # after a faculty member logs in on the Pi, setup is allowed for this long

# Status rules (see BUILD_PLAN.md section 4)
STATUS_BUFFER_SECONDS = 10    # a new automatic status must stay the same this long before it is shown
OFFLINE_SECONDS = 60          # no report from the cabin device for this long = grey (unknown)
OVERRIDE_MINUTES = 60         # Available / In a meeting buttons end by themselves after this long
MEETING_END_SECONDS = 20      # "In a meeting" button ends after headcount <= 1 for this long (if it was >= 2)
MAX_BT_DEVICES = 5            # Bluetooth devices per faculty member

# Starter list (BUILD_PLAN.md step 2): only the AI School is imported from the university website list
STARTER_CSV = os.path.join(FOLDER, "..", "..", "..", "laptop codes", "data", "people.csv")
STARTER_SCHOOL = "Presidency School of Artificial Intelligence and Advanced Computing"
STARTER_DEAN = "Dr. Shakkeera L"

# Choices shown on the pages
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
POSITIONS = ["Faculty", "HOD", "Dean"]
AWAY_REASONS = ["Busy", "On a break", "Meeting outside", "On leave"]

# Timetable (BUILD_PLAN.md section 2b)
ACTIVITIES = ["Class", "Lab", "Meeting", "Office hours", "Other"]    # what an hour can be (Free = nothing)
BUILDINGS = [chr(c) for c in range(ord("A"), ord("T") + 1)]         # blocks A ... T
FLOORS = list(range(0, 11))                                         # 0 = ground floor ... 10
ROOM_NUMBERS = list(range(1, 31))                                   # Room / Lab 1 ... 30
CLASS_MINUTES = 50
TEA_MINUTES = 10
LUNCH_MINUTES = 50            # the lunch hour is a numbered hour too
DAY_START = "09:00"
# The order of the day: 8 numbered hours ("hour", and "lunch" which is an hour too) and two tea breaks.
TEMPLATES = {
    "A": ["hour", "hour", "tea", "hour", "hour", "lunch", "hour", "tea", "hour", "hour"],   # lunch = Hour 5
    "B": ["hour", "hour", "tea", "hour", "lunch", "hour", "hour", "tea", "hour", "hour"],   # lunch = Hour 4
}
NUMBERED = ("hour", "lunch")  # slots that have an hour number and can be filled in
