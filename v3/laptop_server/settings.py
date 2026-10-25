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
MAX_BODY_BYTES = 64 * 1024     # bigger requests are refused
PUBLIC_LIMIT = 60              # the public page shows at most this many people per search
