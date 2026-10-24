# Smart Cabin server - run this on the laptop:   python main.py
#
# What it does:
#   1. installs FastAPI, uvicorn and Jinja2 the first time (install.py). SQLite needs nothing.
#   2. creates the database file smart_cabin.db if it isn't there yet
#   3. starts three things at once:
#        - a timer thread: every few seconds it updates every status (devices that go quiet turn grey,
#          buttons that expire end, the 10 s buffer finishes, old "notify me" watches end)
#        - a beacon thread: tells new Pis where this server is (UDP broadcast, port 50505)
#        - the web server: pages for people, and the API for the cabin devices (port 8080)
#   4. prints the addresses to open, and opens the status page in the browser
#
# Ctrl+C stops it. The API for the cabin devices is listed (and can be tried) at /docs.

import install

install.install_missing()                          # before importing FastAPI

import json                                       # noqa: E402
import socket                                     # noqa: E402
import threading                                  # noqa: E402
import time                                       # noqa: E402
import webbrowser                                 # noqa: E402

import uvicorn                                    # noqa: E402
from fastapi import FastAPI                       # noqa: E402
from fastapi.staticfiles import StaticFiles       # noqa: E402

import api_account                                # noqa: E402
import api_admin                                  # noqa: E402
import api_device                                 # noqa: E402
import api_faculty                                # noqa: E402
import api_public                                 # noqa: E402
import api_timetable                              # noqa: E402
import config                                     # noqa: E402
import database                                   # noqa: E402
import pages                                      # noqa: E402
import status_engine                              # noqa: E402

app = FastAPI(title="Smart Cabin", description="Faculty availability. The cabin devices use the /api/device/... calls.")
app.mount("/static", StaticFiles(directory=config.FOLDER + "/static"), name="static")
for part in (pages, api_account, api_public, api_admin, api_faculty, api_timetable, api_device):
    app.include_router(part.router)


def status_timer():
    # Thread 1: keeps every status up to date, even when no device is reporting
    last_cleanup = 0
    while True:
        try:
            status_engine.refresh_all()
            if time.time() - last_cleanup > 3600:
                api_faculty.end_old_watches()
                last_cleanup = time.time()
        except Exception as error:                 # never let one bad row stop the timer
            print("Status timer problem:", error)
        time.sleep(5)


def beacon():
    # Thread 2: tells Pis where the server is (BUILD_PLAN.md step 9). Every 2 s, on every network of this
    # laptop, a small UDP broadcast carries that network's own address, e.g. http://192.168.137.1:8080.
    while True:
        for address in laptop_addresses():
            message = json.dumps({"smartcabin": "server", "url": "http://" + address + ":" + str(config.PORT)}).encode()
            broadcast = ".".join(address.split(".")[:3]) + ".255"          # e.g. 192.168.137.255 (a /24 network)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.bind((address, 0))                                     # send out through that network
                    for target in (broadcast, "255.255.255.255"):
                        s.sendto(message, (target, config.BEACON_PORT))
            except OSError:
                pass                                                         # a network that just went away
        time.sleep(config.BEACON_SECONDS)


def laptop_addresses():
    # Every IPv4 address of this laptop (Wi-Fi, hotspot ...), so phones and the Pi know where to connect
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in addresses if not a.startswith("127."))


def main():
    database.create_tables()
    threading.Thread(target=status_timer, daemon=True).start()
    threading.Thread(target=beacon, daemon=True).start()

    print()
    print("Smart Cabin server is starting. Open:")
    print("  on this laptop :  http://localhost:" + str(config.PORT))
    for address in laptop_addresses():
        print("  phones / Pi    :  http://" + address + ":" + str(config.PORT))
    print("  API for devices:  http://localhost:" + str(config.PORT) + "/docs")
    print("Windows may ask to allow Python on the network: allow it on Private networks.")
    print("Ctrl+C stops the server.")
    print()
    threading.Timer(2, lambda: webbrowser.open("http://localhost:" + str(config.PORT))).start()
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
