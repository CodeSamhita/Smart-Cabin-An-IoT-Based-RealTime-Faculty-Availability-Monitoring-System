# Smart Cabin laptop server - every setting in one place. Change values here, not in the code.

import os

FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(FOLDER, "data")          # all the CSV files
LOG_FOLDER = os.path.join(FOLDER, "logs")
PAGES_FOLDER = os.path.join(FOLDER, "pages")          # one folder per page, plus pages/common/
CERT_FILE = os.path.join(FOLDER, "certificate", "server_cert.pem")   # made at the first start
KEY_FILE = os.path.join(FOLDER, "certificate", "server_key.pem")

PORT = 8080
USE_HTTPS = True               # False only for a quick test; the Pis expect https

SILENT_SECONDS = 60            # a device that sent nothing for this long = Unknown
SESSION_HOURS = 12             # admin login lasts this long
PIN_MINUTES = 15               # a setup PIN for registration is valid this long
PASSWORD_ROUNDS = 200000       # PBKDF2 rounds for the admin password
MAX_BODY_BYTES = 256 * 1024    # bigger requests are refused (the Faculty logins table of ~840 people is ~50 KB)
PUBLIC_LIMIT = 60              # the public page shows at most this many people per search

# Faculty logins
FACULTY_SESSION_HOURS = 12     # a faculty login lasts this long
DEFAULT_PASSWORD_DAYS = (1, 3, 7, 14)    # how long the admin's default password may work (the admin picks one)

# The university's periods (section timetable, odd semester 2026-27). Short breaks after period 2 and after period 6
# are the same for everyone; lunch is an entry in each person's timetable.
PERIODS = {1: ("08:50", "09:45"), 2: ("09:45", "10:40"), 3: ("10:50", "11:45"), 4: ("11:45", "12:35"),
           5: ("12:35", "13:25"), 6: ("13:25", "14:20"), 7: ("14:30", "15:25"), 8: ("15:25", "16:15")}
BREAKS = (("10:40", "10:50"), ("14:20", "14:30"))
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
