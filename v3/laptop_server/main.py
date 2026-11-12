# Smart Cabin laptop server - start it with:   python main.py
# The welcome page opens by itself in the default browser (python main.py --no-browser to stop that).
#   public page : https://localhost:8080          (anyone, no login)
#   devices page: https://localhost:8080/devices  (admin; the admin account is made on the first visit,
#                                                  from this laptop only)
# The browser warns about the certificate the first time (it is self-signed): choose "Advanced" ->
# "Continue". Stop the server with Ctrl+C.
#   python main.py --http   runs without HTTPS, only for troubleshooting (the Pis will not connect)
#   python main.py --port 8090   another port
#   python main.py --data D:\test_data   another data folder (its own CSV files and log), e.g. for trying things out
#                                        without touching the real data

import os
import shutil
import sys
import threading
import webbrowser

import settings

if "--http" in sys.argv:
    settings.USE_HTTPS = False
if "--port" in sys.argv and sys.argv.index("--port") + 1 < len(sys.argv):
    settings.PORT = int(sys.argv[sys.argv.index("--port") + 1])
if "--data" in sys.argv and sys.argv.index("--data") + 1 < len(sys.argv):
    settings.DATA_FOLDER = os.path.abspath(sys.argv[sys.argv.index("--data") + 1])
    settings.LOG_FOLDER = os.path.join(settings.DATA_FOLDER, "logs")

import discovery
import logbook
import security
import web

STARTER_FILES = ["people.csv", "programs.csv"]   # timetables come from import_timetable.py, not a starter file
STARTER_FOLDER = os.path.join(settings.FOLDER, "..", "..", "laptop codes", "data")   # the earlier data folder


def check_data():
    os.makedirs(settings.DATA_FOLDER, exist_ok=True)
    for name in STARTER_FILES:
        target = os.path.join(settings.DATA_FOLDER, name)
        source = os.path.join(STARTER_FOLDER, name)
        if not os.path.exists(target) and os.path.exists(source):
            shutil.copy(source, target)
            logbook.log.info("copied %s from laptop codes/data", name)
        if not os.path.exists(target):
            logbook.log.error("MISSING data/%s - the public page needs it", name)


def open_home_page(url):
    # Opens the welcome page in the laptop's default browser. The first time, the browser warns about the
    # self-signed certificate: "Advanced" -> "Continue".
    try:
        if not webbrowser.open(url):
            print("Could not open a browser by itself. Open this yourself: " + url)
    except Exception as error:
        logbook.log.warning("could not open the browser: %s - open %s yourself", error, url)


def main():
    check_data()
    try:
        server = web.start()
    except OSError as error:
        sys.exit("Could not start on port " + str(settings.PORT) + ": " + str(error)
                 + "\nIs the server already running in another window?")
    scheme = "https" if settings.USE_HTTPS else "http"
    discovery.start()                                    # the Pis find this server by its broadcast
    logbook.log.info("Smart Cabin server started")
    print("\nOpen on this laptop:   " + scheme + "://localhost:" + str(settings.PORT))
    print("Devices (admin):       " + scheme + "://localhost:" + str(settings.PORT) + "/devices")
    for address in security.laptop_addresses():
        if address != "127.0.0.1":
            print("From a phone / Pi:     " + scheme + "://" + address + ":" + str(settings.PORT))
    if not security.admin_exists():
        print("\nNo admin account yet: open the Devices page on THIS laptop to make one.")
    print("Log: " + logbook.LOG_FILE + "\nStop with Ctrl+C\n")
    if "--no-browser" not in sys.argv:
        home = scheme + "://localhost:" + str(settings.PORT) + "/"
        threading.Timer(1.0, open_home_page, args=[home]).start()      # a moment later, so the server is listening
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
