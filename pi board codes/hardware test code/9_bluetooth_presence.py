# Bluetooth presence on a web page: is a user's phone, laptop or watch near the Pi?
# Each user can have 0 to MAX_DEVICES devices. Nothing is typed: the device is paired once from the page.
#
# Why pair? Phones and laptops hide behind random addresses when they are just advertising, so an
# unpaired device can't be recognised again. Pairing once gives the Pi the device's real (fixed) address
# and its keys. After that, the Pi can ask "are you there?" at any time.
#
# Pairing here only SAVES THE IDENTITY. The device is never used as a keyboard, speaker or anything else:
#   - the device is not "trusted", and it is disconnected straight after pairing, so no service can attach
#   - the pairing helper (NoInputNoOutput agent) only runs during the 60 s pairing window
# To check, the Pi sends an l2ping (a tiny "are you there?" at the Bluetooth link level, no service used).
# It works while the device's Bluetooth is on, even with the screen locked.
#
# Only detected, never used as an input or output device:
#   - each check connects once (l2ping) and disconnects straight after
#   - a guard drops (and untrusts) any other connection to the Pi every GUARD_SECONDS, so a device can't
#     use the Pi as a speaker, headset, keyboard or for file transfer
#   - saved devices are untrusted at start, and no agent runs outside pairing, so every service is refused
#
# Adding a device, two ways (both in the same 60 s window):
#   a) Pi asks: on the device open the Bluetooth settings screen (that makes it visible), then press
#      "Pair" next to it in the list on the page, and accept on the device. Works for iPhones too.
#   b) Device asks: on the device choose the Pi's name in its Bluetooth list.
#
# Run:  sudo python3 9_bluetooth_presence.py      then open the address it prints (port 8085)
# sudo is needed for l2ping.
#
# Libraries (once):  sudo apt install -y bluez bluez-tools

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8085
MAX_DEVICES = 5               # per user
PAIR_SECONDS = 60             # how long the Pi is visible and pairable
CHECK_SECONDS = 15            # time between presence rounds
NEAR_SECONDS = 60             # a user is "near" if one of their devices answered within this time
GUARD_SECONDS = 3             # how often other connections to the Pi are looked for and dropped

FOLDER = os.path.dirname(os.path.abspath(__file__))
DEVICES_FILE = os.path.join(FOLDER, "bluetooth_devices.json")
MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")

lock = threading.Lock()
state = {"message": "starting...", "adapter": "?",
         "pairing_user": None, "pairing_until": 0, "nearby": [],   # nearby = devices found while pairing
         "checking": "", "connected": [], "dropped": 0, "last_drop": ""}
last_seen = {}                # address -> time it last answered


# ---------- System commands ----------
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


