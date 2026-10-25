# Bluetooth registration: pair the user's phone / laptop / watch once, so the Pi can recognise it later.
# Only the identity is kept. The Pi is never used as a speaker, headset, keyboard or for file transfer:
#   - after pairing the device is untrusted and disconnected
#   - a guard drops (and untrusts) any connection to the Pi every GUARD_SECONDS, except while pairing
#   - no pairing agent runs outside the pairing window, so an untrusted device's requests are refused
import re
import subprocess
import time

import config
import shared
import storage

MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def run_command(args, timeout=10):
    # Run a command and return what it printed ("" if it failed or took too long)
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def start_process(args):
    # Start a command that keeps running in the background (scan, pairing agent)
    try:
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None


def known_devices(kind=""):
    # [(address, name)] that bluetoothctl knows. kind "Paired" / "Connected" filters, "" = also just seen.
    found = []
    for line in run_command(["bluetoothctl", "devices"] + ([kind] if kind else [])).splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2 and parts[0] == "Device" and MAC.match(parts[1].upper()):
            found.append((parts[1].upper(), parts[2] if len(parts) == 3 else parts[1]))
    return found


def forget(address):
    # Unpair a device (Cancel, Delete user)
    if not config.SIM:
        run_command(["bluetoothctl", "remove", address])


def keep_identity(address, name):
    # A device was paired for the registration: keep only its identity
    if not config.SIM:
        run_command(["bluetoothctl", "untrust", address])
        run_command(["bluetoothctl", "disconnect", address])
    with shared.lock:
        shared.state["pairing"] = False
        owner = storage.device_owner(address)
        if owner:
            shared.say(name + " is already registered to " + owner + ". Not kept.")
        elif any(d["address"] == address for d in shared.draft["devices"]):
            shared.say(name + " is already in this registration.")
        else:
            shared.draft["devices"].append({"address": address, "name": name})
            shared.say(name + " (" + address + ") recorded.")


def pairing_window():
    # PAIR_SECONDS: the Pi is visible and pairable, lists visible devices, and accepts one pairing
    if config.SIM:
        with shared.lock:
            shared.state["nearby"] = [{"address": "AA:BB:CC:00:00:0" + str(n), "name": name + " (simulated)"}
                                      for n, name in enumerate(["Pixel 7", "iPhone 13", "Galaxy Watch"], 1)]
        while shared.state["pairing"] and time.time() < shared.state["pairing_until"]:
            time.sleep(0.5)
        with shared.lock:
            shared.state.update(pairing=False, nearby=[])
        return

    before = {address for address, _ in known_devices("Paired")}
    run_command(["bluetoothctl", "pairable", "on"])
    run_command(["bluetoothctl", "discoverable", "on"])
    agent = start_process(["bt-agent", "--capability=NoInputNoOutput"])     # answers "pair?" with yes
    scan = start_process(["bluetoothctl", "--timeout", str(config.PAIR_SECONDS), "scan", "on"])
    try:
        while time.time() < shared.state["pairing_until"]:
            if not shared.state["pairing"]:                 # cancelled, or a device was kept
                return
            new = [(a, n) for a, n in known_devices("Paired") if a not in before]
            if new:                                         # the device paired by itself (picked the Pi)
                keep_identity(new[0][0], new[0][1])
                return
            nearby = [{"address": a, "name": n} for a, n in known_devices()
                      if a not in before and n != a and not MAC.match(n.replace("-", ":").upper())]
            with shared.lock:
                shared.state["nearby"] = nearby[:20]
            time.sleep(2)
        with shared.lock:
            if shared.state["pairing"]:
                shared.say("No device paired within " + str(config.PAIR_SECONDS) + " s.")
    finally:
        for process in (scan, agent):
            if process:
                process.terminate()
        run_command(["bluetoothctl", "discoverable", "off"])
        run_command(["bluetoothctl", "pairable", "off"])
        with shared.lock:
            shared.state.update(pairing=False, nearby=[])


def pair_from_pi(address, name):
    # The Pi asks the device to pair. The device shows "Pair?": accept it there.
    with shared.lock:
        shared.say("Asking " + name + " to pair - accept on the device...")
    if config.SIM:
        time.sleep(1)
        return keep_identity(address, name)
    run_command(["bluetoothctl", "--timeout", "30", "pair", address], 35)
    if "Paired: yes" in run_command(["bluetoothctl", "info", address]):
        keep_identity(address, name)
    else:
        with shared.lock:
            shared.say("Pairing with " + name + " failed or wasn't accepted. Try again.")


def guard_loop():
    # Detect-only: drop every connection to the Pi, except during the pairing window
    while True:
        time.sleep(config.GUARD_SECONDS)
        if shared.state["pairing"]:
            continue
        for address, name in known_devices("Connected"):
            if "Connected: yes" not in run_command(["bluetoothctl", "info", address]):
                continue                                    # an older bluetoothctl ignored the filter
            run_command(["bluetoothctl", "untrust", address])
            run_command(["bluetoothctl", "disconnect", address])
            with shared.lock:
                shared.state["dropped"] += 1


def start():
    # Called once from main.py. Returns True if Bluetooth works.
    if config.SIM:
        with shared.lock:
            shared.state.update(phone_ok=True, phone_text="simulated Bluetooth")
        return True
    if not run_command(["which", "bluetoothctl"]) or not run_command(["which", "bt-agent"]):
        with shared.lock:
            shared.state["phone_text"] = "Bluetooth not working: sudo apt install -y bluez bluez-tools"
        return False
    run_command(["rfkill", "unblock", "bluetooth"])
    run_command(["bluetoothctl", "power", "on"])
    run_command(["bluetoothctl", "discoverable", "off"])    # only visible while adding a device
    run_command(["bluetoothctl", "pairable", "off"])
    for address in storage.all_device_addresses():           # registered devices stay untrusted
        run_command(["bluetoothctl", "untrust", address])
    with shared.lock:
        shared.state.update(phone_ok=True, phone_text="ready")
    return True
