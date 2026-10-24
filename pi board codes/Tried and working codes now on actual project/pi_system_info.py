# Smart Cabin - show system information of the Raspberry Pi.
# Uses only Python's standard library and the Pi's own files and commands - nothing to install.
#
# Run:
#   python3 pi_system_info.py            print a report once
#   python3 pi_system_info.py --watch 5  print it again every 5 seconds (Ctrl+C to stop)
#   python3 pi_system_info.py --json     print it as JSON (for sending to the laptop later)

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time

NOT_AVAILABLE = "not available"

# What each bit of "vcgencmd get_throttled" means
THROTTLE_BITS = {
    0: "under-voltage NOW",
    1: "CPU speed capped NOW",
    2: "throttled NOW",
    3: "soft temperature limit NOW",
    16: "under-voltage happened since boot",
    17: "CPU speed capped since boot",
    18: "throttled since boot",
    19: "soft temperature limit since boot",
}


# ---------- Small helpers ----------
def read_file(path):
    # File contents, or "" if it doesn't exist (e.g. when testing on a laptop)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except OSError:
        return ""


def run_command(args, timeout=5):
    # What a command printed, or "" if it is missing or took too long
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def nice_bytes(number):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if number < 1024:
            return format(number, ".1f") + " " + unit
        number = number / 1024
    return format(number, ".1f") + " PB"


def nice_duration(seconds):
    days, seconds = divmod(int(seconds), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return str(days) + "d " + str(hours) + "h " + str(minutes) + "m"


def my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))     # no data is sent, it only picks the right network card
        return s.getsockname()[0]
    except OSError:
        return NOT_AVAILABLE
    finally:
        s.close()


