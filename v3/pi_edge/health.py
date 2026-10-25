# Smart Cabin edge device - the board's health: temperature, CPU use, free memory, throttling.
# Sent to the server with every report; the server's Devices page shows it.

import os
import subprocess

import settings
import shared


def temperature():
    # CPU temperature in °C, or None
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000, 1)
    except (OSError, ValueError):
        return None


def cpu_percent():
    try:
        return round(100 * os.getloadavg()[0] / (os.cpu_count() or 1))     # 1-minute load as % of all cores
    except (OSError, AttributeError):
        return None


def memory_free_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def throttled():
    # "0x0" = never slowed down by heat or low power. Anything else: see `vcgencmd get_throttled` docs.
    if settings.SIMULATE:
        return "n/a"
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=3).stdout
        return out.strip().split("=")[-1] or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def report():
    s = shared.snapshot()
    return {"temperature": temperature(), "cpu_percent": cpu_percent(), "memory_free_mb": memory_free_mb(),
            "throttled": throttled(), "parts": s["parts"], "last_error": s["last_error"]}
