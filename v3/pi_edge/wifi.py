# Smart Cabin edge device - the Wi-Fi networks this Pi knows (NetworkManager, through nmcli).
#   view()    : the saved networks (in use, in range, signal), cached for a few seconds
#   add()     : a network with a password, or campus Wi-Fi with a username + password (WPA2-Enterprise, e.g. eduroam)
#   remove()  : forget a network - never the setup network from flashing, never the one in use right now
#   loop()    : thread. NetworkManager does not leave a working network by itself, so every minute: if a setup
#               network (the laptop hotspot) is in range but another one is in use, switch back to the hotspot.
# Setup networks = the ones set when flashing (every network not added on this page, see settings.WIFI_PREFIX). They
# get the highest priority, so the laptop hotspot is used whenever it is on; campus Wi-Fi is used otherwise.
# Passwords stay with NetworkManager (root-only files): they are never shown again and never sent to the server.

import re
import subprocess
import threading
import time

import notify
import settings
import shared
from logbook import log
from registration import PageError

SETUP_PRIORITY = 10              # the laptop hotspot first
OTHER_PRIORITY = 5               # campus Wi-Fi and any other network
cache = {"at": 0.0, "view": None}
lock = threading.Lock()


def nmcli(*args, timeout=20):
    # Runs nmcli with a list of arguments (no shell, so names and passwords can't inject anything)
    result = subprocess.run(["nmcli"] + list(args), capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise PageError((result.stderr or result.stdout).strip().replace("Error: ", "") or "nmcli failed")
    return result.stdout


def fields(line):
    # One line of `nmcli -t` output: fields split at ":" that is not escaped as "\:"
    return [f.replace("\\:", ":").replace("\\\\", "\\") for f in re.split(r"(?<!\\):", line)]


def available():
    return settings.ON_PI and not settings.SIMULATE


def is_setup(name):
    # A network set when flashing (not added on this page)
    return not name.startswith(settings.WIFI_PREFIX)


def saved():
    # [{name, ssid, priority, active}] for every saved Wi-Fi connection
    networks = []
    for line in nmcli("-t", "-f", "NAME,TYPE,AUTOCONNECT-PRIORITY,ACTIVE", "connection", "show").splitlines():
        parts = fields(line)
        if len(parts) < 4 or parts[1] != "802-11-wireless":
            continue
        ssid = nmcli("-g", "802-11-wireless.ssid", "connection", "show", parts[0]).strip() or parts[0]
        networks.append({"name": parts[0], "ssid": ssid, "priority": int(parts[2] or 0), "active": parts[3] == "yes"})
    return networks


def in_range():
    # {ssid: signal %} of the networks the Pi can see now (from its last scan; no new scan, so it is quick)
    seen = {}
    for line in nmcli("-t", "-f", "SSID,SIGNAL", "device", "wifi", "list", "--rescan", "no").splitlines():
        parts = fields(line)
        if len(parts) >= 2 and parts[0]:
            seen[parts[0]] = max(seen.get(parts[0], 0), int(parts[1] or 0))
    return seen


def view():
    if not available():
        return {"present": False, "message": "no Wi-Fi settings on this computer (" + settings.COMPUTER + ")", "networks": []}
    with lock:
        if cache["view"] and time.time() - cache["at"] < 5:
            return cache["view"]
        try:
            seen = in_range()
            networks = [dict(n, setup=is_setup(n["name"]), signal=seen.get(n["ssid"]),
                             in_range=n["ssid"] in seen) for n in saved()]
            networks.sort(key=lambda n: (not n["setup"], -n["priority"], n["ssid"].lower()))
            result = {"present": True, "message": "", "networks": networks}
        except (OSError, subprocess.SubprocessError, PageError) as problem:
            result = {"present": True, "message": "could not read the Wi-Fi settings: " + str(problem), "networks": []}
        cache.update(at=time.time(), view=result)
        return result


def allowed():
    # Changes need the registered person at the device (face or registered card in the last 2 minutes);
    # before anyone is registered here, anyone at the device page may do it (the setup)
    import person_data
    import registration
    local = registration.local_person()
    if local and registration.approval(local) == "approved" and not person_data.at_device():
        raise PageError("Show your face to the camera or tap your card first, then try again within 2 minutes.")


def setup_first():
    # The setup networks (the laptop hotspot) get the highest priority, so they are used whenever they are on
    try:
        for n in saved():
            if is_setup(n["name"]) and n["priority"] != SETUP_PRIORITY:
                nmcli("connection", "modify", n["name"], "connection.autoconnect-priority", str(SETUP_PRIORITY))
    except (OSError, subprocess.SubprocessError, PageError) as problem:
        log.warning("wifi: could not give the setup network the first place: %s", problem)


def add(ssid, password, username=""):
    if not available():
        raise PageError("This computer has no Wi-Fi settings to change (" + settings.COMPUTER + ").")
    allowed()
    ssid, username = str(ssid or "").strip(), str(username or "").strip()
    password = str(password or "")
    if not 1 <= len(ssid) <= 32:
        raise PageError("Type the Wi-Fi name (1 to 32 characters).")
    if not 8 <= len(password) <= 63 and not username:
        raise PageError("The Wi-Fi password must be 8 to 63 characters.")
    if username and not password:
        raise PageError("Type the password that goes with the username.")
    if any(n["ssid"] == ssid for n in saved()):
        raise PageError("\"" + ssid + "\" is already saved. Remove it first to change its password.")
    setup_first()
    name = settings.WIFI_PREFIX + ssid
    args = ["connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", name, "ssid", ssid,
            "connection.autoconnect", "yes", "connection.autoconnect-priority", str(OTHER_PRIORITY)]
    if username:                                       # campus Wi-Fi: WPA2-Enterprise, PEAP + MSCHAPv2 (eduroam style)
        args += ["wifi-sec.key-mgmt", "wpa-eap", "802-1x.eap", "peap", "802-1x.phase2-auth", "mschapv2",
                 "802-1x.identity", username, "802-1x.password", password]
    else:
        args += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    nmcli(*args)
    cache["view"] = None
    log.info("wifi: saved the network %s%s", ssid, " (username + password)" if username else "")
    notify.event("changed")
    return "\"" + ssid + "\" saved. The Pi uses it when the laptop hotspot is not on."


def remove(name):
    if not available():
        raise PageError("This computer has no Wi-Fi settings to change (" + settings.COMPUTER + ").")
    allowed()
    network = next((n for n in saved() if n["name"] == name), None)
    if network is None:
        raise PageError("No saved network with that name.")
    if is_setup(network["name"]):
        raise PageError("The setup network (the laptop hotspot from flashing) can't be removed, so the Pi can always be reached.")
    if network["active"]:
        raise PageError("\"" + network["ssid"] + "\" is in use right now. Remove it while the Pi is on another network.")
    nmcli("connection", "delete", name)
    cache["view"] = None
    log.info("wifi: removed the network %s", network["ssid"])
    notify.event("changed")
    return "\"" + network["ssid"] + "\" removed."


def loop():
    # Back to the laptop hotspot when it is on again (NetworkManager would stay on campus Wi-Fi otherwise)
    if not available():
        return
    setup_first()
    while True:
        time.sleep(60)
        try:
            networks = saved()
            if any(n["active"] and is_setup(n["name"]) for n in networks) or not any(n["active"] for n in networks):
                continue                                   # on the hotspot already, or not connected (NetworkManager retries)
            seen = in_range()
            setup = next((n for n in networks if is_setup(n["name"]) and n["ssid"] in seen), None)
            if setup:
                log.info("wifi: the laptop hotspot %s is on again: switching to it", setup["ssid"])
                nmcli("connection", "up", setup["name"], timeout=40)
                cache["view"] = None
                shared.changed.set()
        except Exception as problem:
            log.warning("wifi check: %s", problem)
