# Smart Cabin cabin device - Bluetooth: is one of the owner's phones / laptops near? (same tested logic as
# hardware test 9). Pairing only saves the device's identity: it is never trusted and is disconnected straight
# after pairing, so it can't be used as a keyboard, speaker or anything else. The check is an l2ping: a tiny
# "are you there?" with no service, which works while the device's Bluetooth is on, even when it is locked.

import re
import subprocess
import time

import config
import shared
import storage

MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")
sim_near = set()              # simulation: addresses that "answer"


def run(args, timeout=10):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def start():
    if config.SIMULATE:
        shared.set_sensor("bluetooth", "ok (simulated: use 'Phone near' on the page)")
        return
    run(["rfkill", "unblock", "bluetooth"])
    run(["bluetoothctl", "power", "on"])
    run(["bluetoothctl", "discoverable", "off"])          # only visible during a pairing window
    run(["bluetoothctl", "pairable", "off"])
    check()


def check():
    if config.SIMULATE:
        return True
    if "Powered: yes" in run(["bluetoothctl", "show"]):
        shared.set_sensor("bluetooth", "ok")
        return True
    run(["bluetoothctl", "power", "on"])
    shared.set_sensor("bluetooth", "error: no Bluetooth adapter, or it is off")
    return False


def is_near(address):
    if config.SIMULATE:
        return address in sim_near
    return "bytes from" in run(["l2ping", "-c", "1", "-t", "3", address], 8)


def known_devices(kind=""):
    # [(address, name)] that BlueZ knows; kind "Paired" = only paired ones
    if config.SIMULATE:
        return [("AA:BB:CC:DD:EE:01", "Pixel 7 (simulated)"), ("AA:BB:CC:DD:EE:02", "iPhone (simulated)")] if not kind else []
    found = []
    for line in run(["bluetoothctl", "devices"] + ([kind] if kind else [])).splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2 and parts[0] == "Device" and MAC.match(parts[1].upper()):
            found.append((parts[1].upper(), parts[2] if len(parts) == 3 else parts[1]))
    return found


def keep_identity_only(address):
    # Not trusted, not connected: the pairing only stores who the device is
    run(["bluetoothctl", "untrust", address])
    run(["bluetoothctl", "disconnect", address])
    ours = storage.load("paired_by_us.json", [])
    if address not in ours:
        storage.save("paired_by_us.json", ours + [address])


def pairing_window(on_paired):
    # PAIR_SECONDS: visible + pairable, scans and lists visible devices (shared.state["nearby"]).
    # A device that pairs from its own side is passed to on_paired(address, name).
    before = {a for a, _ in known_devices("Paired")}
    agent = scan = None
    if not config.SIMULATE:
        run(["bluetoothctl", "pairable", "on"])
        run(["bluetoothctl", "discoverable", "on"])
        try:
            agent = subprocess.Popen(["bt-agent", "--capability=NoInputNoOutput"], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)                    # answers "pair?" with yes
            scan = subprocess.Popen(["bluetoothctl", "--timeout", str(config.PAIR_SECONDS), "scan", "on"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
    end = time.time() + config.PAIR_SECONDS
    try:
        while time.time() < end:
            with shared.lock:
                if not shared.state["pairing"]:
                    return                                   # cancelled, or a device was added
            new = [(a, n) for a, n in known_devices("Paired") if a not in before]
            if new:
                on_paired(new[0][0], new[0][1])
                return
            nearby = [{"address": a, "name": n} for a, n in known_devices()
                      if a not in before and n != a and not MAC.match(n.replace("-", ":").upper())]
            with shared.lock:
                shared.state["nearby"] = nearby[:20]
            time.sleep(2)
        shared.set_message("No device paired within " + str(config.PAIR_SECONDS) + " s.")
    finally:
        for process in (scan, agent):
            if process:
                process.terminate()
        if not config.SIMULATE:
            run(["bluetoothctl", "discoverable", "off"])
            run(["bluetoothctl", "pairable", "off"])
        with shared.lock:
            shared.state["pairing"] = False
            shared.state["nearby"] = []


def pair_from_pi(address):
    # The Pi asks the device to pair (works for iPhones). The device shows "Pair?": accept it there.
    if config.SIMULATE:
        return True
    run(["bluetoothctl", "--timeout", "30", "pair", address], 35)
    return "Paired: yes" in run(["bluetoothctl", "info", address])


def forget_removed(addresses_on_server):
    # Phones removed on the faculty page: remove the pairing here too (only pairings this program made)
    ours = storage.load("paired_by_us.json", [])
    for address in [a for a in ours if a not in addresses_on_server]:
        if not config.SIMULATE:
            run(["bluetoothctl", "remove", address])
        ours.remove(address)
    storage.save("paired_by_us.json", ours)
