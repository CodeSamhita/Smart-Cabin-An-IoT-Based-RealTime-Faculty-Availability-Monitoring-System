# Smart Cabin edge device - the "black box": records what the board was doing, so a sudden switch-off or reboot
# can be explained afterwards. A separate program from the Smart Cabin app, so it keeps recording if the app crashes.
#
#   sudo python3 blackbox.py --install   start it now and at every boot (systemd), and keep the system log across reboots
#   python3 blackbox.py --report         show the report about the last unexpected stop
#   python3 blackbox.py                  run it by hand (Ctrl+C to stop)
#
# Every 2 s one line goes into data/blackbox.csv and is forced onto the SD card at once (so the last seconds before a
# power cut are kept): temperature, the Pi's power / heat warning flags, CPU, memory, swap, Wi-Fi, the app.
# At each start it checks whether the last run ended normally. If not, data/blackbox_report.txt says what the last
# readings were, what the likely cause is, and what the kernel logged about power, memory or heat before the stop.

import csv
import os
import signal
import subprocess
import sys
import time

FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(FOLDER, "data")
RECORD = os.path.join(DATA, "blackbox.csv")
REPORT = os.path.join(DATA, "blackbox_report.txt")
EVERY_SECONDS = 2
MAX_BYTES = 5 * 1024 * 1024                # the record is started fresh (old one kept as .old) above 5 MB
COLUMNS = ["time", "event", "uptime_s", "temp_c", "throttled", "warnings_now", "warnings_since_boot", "cpu_percent",
           "load_1min", "mem_free_mb", "swap_used_mb", "wifi_ssid", "wifi_signal_dbm", "app_running", "app_mem_mb"]

# The bits of `vcgencmd get_throttled` (the Pi's own record of power and heat problems)
NOW = {0x1: "UNDER-VOLTAGE", 0x2: "speed capped", 0x4: "throttled", 0x8: "temperature limit"}
SINCE_BOOT = {0x10000: "under-voltage", 0x20000: "speed capped", 0x40000: "throttled", 0x80000: "temperature limit"}


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def run(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def throttled():
    raw = run(["vcgencmd", "get_throttled"]).split("=")[-1]
    try:
        bits = int(raw, 16)
    except ValueError:
        return raw or "?", "", ""
    now = " + ".join(name for bit, name in NOW.items() if bits & bit)
    since = " + ".join(name for bit, name in SINCE_BOOT.items() if bits & bit)
    return raw, now, since


def memory():
    info = {}
    for line in read("/proc/meminfo").splitlines():
        name, _, value = line.partition(":")
        if value.split():
            info[name] = int(value.split()[0]) // 1024
    return info.get("MemAvailable", ""), (info.get("SwapTotal", 0) - info.get("SwapFree", 0)) if "SwapTotal" in info else ""


def cpu_percent(previous):
    # CPU use since the last reading, from /proc/stat
    fields = [int(x) for x in read("/proc/stat").splitlines()[0].split()[1:]]
    idle, total = fields[3] + fields[4], sum(fields)
    if previous:
        busy = 100 * (1 - (idle - previous[0]) / max(1, total - previous[1]))
        return round(busy), (idle, total)
    return "", (idle, total)


def wifi():
    ssid = run(["iwgetid", "-r"])
    signal_dbm = ""
    for line in read("/proc/net/wireless").splitlines()[2:]:
        parts = line.split()
        if len(parts) > 3:
            signal_dbm = parts[3].rstrip(".")
    return ssid or "not connected", signal_dbm


def app():
    # Is the Smart Cabin app (main.py) running, and how much memory does it use?
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            command = read("/proc/" + pid + "/cmdline").replace("\x00", " ")
            if "main.py" in command and "python" in command:
                for line in read("/proc/" + pid + "/status").splitlines():
                    if line.startswith("VmRSS"):
                        return "yes", int(line.split()[1]) // 1024
                return "yes", ""
    return "no", ""


def write(row):
    os.makedirs(DATA, exist_ok=True)
    if os.path.exists(RECORD) and os.path.getsize(RECORD) > MAX_BYTES:
        os.replace(RECORD, RECORD + ".old")
    new = not os.path.exists(RECORD)
    with open(RECORD, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())                      # onto the SD card now, so it survives a power cut


def reading(event, previous_cpu):
    raw, now, since = throttled()
    free, swap = memory()
    cpu, previous_cpu = cpu_percent(previous_cpu)
    ssid, signal_dbm = wifi()
    running, app_mem = app()
    temp = read("/sys/class/thermal/thermal_zone0/temp")
    row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event,
           "uptime_s": int(float(read("/proc/uptime").split()[0] or 0)) if read("/proc/uptime") else "",
           "temp_c": round(int(temp) / 1000, 1) if temp.isdigit() else "", "throttled": raw, "warnings_now": now,
           "warnings_since_boot": since, "cpu_percent": cpu, "load_1min": read("/proc/loadavg").split(" ")[0],
           "mem_free_mb": free, "swap_used_mb": swap, "wifi_ssid": ssid, "wifi_signal_dbm": signal_dbm,
           "app_running": running, "app_mem_mb": app_mem}
    return row, previous_cpu


# ---------- what happened last time ----------
def last_rows(count=15):
    try:
        with open(RECORD, newline="") as f:
            return list(csv.DictReader(f))[-count:]
    except OSError:
        return []


