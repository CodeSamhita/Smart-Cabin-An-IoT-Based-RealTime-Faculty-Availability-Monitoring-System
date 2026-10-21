# Smart Cabin - send the Pi's status to the laptop.
#
# It finds the laptop by itself with mDNS (the laptop announces "_smartcabin._tcp" on the Wi-Fi),
# so there are no IP addresses to type. Then every few seconds it reads the status from
# smartcabin_pi.py and sends it to the laptop.
#
# Run on the Pi (smartcabin_pi.py should be running too):  python3 pi_sender.py
# On the laptop run:                                         python code/pi_receiver.py

import json
import socket
import subprocess
import sys
import threading
import time
import urllib.request

# ---------------- Settings you can tune ----------------
SEND_SECONDS = 2                                   # how often to send
STATUS_URL = "http://localhost:8000/status.json"   # where smartcabin_pi.py gives its status
TOKEN = "smartcabin-2026"                          # must be the same in code/pi_receiver.py
SERVICE_TYPE = "_smartcabin._tcp.local."           # the mDNS name the laptop announces
# --------------------------------------------------------


def install_missing_libraries():
    try:
        import zeroconf  # noqa: F401
        return
    except ImportError:
        pass
    print("Installing zeroconf (mDNS library)...")
    if sys.platform.startswith("linux"):
        subprocess.run(["sudo", "apt-get", "update"])
        subprocess.run(["sudo", "apt-get", "install", "-y", "python3-zeroconf"], check=True)
    else:
        subprocess.run([sys.executable, "-m", "pip", "install", "zeroconf"], check=True)


install_missing_libraries()
from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf  # noqa: E402

lock = threading.Lock()
laptops = {}      # mDNS service name -> address to send to, e.g. "http://192.168.1.20:8500/pi-data"


def on_service_change(zeroconf, service_type, name, state_change):
    # Called by zeroconf whenever a laptop appears, changes or leaves the network
    short_name = name.replace("." + SERVICE_TYPE, "")
    if state_change is ServiceStateChange.Removed:
        with lock:
            laptops.pop(name, None)
        print("Laptop left:", short_name)
        return

    info = zeroconf.get_service_info(service_type, name, timeout=3000)
    if info is None:
        return
    addresses = info.parsed_addresses(IPVersion.V4Only)
    if not addresses:
        return
    path = info.properties.get(b"path", b"/pi-data").decode()
    url = "http://" + pick_address(addresses) + ":" + str(info.port) + path
    with lock:
        is_new = laptops.get(name) != url
        laptops[name] = url
    if is_new:
        print("Found laptop:", short_name, "at", url)


def pick_address(addresses):
    # The laptop may have several addresses (Wi-Fi, hotspot ...). Prefer the one on the same
    # network as this Pi, e.g. both 192.168.1.x
    my_network = my_ip().rsplit(".", 1)[0]
    for address in addresses:
        if address.rsplit(".", 1)[0] == my_network:
            return address
    return addresses[0]


def read_pi_status():
    # The status from smartcabin_pi.py, or None if it is not running
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=3) as reply:
            return json.loads(reply.read())
    except Exception:
        return None


def my_ip():
    # The address other computers on the same Wi-Fi can use to reach this one
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))     # no data is sent, it only picks the right network card
        return s.getsockname()[0]
    except OSError:
        return "unknown"
    finally:
        s.close()


def build_message(status):
    return {
        "device": socket.gethostname(),
        "pi_page": "http://" + my_ip() + ":8000",
        "sent": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app_running": status is not None,
        "status": status,
    }


def send(url, message):
    # POST the message as JSON. Returns True if the laptop said OK.
    body = json.dumps(message).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "X-Token": TOKEN})
    try:
        with urllib.request.urlopen(request, timeout=3) as reply:
            return reply.status == 200
    except Exception as error:
        return str(error)


def main():
    zc = Zeroconf()
    ServiceBrowser(zc, SERVICE_TYPE, handlers=[on_service_change])
    print("Device:", socket.gethostname(), "| looking for the laptop on the network (mDNS)...")
    print("Press Ctrl+C to stop.")

    last_result = {}          # url -> last result, so we only print when something changes
    last_waiting_note = 0.0
    was_running = None
    try:
        while True:
            status = read_pi_status()
            if status is None and was_running is not False:
                print("smartcabin_pi.py is not answering on", STATUS_URL, "- sending 'app not running' instead.")
            if status is not None and was_running is not True:
                print("Reading status from smartcabin_pi.py.")
            was_running = status is not None
            message = build_message(status)

            with lock:
                urls = list(laptops.values())
            if not urls and time.time() - last_waiting_note > 10:
                print("No laptop found yet. Is pi_receiver.py running on the laptop, on the same Wi-Fi?")
                last_waiting_note = time.time()

            for url in urls:
                result = send(url, message)
                if result != last_result.get(url):
                    print("Sending to", url, "->", "OK" if result is True else "failed: " + str(result))
                    last_result[url] = result
            time.sleep(SEND_SECONDS)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        zc.close()


if __name__ == "__main__":
    main()