# ---------- Saved users and devices ----------
def load_users():
    # {user: [{"address": "AA:BB:..", "name": "Pixel 7", "added": "2026-10-24 14:02"}, ...]}
    try:
        with open(DEVICES_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_users():
    with open(DEVICES_FILE, "w") as f:
        json.dump(users, f, indent=1)


users = load_users()


def owner_of(address):
    for user, devices in users.items():
        if any(d["address"] == address for d in devices):
            return user
    return None


# ---------- Bluetooth (BlueZ, through bluetoothctl) ----------
def adapter_ok():
    text = run_command(["bluetoothctl", "show"])
    if "Powered: yes" in text:
        return True
    if "Controller" in text:
        run_command(["bluetoothctl", "power", "on"])
    return False


def known_devices(kind=""):
    # [(address, name)] that bluetoothctl knows. kind "Paired" = only paired ones, "" = also just discovered.
    text = run_command(["bluetoothctl", "devices"] + ([kind] if kind else []))
    found = []
    for line in text.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2 and parts[0] == "Device" and MAC.match(parts[1].upper()):
            name = parts[2] if len(parts) == 3 else parts[1]
            found.append((parts[1].upper(), name))
    return found


def is_paired(address):
    return "Paired: yes" in run_command(["bluetoothctl", "info", address])


def save_identity(user, address, name):
    # Keep the address and keys only: not trusted, and disconnected, so it can't be used as any device
    run_command(["bluetoothctl", "untrust", address])
    run_command(["bluetoothctl", "disconnect", address])
    with lock:
        users.setdefault(user, []).append({"address": address, "name": name, "added": time.strftime("%Y-%m-%d %H:%M")})
        save_users()
        state["message"] = "Saved " + name + " (" + address + ") for " + user + "."
        state["pairing_user"] = None


def pairing_window(user):
    # 60 s: the Pi is visible and pairable, scans for visible devices, and accepts one pairing for this user
    before = {address for address, _ in known_devices("Paired")}
    run_command(["bluetoothctl", "pairable", "on"])
    run_command(["bluetoothctl", "discoverable", "on"])
    agent = start_process(["bt-agent", "--capability=NoInputNoOutput"])     # answers "pair?" with yes
    scan = start_process(["bluetoothctl", "--timeout", str(PAIR_SECONDS), "scan", "on"])
    start = time.time()
    try:
        while time.time() - start < PAIR_SECONDS:
            with lock:
                if state["pairing_user"] != user:       # cancelled, or a device was saved
                    return
            # b) the device paired by itself
            new = [(a, n) for a, n in known_devices("Paired") if a not in before and owner_of(a) is None]
            if new:
                save_identity(user, new[0][0], new[0][1])
                return
            # a) list the visible devices, so the page can offer "Pair"
            nearby = [{"address": a, "name": n} for a, n in known_devices()
                      if a not in before and n != a and not MAC.match(n.replace("-", ":").upper())]
            with lock:
                state["nearby"] = nearby[:20]
            time.sleep(2)
        with lock:
            if state["pairing_user"] == user:
                state["message"] = "No device paired within " + str(PAIR_SECONDS) + " s."
    finally:
        for process in (scan, agent):
            if process:
                process.terminate()
        run_command(["bluetoothctl", "discoverable", "off"])
        run_command(["bluetoothctl", "pairable", "off"])
        with lock:
            if state["pairing_user"] == user:
                state["pairing_user"] = None
            state["nearby"] = []


def pair_from_pi(user, address, name):
    # a) the Pi asks the device to pair. The device shows a "Pair?" question: accept it there.
    with lock:
        state["message"] = "Asking " + name + " to pair - accept on the device..."
    run_command(["bluetoothctl", "--timeout", "30", "pair", address], 35)
    if is_paired(address):
        save_identity(user, address, name)
    else:
        with lock:
            state["message"] = "Pairing with " + name + " failed or wasn't accepted. Try again."


def is_near(address):
    # Connect once, check, disconnect: l2ping opens a link and sends one "are you there?" (no service,
    # no data), then the link is closed straight away instead of waiting for it to time out.
    with lock:
        state["checking"] = address               # the guard leaves this one link alone
    try:
        return "bytes from" in run_command(["l2ping", "-c", "1", "-t", "3", address], 8)
    finally:
        run_command(["bluetoothctl", "disconnect", address])
        with lock:
            state["checking"] = ""


def connected_now():
    # [(address, name)] connected to the Pi right now (checked one by one, so an older bluetoothctl
    # that ignores the "Connected" filter can't cause wrong answers)
    return [(a, n) for a, n in known_devices("Connected")
            if "Connected: yes" in run_command(["bluetoothctl", "info", a])]


def guard_loop():
    # The Pi must never be used as an input or output device: drop every connection except a check
    while True:
        time.sleep(GUARD_SECONDS)
        with lock:
            pairing = state["pairing_user"] is not None
            checking = state["checking"]
        if pairing:                                   # pairing needs its connection for a few seconds
            continue
        found = connected_now()
        for address, name in found:
            if address == checking:
                continue
            run_command(["bluetoothctl", "untrust", address])
            run_command(["bluetoothctl", "disconnect", address])
            with lock:
                state["dropped"] += 1
                state["last_drop"] = name + " at " + time.strftime("%H:%M:%S")
        with lock:
            state["connected"] = [n for a, n in found if a == checking]


def presence_loop():
    while True:
        ok = adapter_ok()
        with lock:
            state["adapter"] = "ready" if ok else "no Bluetooth adapter, or it is off"
            if state["message"] == "starting...":
                state["message"] = "ready"
            pairing = state["pairing_user"] is not None
            plan = {user: [d["address"] for d in devices] for user, devices in users.items()}
        if ok and not pairing:                          # pinging during pairing would disturb it
            for user, addresses in plan.items():
                for address in addresses:
                    if is_near(address):
                        with lock:
                            last_seen[address] = time.time()
                        break                           # one device is enough: skip this user's others
        time.sleep(CHECK_SECONDS)


# ---------- Web page ----------
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bluetooth Presence</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f5f7; color: #222; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .top { color: #555; margin: 0 0 14px; font-size: 14px; }
  .grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); }
  .card { background: #fff; border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  .card h2 { font-size: 17px; margin: 0 0 8px; display: flex; justify-content: space-between; align-items: center; }
  .badge { font-size: 13px; padding: 3px 10px; border-radius: 20px; color: #fff; }
  .near { background: #1a8f3c; } .away { background: #888; }
  .device { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 5px 0;
            border-top: 1px solid #f0f0f0; font-size: 14px; }
  .device small { color: #777; display: block; font-family: monospace; }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; background: #bbb; }
  .dot.on { background: #1a8f3c; }
  button { font-size: 14px; padding: 5px 10px; border: 1px solid #ccc; border-radius: 5px; background: #fff; cursor: pointer; }
  button:hover { background: #eee; }
  button:disabled { color: #aaa; cursor: default; }
  input[type=text] { font-size: 15px; padding: 6px; width: 200px; max-width: 100%; }
  .pairing { background: #fff8e6; border: 1px solid #f0c36d; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; }
  .pairing ol { margin: 6px 0 8px 18px; padding: 0; font-size: 14px; }
  .small { color: #555; font-size: 13px; }
</style></head>
<body>
<h1>Bluetooth Presence</h1>
<p class="top" id="top"></p>
<p class="small" id="guard" style="margin:-8px 0 14px"></p>
<div id="pairing"></div>
<p><input type="text" id="new-user" placeholder="New user, e.g. Dr. Rao"> <button onclick="addUser()">Add user</button></p>
<div class="grid" id="users"></div>
<script>
const esc = t => String(t).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const q = encodeURIComponent;

async function post(url) {
  const r = await fetch(url, {method: "POST"});
  if (!r.ok) alert(await r.text());
  refresh();
}
function addUser() {
  const name = document.getElementById("new-user").value.trim();
  if (name) post("/user/add?user=" + q(name));
  document.getElementById("new-user").value = "";
}
function ago(seconds) {
  if (seconds === null) return "never seen";
  if (seconds < 60) return "seen " + seconds + " s ago";
  if (seconds < 3600) return "seen " + Math.round(seconds / 60) + " min ago";
  return "seen " + Math.round(seconds / 3600) + " h ago";
}

async function refresh() {
  let s;
  try { s = await (await fetch("/status.json")).json(); }
  catch (e) { document.getElementById("top").textContent = "Can't reach the Pi"; return; }

  document.getElementById("top").textContent = "Pi name: " + s.pi_name + " | Bluetooth: " + s.adapter +
    " | checks every " + s.check_seconds + " s | " + s.message;
  const g = s.guard;
  document.getElementById("guard").textContent = "Only detected, never used: the Pi connects for each check " +
    "(about 1 s) and disconnects. Connected now: " + (g.connected.length ? g.connected.join(", ") + " (checking)" : "none") +
    ". Other connections dropped: " + g.dropped + (g.last_drop ? " (last: " + g.last_drop + ")" : "") + ".";

  const p = s.pairing;
  document.getElementById("pairing").innerHTML = !p.user ? "" :
    "<div class='pairing'><b>Adding a device for " + esc(p.user) + "</b> (" + p.seconds_left + " s left) " +
    "<button onclick=\\"post('/pair/cancel')\\">Cancel</button><ol>" +
    "<li>On the device, open the <b>Bluetooth settings</b> screen and keep it open.</li>" +
    "<li>Press <b>Pair</b> next to it below, then accept on the device. " +
    "<i>Or</i> choose <b>" + esc(s.pi_name) + "</b> in the device's own list.</li></ol>" +
    (p.nearby.length ? p.nearby.map(d => "<div class='device'><span>" + esc(d.name) + "<small>" + d.address +
       "</small></span><button onclick=\\"post('/pair/device?address=" + d.address + "&name=" + q(d.name) +
       "')\\">Pair</button></div>").join("") : "<div class='small'>Looking for visible devices...</div>") + "</div>";

  document.getElementById("users").innerHTML = s.users.length ? s.users.map(u =>
    "<div class='card'><h2>" + esc(u.user) + "<span class='badge " + (u.near ? "near'>Near" : "away'>Away") +
    "</span></h2>" +
    (u.devices.length ? u.devices.map(d => "<div class='device'><span><span class='dot" + (d.near ? " on" : "") +
       "'></span>" + esc(d.name) + "<small>" + d.address + " - " + ago(d.seen_ago) + "</small></span>" +
       "<button onclick=\\"if (confirm('Remove " + esc(d.name.replace(/['"\\\\]/g, "")) + "?')) post('/device/remove?address=" + d.address + "')\\">Remove</button></div>").join("")
     : "<div class='small'>No devices yet.</div>") +
    "<p style='margin:10px 0 0'><button " + (u.devices.length >= s.max_devices || p.user ? "disabled " : "") +
    "data-user='" + esc(u.user) + "' onclick='post(\\"/pair/start?user=\\" + q(this.dataset.user))'>Add device</button> " +
    "<button data-user='" + esc(u.user) + "' onclick='if (confirm(\\"Delete user \\" + this.dataset.user + \\" and their devices?\\")) " +
    "post(\\"/user/delete?user=\\" + q(this.dataset.user))'>Delete user</button>" +
    " <span class='small'>" + u.devices.length + " / " + s.max_devices + "</span></p></div>").join("")
    : "<p class='small'>No users yet. Add one above.</p>";
}

refresh();
setInterval(refresh, 1500);
</script>
</body></html>
"""


def status():
    now = time.time()
    with lock:
        user_list = []
        for user, devices in sorted(users.items()):
            shown = []
            for d in devices:
                seen = last_seen.get(d["address"])
                shown.append({"address": d["address"], "name": d["name"],
                              "seen_ago": None if seen is None else round(now - seen),
                              "near": seen is not None and now - seen < NEAR_SECONDS})
            user_list.append({"user": user, "devices": shown, "near": any(d["near"] for d in shown)})
        pairing = {"user": state["pairing_user"], "seconds_left": max(0, round(state["pairing_until"] - now)),
                   "nearby": state["nearby"]}
        guard = {"connected": state["connected"], "dropped": state["dropped"], "last_drop": state["last_drop"]}
        return {"users": user_list, "pairing": pairing, "message": state["message"], "adapter": state["adapter"],
                "guard": guard,
                "pi_name": socket.gethostname(), "max_devices": MAX_DEVICES, "check_seconds": CHECK_SECONDS}


def handle_action(path, query):
    # Returns (ok, text)
    user = query.get("user", [""])[0].strip()[:60]
    address = query.get("address", [""])[0].upper()
    with lock:
        if path == "/user/add":
            if not user:
                return False, "Type a name"
            users.setdefault(user, [])
            save_users()
            return True, "ok"
        if path == "/user/delete" and user in users:
            for d in users.pop(user):
                run_command(["bluetoothctl", "remove", d["address"]])     # forget the pairing too
            save_users()
            return True, "ok"
        if path == "/device/remove" and MAC.match(address):
            owner = owner_of(address)
            if owner is None:
                return False, "Unknown device"
            users[owner] = [d for d in users[owner] if d["address"] != address]
            save_users()
            run_command(["bluetoothctl", "remove", address])
            return True, "ok"
        if path == "/pair/start" and user in users:
            if state["pairing_user"]:
                return False, "Already adding a device for " + state["pairing_user"]
            if len(users[user]) >= MAX_DEVICES:
                return False, user + " already has " + str(MAX_DEVICES) + " devices"
            state.update(pairing_user=user, pairing_until=time.time() + PAIR_SECONDS, nearby=[],
                         message="Adding a device for " + user + "...")
            threading.Thread(target=pairing_window, args=(user,), daemon=True).start()
            return True, "ok"
        if path == "/pair/device" and MAC.match(address) and state["pairing_user"]:
            name = query.get("name", [address])[0][:60]
            threading.Thread(target=pair_from_pi, args=(state["pairing_user"], address, name), daemon=True).start()
            return True, "ok"
        if path == "/pair/cancel":
            state["pairing_user"] = None
            state["message"] = "Adding a device was cancelled."
            return True, "ok"
    return False, "bad request"


class Handler(BaseHTTPRequestHandler):
    def send(self, body, content_type, code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send(PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/status.json":
            self.send(json.dumps(status()).encode(), "application/json")
        else:
            self.send(b"not found", "text/plain", 404)

    def do_POST(self):
        url = urlparse(self.path)
        ok, text = handle_action(url.path, parse_qs(url.query))
        self.send(text.encode(), "text/plain", 200 if ok else 400)

    def log_message(self, *args):
        pass                                          # keep the terminal quiet


def my_address():
    # The IP address other devices on the network use to reach this Pi
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))                    # nothing is sent, this only picks the network
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def main():
    if not run_command(["which", "bluetoothctl"]):
        sys.exit("bluetoothctl missing:  sudo apt install -y bluez bluez-tools")
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("Note: not running with sudo, so l2ping can't check devices. Use: sudo python3 9_bluetooth_presence.py")
    run_command(["rfkill", "unblock", "bluetooth"])
    run_command(["bluetoothctl", "power", "on"])
    run_command(["bluetoothctl", "discoverable", "off"])     # only visible during a pairing window
    run_command(["bluetoothctl", "pairable", "off"])
    for devices in users.values():                          # untrusted = every service needs permission,
        for d in devices:                                   # and with no agent running it is refused
            run_command(["bluetoothctl", "untrust", d["address"]])
            run_command(["bluetoothctl", "disconnect", d["address"]])

    threading.Thread(target=presence_loop, daemon=True).start()
    threading.Thread(target=guard_loop, daemon=True).start()

    server = ThreadingHTTPServer(("", PORT), Handler)
    print("Bluetooth presence page:")
    print("  http://" + my_address() + ":" + str(PORT))
    print("  http://" + socket.gethostname() + ".local:" + str(PORT))
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