def number(text, default=0.0):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def likely_causes(rows, kernel):
    last = rows[-1]
    causes = []
    if "UNDER-VOLTAGE" in last["warnings_now"] or "under-voltage" in last["warnings_since_boot"] or "voltage" in kernel.lower():
        causes.append("POWER: the Pi saw under-voltage. The power supply or cable is too weak for the Pi + camera + "
                      "NeoPixel + RC522. Use the official 5.1 V 2.5 A (Zero 2W) / 3 A (Pi 4) supply and a short, thick cable, "
                      "and power the NeoPixel from the 5 V pin only if the supply can take it.")
    if number(last["temp_c"]) >= 80 or "temperature limit" in last["warnings_since_boot"] or "thermal" in kernel.lower():
        causes.append("HEAT: the CPU was at %s °C. Add a heatsink and air flow." % last["temp_c"])
    if number(last["mem_free_mb"], 999) < 40 or "out of memory" in kernel.lower() or "oom" in kernel.lower():
        causes.append("MEMORY: only %s MB free (swap used %s MB). Boot without the desktop; the kernel may have stopped "
                      "the app." % (last["mem_free_mb"], last["swap_used_mb"]))
    if last["wifi_ssid"] == "not connected" or number(last["wifi_signal_dbm"], 0) < -75:
        causes.append("WI-FI: weak or no Wi-Fi (%s, %s dBm) - this closes the SSH connection, but does not switch the "
                      "board off." % (last["wifi_ssid"], last["wifi_signal_dbm"]))
    if not causes:
        causes.append("No warning before the stop. A sudden stop with no warning at all usually means the power was "
                      "cut (loose cable, supply dropping out) - the Pi had no time to log anything.")
    return causes


def check_last_run():
    # Called at start: did the last run end with STOP? If not, write the report.
    rows = last_rows()
    if not rows or rows[-1]["event"] == "stop":
        return
    kernel = run(["journalctl", "-k", "-b", "-1", "--no-pager", "-q"])
    keep = [line for line in kernel.splitlines()
            if any(word in line.lower() for word in ("voltage", "oom", "out of memory", "thermal", "throttl", "brcmfmac", "watchdog"))]
    causes = likely_causes(rows, "\n".join(keep))
    lines = ["Smart Cabin black box - the last run ended without a normal stop",
             "Report made " + time.strftime("%Y-%m-%d %H:%M:%S"),
             "Last reading " + rows[-1]["time"] + " (the board stopped within " + str(EVERY_SECONDS) + " s after it)", "",
             "Likely cause:"] + ["  - " + c for c in causes] + ["", "Last readings (oldest first):"]
    lines += ["  " + r["time"] + "  temp " + r["temp_c"] + " C  flags " + r["throttled"] + " " + r["warnings_now"]
              + "  cpu " + str(r["cpu_percent"]) + " %  free " + str(r["mem_free_mb"]) + " MB  swap " + str(r["swap_used_mb"])
              + " MB  wifi " + r["wifi_signal_dbm"] + " dBm  app " + r["app_running"] for r in rows]
    lines += ["", "Kernel messages of the previous boot about power, memory, heat or Wi-Fi:"]
    lines += ["  " + line for line in keep[-30:]] or ["  (none - or the system log is not kept across reboots: run --install once)"]
    os.makedirs(DATA, exist_ok=True)
    with open(REPORT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------- running ----------
def record_forever():
    stopping = {"now": False}

    def stop(*_):
        stopping["now"] = True

    signal.signal(signal.SIGTERM, stop)            # a normal shutdown / reboot stops services with SIGTERM
    check_last_run()
    row, previous_cpu = reading("start", None)
    write(row)
    while not stopping["now"]:
        time.sleep(EVERY_SECONDS)
        try:
            row, previous_cpu = reading("", previous_cpu)
            write(row)
        except Exception as problem:               # never stop recording because of one bad reading
            print("black box: could not record:", problem, file=sys.stderr)
    row, _ = reading("stop", previous_cpu)
    write(row)


def install():
    if os.geteuid() != 0:
        sys.exit("Run it with sudo:  sudo python3 blackbox.py --install")
    os.makedirs("/var/log/journal", exist_ok=True)  # keep the system log across reboots, so the kernel's messages survive
    subprocess.run(["systemctl", "restart", "systemd-journald"])
    service = ("[Unit]\nDescription=Smart Cabin black box (records the board's health)\nAfter=multi-user.target\n\n"
               "[Service]\nExecStart=" + sys.executable + " " + os.path.abspath(__file__) + "\nRestart=always\nRestartSec=5\n"
               "User=root\n\n[Install]\nWantedBy=multi-user.target\n")
    with open("/etc/systemd/system/smartcabin-blackbox.service", "w") as f:
        f.write(service)
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "enable", "--now", "smartcabin-blackbox.service"])
    print("The black box now records every %d s, also after every reboot." % EVERY_SECONDS)
    print("Record: " + RECORD + "\nAfter an unexpected stop: python3 blackbox.py --report")


if __name__ == "__main__":
    if "--install" in sys.argv:
        install()
    elif "--report" in sys.argv:
        print(read(REPORT) or "No report: the last run ended normally (or the black box has not run yet).")
    else:
        try:
            record_forever()
        except KeyboardInterrupt:
            write(reading("stop", None)[0])
