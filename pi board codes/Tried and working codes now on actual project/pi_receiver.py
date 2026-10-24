# Smart Cabin - receive the status sent by the Raspberry Pi(s).
#
# It announces this laptop on the Wi-Fi with mDNS as "_smartcabin._tcp", so pi_sender.py on the Pi
# finds it by itself - no IP addresses to type. Each Pi sends its status every few seconds.
# Everything received is shown on a web page and saved to pi_status.json (in this folder).
#
# Run:  python pi_receiver.py      then open http://localhost:8500
# The first time, Windows may ask to allow Python on the network: allow it on Private networks.

import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------- Settings you can tune ----------------
PORT = 8500
TOKEN = "smartcabin-2026"                          # must be the same in pi_sender.py on the Pi
SERVICE_TYPE = "_smartcabin._tcp.local."           # the mDNS name the Pi looks for
OFFLINE_SECONDS = 15                               # a Pi is "offline" if nothing came for this long
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pi_status.json")
# --------------------------------------------------------


def install_missing_libraries():
    try:
        import zeroconf  # noqa: F401
    except ImportError:
        print("Installing zeroconf (mDNS library)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "zeroconf"], check=True)


install_missing_libraries()
from zeroconf import ServiceInfo, Zeroconf  # noqa: E402

lock = threading.Lock()
pis = {}      # device name -> {"received": time, "message": what the Pi sent}


def my_ip():
    # The address the Pi can use to reach this laptop (the Wi-Fi one, not VPN / virtual adapters)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))     # no data is sent, it only picks the right network card
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def all_ips():
    # Every IPv4 address of this laptop (Wi-Fi, LAN, mobile hotspot ...), the main one first.
    # The Pi picks the one on its own network.
    ips = [my_ip()]
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips


def start_mdns():
    # Announce "a Smart Cabin receiver is here, at these IPs and this port"
    ips = all_ips()
    name = socket.gethostname()
    info = ServiceInfo(SERVICE_TYPE,
                       "Smart Cabin " + name + "." + SERVICE_TYPE,
                       addresses=[socket.inet_aton(ip) for ip in ips],
                       port=PORT,
                       properties={"path": "/pi-data"},
                       server=name.lower() + ".local.")
    zc = Zeroconf()
    zc.register_service(info)
    print("Announced on the network (mDNS) as 'Smart Cabin " + name + "' at " + ", ".join(ips) + " port " + str(PORT))
    return zc, info


def save_all():
    # Save what every Pi sent, for the dashboard or the results later.
    # Write to a temporary file first, then swap it in, so no one reads a half-written file.
    with lock:
        data = {device: {"received": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["received"])),
                         "message": entry["message"]} for device, entry in pis.items()}
    temp_path = SAVE_FILE + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    try:
        os.replace(temp_path, SAVE_FILE)
    except PermissionError:
        pass      # file busy (open in another program); it will be saved next time


def pi_list():
    now = time.time()
    with lock:
        result = []
        for device, entry in sorted(pis.items()):
            seconds_ago = int(now - entry["received"])
            result.append({"device": device, "online": seconds_ago < OFFLINE_SECONDS,
                           "seconds_ago": seconds_ago, "message": entry["message"]})
        return result


def receive(message, sender_ip):
    device = message.get("device") or sender_ip
    with lock:
        is_new = device not in pis
        pis[device] = {"received": time.time(), "message": message}
    if is_new:
        print("Pi connected:", device, "from", sender_ip)
    save_all()