# ---------- One function per section ----------
def board_info():
    serial = NOT_AVAILABLE
    for line in read_file("/proc/cpuinfo").splitlines():
        if line.startswith("Serial"):
            serial = line.split(":")[1].strip()
    os_name = NOT_AVAILABLE
    for line in read_file("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            os_name = line.split("=", 1)[1].strip('"')
    return {
        "model": read_file("/proc/device-tree/model").rstrip("\x00") or platform.node() + " (not a Raspberry Pi)",
        "serial": serial,
        "os": os_name if os_name != NOT_AVAILABLE else platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
    }


def uptime_info():
    text = read_file("/proc/uptime")
    if not text:
        return {"uptime": NOT_AVAILABLE, "time_now": time.strftime("%Y-%m-%d %H:%M:%S")}
    seconds = float(text.split()[0])
    return {
        "uptime": nice_duration(seconds),
        "booted_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - seconds)),
        "time_now": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def cpu_times():
    # Total and idle time of all CPUs together, from the first line of /proc/stat
    numbers = [int(n) for n in read_file("/proc/stat").splitlines()[0].split()[1:]]
    idle = numbers[3] + numbers[4]          # idle + waiting for disk
    return sum(numbers), idle


def cpu_info():
    info = {"cores": os.cpu_count()}

    # CPU use: measure twice, half a second apart
    if read_file("/proc/stat"):
        total1, idle1 = cpu_times()
        time.sleep(0.5)
        total2, idle2 = cpu_times()
        busy = 1 - (idle2 - idle1) / max(total2 - total1, 1)
        info["usage"] = format(busy * 100, ".0f") + " %"
    else:
        info["usage"] = NOT_AVAILABLE

    try:
        load = os.getloadavg()
        info["load_1_5_15_min"] = " / ".join(format(x, ".2f") for x in load)
    except (OSError, AttributeError):
        info["load_1_5_15_min"] = NOT_AVAILABLE

    freq = read_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    max_freq = read_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq")
    info["speed"] = (str(int(freq) // 1000) + " MHz (max " + str(int(max_freq) // 1000) + " MHz)") if freq and max_freq else NOT_AVAILABLE

    temp = read_file("/sys/class/thermal/thermal_zone0/temp")
    if temp:
        celsius = int(temp) / 1000
        warning = "  <- HOT" if celsius >= 80 else ""
        info["temperature"] = format(celsius, ".1f") + " C" + warning
    else:
        info["temperature"] = NOT_AVAILABLE
    return info


def memory_info():
    values = {}
    for line in read_file("/proc/meminfo").splitlines():
        name, rest = line.split(":", 1)
        values[name] = int(rest.split()[0]) * 1024        # the file gives kB
    if not values:
        return {"ram": NOT_AVAILABLE, "swap": NOT_AVAILABLE}

    def used_text(total, free):
        if total == 0:
            return "none"
        used = total - free
        return nice_bytes(used) + " used of " + nice_bytes(total) + " (" + format(used / total * 100, ".0f") + " %)"

    gpu = run_command(["vcgencmd", "get_mem", "gpu"])        # e.g. "gpu=64M"
    return {
        "ram": used_text(values["MemTotal"], values.get("MemAvailable", values["MemFree"])),
        "swap": used_text(values.get("SwapTotal", 0), values.get("SwapFree", 0)),
        "gpu_memory": gpu.split("=")[1] if "=" in gpu else NOT_AVAILABLE,
    }


def disk_info():
    usage = shutil.disk_usage("/")
    percent = usage.used / usage.total * 100
    warning = "  <- almost full" if percent >= 90 else ""
    return {"sd_card": nice_bytes(usage.used) + " used of " + nice_bytes(usage.total) +
                       " (" + format(percent, ".0f") + " %), " + nice_bytes(usage.free) + " free" + warning}


def power_info():
    text = run_command(["vcgencmd", "get_throttled"])        # e.g. "throttled=0x50005"
    if "=" not in text:
        return {"power": NOT_AVAILABLE, "core_voltage": NOT_AVAILABLE}
    flags = int(text.split("=")[1], 16)
    problems = [meaning for bit, meaning in THROTTLE_BITS.items() if flags & (1 << bit)]
    volts = run_command(["vcgencmd", "measure_volts", "core"])   # e.g. "volt=1.2000V"
    return {
        "power": "OK" if not problems else "PROBLEM: " + ", ".join(problems),
        "throttled_code": hex(flags),
        "core_voltage": volts.split("=")[1] if "=" in volts else NOT_AVAILABLE,
    }


def network_info():
    all_ips = run_command(["hostname", "-I"]) if sys.platform.startswith("linux") else ""   # -I only exists on Linux
    ssid = run_command(["iwgetid", "-r"])
    signal = NOT_AVAILABLE
    # /proc/net/wireless: the 4th column of the wlan0 line is the signal level in dBm
    for line in read_file("/proc/net/wireless").splitlines():
        if line.strip().startswith("wlan0"):
            level = float(line.split()[3].rstrip("."))
            quality = "good" if level > -60 else "ok" if level > -70 else "weak"
            signal = format(level, ".0f") + " dBm (" + quality + ")"
    return {
        "ip": my_ip(),
        "all_ips": all_ips or NOT_AVAILABLE,
        "wifi_name": ssid or NOT_AVAILABLE,
        "wifi_signal": signal,
        "mdns_name": socket.gethostname() + ".local",
    }


def hardware_info():
    # Camera: ask the camera tool (newer OS: rpicam-hello, older: libcamera-hello)
    camera_text = run_command(["rpicam-hello", "--list-cameras"], 15) or run_command(["libcamera-hello", "--list-cameras"], 15)
    if not camera_text:
        camera = NOT_AVAILABLE
    elif "No cameras available" in camera_text:
        camera = "NOT connected (check the ribbon cable)"
    else:
        # The line after "Available cameras" looks like "0 : imx219 [3280x2464 10-bit RGGB] (...)"
        lines = [line.strip() for line in camera_text.splitlines() if line.strip()[:1].isdigit() and " : " in line]
        camera = "connected: " + lines[0].split(" : ")[1].split(" [")[0] if lines else "connected"

    bluetooth_text = run_command(["bluetoothctl", "show"])
    if "Powered: yes" in bluetooth_text:
        bluetooth = "on"
    elif "Controller" in bluetooth_text:
        bluetooth = "off (run: bluetoothctl power on)"
    else:
        bluetooth = NOT_AVAILABLE

    def enabled(path):
        if not sys.platform.startswith("linux"):
            return NOT_AVAILABLE
        return "enabled" if os.path.exists(path) else "disabled"

    return {
        "camera": camera,
        "spi_for_rfid": enabled("/dev/spidev0.0"),
        "i2c": enabled("/dev/i2c-1"),
        "bluetooth": bluetooth,
    }


def top_processes():
    # The 5 programs using the most memory
    text = run_command(["ps", "-eo", "pid,comm,%mem,%cpu", "--sort=-%mem"])
    lines = text.splitlines()[1:6]
    return [" ".join(line.split()) for line in lines] or [NOT_AVAILABLE]


def collect_all():
    return {
        "Board": board_info(),
        "Uptime": uptime_info(),
        "CPU": cpu_info(),
        "Memory": memory_info(),
        "Storage": disk_info(),
        "Power": power_info(),
        "Network": network_info(),
        "Hardware": hardware_info(),
        "Top processes (pid name %mem %cpu)": top_processes(),
    }


def print_report(info):
    print("=" * 60)
    print(" Smart Cabin - Pi system information")
    print("=" * 60)
    for section, values in info.items():
        print("\n[" + section + "]")
        if isinstance(values, list):
            for line in values:
                print("  " + line)
        else:
            for name, value in values.items():
                print("  " + name.replace("_", " ").ljust(18) + ": " + str(value))
    print()


def main():
    if "--json" in sys.argv:
        print(json.dumps(collect_all(), indent=2))
        return

    if "--watch" in sys.argv:
        position = sys.argv.index("--watch")
        seconds = int(sys.argv[position + 1]) if len(sys.argv) > position + 1 else 5
        try:
            while True:
                info = collect_all()
                os.system("clear" if os.name != "nt" else "cls")
                print_report(info)
                print("Refreshing every", seconds, "s. Press Ctrl+C to stop.")
                time.sleep(seconds)
        except KeyboardInterrupt:
            print("Stopped.")
        return

    print_report(collect_all())


if __name__ == "__main__":
    main()
