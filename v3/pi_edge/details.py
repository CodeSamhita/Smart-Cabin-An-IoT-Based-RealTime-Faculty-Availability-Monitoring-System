# Smart Cabin edge device - device details for the Advanced view of the device page (PiDevice.dc.html):
# CPU, RAM, storage, temperature, estimated power, and facts about the board, network and system.
# Everything is read from Linux files and commands; anything that can't be read shows "–" (e.g. on Windows).

import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse

import health
import identity
import settings

SOFTWARE_VERSION = "v2"
# Rough power use (watts) at idle and at full CPU load, for an estimate when no power sensor is fitted
POWER = {"Zero 2": (0.6, 3.0), "Pi 4": (2.7, 6.4), "Pi 5": (3.0, 9.0)}
started_at = time.time()


def read(path):
    try:
        with open(path) as f:
            return f.read().strip("\x00 \n")
    except OSError:
        return ""


def run(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def length(seconds):
    seconds = int(seconds)
    d, h, m = seconds // 86400, seconds % 86400 // 3600, seconds % 3600 // 60
    return (str(d) + " d " if d else "") + str(h) + " h " + str(m) + " m"


def memory():
    info = {}
    for line in read("/proc/meminfo").splitlines():
        name, _, value = line.partition(":")
        if value.strip().split():
            info[name] = int(value.split()[0]) // 1024          # MB
    return info


def uptime_seconds():
    text = read("/proc/uptime")
    return float(text.split()[0]) if text else time.time() - started_at


def os_name():
    for line in read("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip('"')
    return platform.platform()


def cpu_model():
    for line in read("/proc/cpuinfo").splitlines():
        if line.lower().startswith(("model name", "hardware")):
            return line.split(":", 1)[1].strip()
    return platform.processor() or "–"


def mac(interface):
    return read("/sys/class/net/" + interface + "/address") or "–"


def wifi():
    ssid = run(["iwgetid", "-r"])
    signal = ""
    for line in read("/proc/net/wireless").splitlines()[2:]:
        parts = line.split()
        if len(parts) > 3:
            signal = parts[3].rstrip(".")
    return (ssid or "not connected") + (" · signal " + signal + " dBm" if signal else "")


def power_estimate(cpu):
    for name, (idle, top) in POWER.items():
        if name in identity.model():
            return round(idle + (top - idle) * min(100, cpu or 0) / 100, 1)
    return None


def meter(label, value, pct, note):
    return {"label": label, "value": value, "pct": max(0, min(100, int(pct or 0))), "note": note}


cache = {"at": 0.0, "data": None}
KEEP_SECONDS = 15                 # the details are measured at most this often (some commands are slow on a Zero)


def collect():
    if cache["data"] is None or time.time() - cache["at"] > KEEP_SECONDS:
        cache["data"], cache["at"] = measure(), time.time()
    return cache["data"]


def measure():
    cpu = health.cpu_percent()
    temp = health.temperature()
    mem = memory()
    total, free = mem.get("MemTotal", 0), mem.get("MemAvailable", 0)
    used = total - free
    disk = shutil.disk_usage(settings.FOLDER)
    load = " ".join("%.2f" % x for x in os.getloadavg()) if hasattr(os, "getloadavg") else "–"
    watts = power_estimate(cpu)
    top = next((t for n, (i, t) in POWER.items() if n in identity.model()), None)
    meters = [
        meter("CPU", "–" if cpu is None else str(cpu) + " %", cpu, str(os.cpu_count()) + " cores · load " + load),
        meter("RAM", ("%.1f / %.1f GB" % (used / 1024, total / 1024)) if total else "–", 100 * used / total if total else 0,
              (str(round(100 * used / total)) + " % used · swap " + str(mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)) + " MB") if total else "–"),
        meter("Storage", "%.1f / %.0f GB" % ((disk.total - disk.free) / 1e9, disk.total / 1e9), 100 * (disk.total - disk.free) / disk.total,
              "SD card · " + str(round(100 * (disk.total - disk.free) / disk.total)) + " % used"),
        meter("CPU temperature", "–" if temp is None else str(temp) + " °C", temp or 0, "Throttling: " + str(health.throttled())),
        meter("Power now", "–" if watts is None else str(watts) + " W", 100 * watts / top if watts and top else 0,
              "estimated from CPU load" + (" · up to " + str(top) + " W" if top else "")),
    ]
    server = urllib.parse.urlparse(settings.SERVER_URL)
    groups = [
        {"title": "Board", "rows": [["Board type", identity.model(), False], ["Board name", socket.gethostname(), False],
                                    ["Serial number", identity.serial(), True], ["CPU", cpu_model() + " · " + str(os.cpu_count()) + " cores", False],
                                    ["RAM", ("%.1f GB" % (total / 1024)) if total else "–", False]]},
        {"title": "Network", "rows": [["IP address", "", True], ["Wi-Fi", wifi(), False], ["MAC (Wi-Fi)", mac("wlan0"), True],
                                      ["MAC (Ethernet)", mac("eth0"), True], ["Server", settings.SERVER_URL, True]]},
        {"title": "System", "rows": [["Uptime", length(uptime_seconds()), False],
                                     ["Last boot", time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - uptime_seconds())), False],
                                     ["Operating system", os_name(), False], ["Kernel", platform.release(), True],
                                     ["Python", platform.python_version(), True], ["Smart Cabin software", SOFTWARE_VERSION, True]]},
        {"title": "Power", "rows": [["Power now", "–" if watts is None else str(watts) + " W", False],
                                    ["Measured by", "estimated from CPU load (no power sensor fitted)", False],
                                    ["Under-voltage", "never" if str(health.throttled()) in ("0x0",) else str(health.throttled()), False]]},
        {"title": "Sensors", "rows": [["Camera", "Pi Camera · " + "x".join(map(str, settings.CAMERA_SIZE)) + " · one picture every "
                                       + str(settings.PICTURE_SECONDS) + " s", False],
                                      ["RFID reader", "RC522 · SPI", False],
                                      ["Door light", "NeoPixel · GPIO " + str(settings.LED_PIN), False]]},
    ]
    return {"meters": meters, "groups": groups, "uptime": length(uptime_seconds()), "server_host": server.hostname or ""}