def watch_offline():
    # Print when a Pi stops sending
    reported = set()
    while True:
        for pi in pi_list():
            if not pi["online"] and pi["device"] not in reported:
                print("Pi offline:", pi["device"], "(nothing for", pi["seconds_ago"], "s)")
                reported.add(pi["device"])
            if pi["online"]:
                reported.discard(pi["device"])
        time.sleep(2)


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Cabin Receiver</title>
<style>
  body { margin: 0; padding: 16px; font-family: sans-serif; background: #f4f4f4; color: #222; }
  .wrap { max-width: 860px; margin: auto; }
  .box { background: #fff; border-radius: 8px; padding: 12px; margin-bottom: 12px; overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  td, th { text-align: left; padding: 6px; border-bottom: 1px solid #eee; vertical-align: top; }
  .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; vertical-align: middle; margin-right: 6px; }
  small { color: #666; }
  h3 { margin: 0 0 6px 0; }
</style>
</head>
<body>
<div class="wrap">
  <h2>Smart Cabin - data from the Pi</h2>
  <p><small id="info">Waiting for data...</small></p>
  <div id="pis"></div>
</div>
<script>
var COLORS = {"Available": "#1a9b3c", "Busy": "#d22", "Back soon": "#e0a000", "Away": "#999"};
var LEVEL_COLORS = {"ok": "#1a9b3c", "warn": "#e0a000", "error": "#d22", "off": "#bbb"};

function el(tag, text) {
  var e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  return e;
}
function dot(color) {
  var span = el("span");
  span.className = "dot";
  span.style.background = color;
  return span;
}

function drawPi(pi) {
  var box = el("div");
  box.className = "box";
  var title = el("h3");
  title.appendChild(dot(pi.online ? "#1a9b3c" : "#d22"));
  title.appendChild(document.createTextNode(pi.device + (pi.online ? " - online" : " - OFFLINE")));
  box.appendChild(title);

  var m = pi.message;
  var line = el("small", "Last data " + pi.seconds_ago + " s ago (sent " + m.sent + ") | ");
  var link = el("a", "open the Pi's own page");
  link.href = m.pi_page;
  link.target = "_blank";
  line.appendChild(link);
  box.appendChild(line);

  if (!m.app_running || !m.status) {
    box.appendChild(el("p", "The Pi is on, but smartcabin_pi.py is not running."));
    return box;
  }
  var s = m.status;
  var people = el("table");
  people.innerHTML = "<tr><th>Name</th><th>Status</th><th>How we know</th><th>Last seen</th></tr>";
  s.people.forEach(function (p) {
    var row = people.insertRow();
    var cell = row.insertCell();
    cell.appendChild(dot(COLORS[p.status]));
    cell.appendChild(document.createTextNode(p.name));
    row.insertCell().textContent = p.status + " (" + p.reason + ")";
    row.insertCell().textContent = p.how;
    row.insertCell().textContent = p.last_seen;
  });
  if (s.people.length === 0) people.insertRow().insertCell().textContent = "No one registered on this Pi yet.";
  box.appendChild(people);

  var problems = s.hardware.filter(function (h) { return h.level === "warn" || h.level === "error"; });
  var hw = el("p");
  if (problems.length === 0) {
    hw.textContent = "Hardware: all OK";
  } else {
    problems.forEach(function (h) {
      var item = el("div");
      item.appendChild(dot(LEVEL_COLORS[h.level]));
      item.appendChild(document.createTextNode(h.part + ": " + h.text));
      hw.appendChild(item);
    });
  }
  box.appendChild(hw);
  return box;
}

function refresh() {
  fetch("/pis.json").then(function (r) { return r.json(); }).then(function (list) {
    var area = document.getElementById("pis");
    area.innerHTML = "";
    list.forEach(function (pi) { area.appendChild(drawPi(pi)); });
    document.getElementById("info").textContent = list.length === 0
      ? "No Pi has sent anything yet. Run pi_sender.py on the Pi (same Wi-Fi)."
      : list.length + " Pi(s). Updated " + new Date().toLocaleTimeString();
  }).catch(function () {
    document.getElementById("info").textContent = "pi_receiver.py is not running.";
  });
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/":
            send(self, 200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        elif self.path == "/pis.json":
            send(self, 200, "application/json", json.dumps(pi_list()).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/pi-data":
            self.send_error(404)
            return
        if self.headers.get("X-Token") != TOKEN:
            self.send_error(403, "Wrong token")
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            message = json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            self.send_error(400, "Not JSON")
            return
        receive(message, self.client_address[0])
        send(self, 200, "text/plain", b"ok")

    def log_message(self, format, *args):
        pass    # don't print a line for every request


def send(handler, code, content_type, body):
    handler.send_response(code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    zc, info = start_mdns()
    threading.Thread(target=watch_offline, daemon=True).start()
    print("Page: http://localhost:" + str(PORT) + "   Data saved to pi_status.json")
    print("Waiting for the Pi... Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        zc.unregister_service(info)
        zc.close()


if __name__ == "__main__":
    main()
