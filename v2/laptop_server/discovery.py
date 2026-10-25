# Smart Cabin laptop server - lets the Pis find this server by themselves.
# Every 2 s it sends a small UDP broadcast on port 50505, on each network the laptop is on:
#   SMARTCABIN https://<this laptop's address on that network>:8080
# A Pi that hears it uses that address (see pi_edge/server_link.py). Nothing secret is sent: the Pi still checks
# the server's certificate, so a fake announcement can't take over a device.

import socket
import threading
import time

import logbook
import security
import settings

PORT = 50505
EVERY_SECONDS = 2


def announce_forever():
    scheme = "https" if settings.USE_HTTPS else "http"
    warned = set()
    while True:
        for address in security.laptop_addresses():
            if address.startswith("127."):
                continue
            message = ("SMARTCABIN " + scheme + "://" + address + ":" + str(settings.PORT)).encode()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.bind((address, 0))                          # send out of the network that has this address
                    s.sendto(message, ("255.255.255.255", PORT))
            except OSError as error:
                if address not in warned:                         # say it once, not every 2 s
                    warned.add(address)
                    logbook.log.warning("could not announce the server on %s: %s", address, error)
        time.sleep(EVERY_SECONDS)


def start():
    threading.Thread(target=announce_forever, name="discovery", daemon=True).start()
