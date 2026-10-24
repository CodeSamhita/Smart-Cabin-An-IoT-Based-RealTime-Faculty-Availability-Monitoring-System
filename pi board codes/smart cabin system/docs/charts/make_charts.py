# Smart Cabin - makes every chart used in the documents, from the measured numbers.
# Run:  python make_charts.py        (installs matplotlib the first time)
#
# Where the numbers come from:
#   - Pi Zero 2W vs Pi 4: the benchmark JSON files written by pi_benchmark.py
#     (pi board codes/Tried and working codes now on actual project/benchmarks/)
#   - camera modes, H.264, RFID: the hardware test outputs (hardware test code/pi 02w results/)
#   - detectors and face resolution: the laptop tests of 24 Oct 2026 (same test photo, OpenCV 4.10)
# Re-run after new measurements: change the numbers in MEASURED below, or replace the JSON files.
#
# One message per chart, one y-axis per chart, colour = which board / which series (never decoration).

import glob
import importlib
import json
import os
import subprocess
import sys

try:
    importlib.import_module("matplotlib")
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "matplotlib"], check=True)

import matplotlib                                     # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, "..", "..", "..", "Tried and working codes now on actual project", "benchmarks")

# Reference palette (dataviz skill, light mode): slots 1-2 are documented colour-blind safe as a pair
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"

# Measured on 23-24 Oct 2026 (sources in the comment at the top)
MEASURED = {
    "camera_modes_zero_ov5647": {          # 2_test_camera.py on the Pi Zero 2W
        "modes": ["640x480", "1296x972", "1920x1080", "2592x1944"],
        "rated_fps": [62.5, 46.3, 32.8, 15.6],
        "measured_fps": [62.1, 46.1, 32.6, 15.5],
    },
    "h264_zero": {                          # 2_test_camera.py, 1080p30, 4 s each
        "asked_mbps": [5, 10, 17, 25],
        "got_mbps": [4.8, 9.6, 16.2, 24.0],
    },
    "detectors_test_photo": {               # 6_people_count_web.py, street photo with 4 people, laptop
        "names": ["MobileNet-SSD", "YOLOv8n (320)"],
        "people_found": [2, 3],
        "people_real": 4,
        "ms_laptop": [22, 27],
    },
    "face_by_resolution": {                 # YuNet on the same photo, laptop
        "sizes": ["320x240", "640x480", "1296x972"],
        "faces_found": [0, 0, 1],
        "ms_laptop": [12, 17, 63],
    },
    "rfid_zero": {                          # 1_test_rfid.py on the Pi Zero 2W
        "reads_per_s": 31792, "stable_reads": "500 / 500", "self_test": "64 / 64 bytes",
    },
}


def style(ax, title, ylabel="", xlabel=""):
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.set_ylabel(ylabel, color=INK2, fontsize=10)
    ax.set_xlabel(xlabel, color=INK2, fontsize=10)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    path = os.path.join(HERE, name)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print("saved", name)


def label_bars(ax, bars, fmt="{:g}", inside=False):
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h), xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color=INK2)


def load_boards():
    boards = {}
    for path in sorted(glob.glob(os.path.join(BENCH, "benchmark_*.json"))):
        with open(path) as f:
            data = json.load(f)
        name = "Pi Zero 2W" if "Zero" in data["system"]["model"] else "Pi 4"
        boards[name] = data
    return boards


def chart_steps(boards):
    # Where the time goes in one 640x480 picture with one face: the face steps, not the camera
    steps = [("detect", "Find faces\n(YuNet)"), ("embed_per_face", "Face to numbers\n(SFace)"),
             ("match_20_people", "Match vs\n20 people"), ("jpeg_encode", "JPEG"), ("whole_frame_1_face", "Whole\npicture")]
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.38
    for k, (board, colour) in enumerate((("Pi Zero 2W", BLUE), ("Pi 4", ORANGE))):
        if board not in boards:
            continue
        values = [boards[board]["face"]["640x480"][s]["median_ms"] for s, _ in steps]
        bars = ax.bar([i + (k - 0.5) * width for i in range(len(steps))], values, width - 0.04, color=colour, label=board)
        label_bars(ax, bars)
    ax.set_xticks(range(len(steps)), [label for _, label in steps])
    style(ax, "Time per picture step, 640x480, median (lower is better)", "milliseconds")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "board_steps.png")


def chart_sustained(boards):
    # Two separate charts (never two y-axes on one): speed over 60 s, and temperature over 60 s
    for key, title, unit, name in (("fps_every_10s", "Sustained speed over 60 s (higher is better)", "pictures per second", "board_fps.png"),
                                   ("temp_every_10s_c", "CPU temperature over 60 s at full load", "°C", "board_temperature.png")):
        fig, ax = plt.subplots(figsize=(7, 3.6))
        for board, colour in (("Pi Zero 2W", BLUE), ("Pi 4", ORANGE)):
            if board in boards and key in boards[board]["sustained"]:
                values = boards[board]["sustained"][key]
                xs = [10 * (i + 1) for i in range(len(values))]
                ax.plot(xs, values, color=colour, linewidth=2, marker="o", markersize=5, label=board)
                ax.annotate(board + " " + str(values[-1]), (xs[-1], values[-1]), xytext=(6, 0), textcoords="offset points",
                            va="center", fontsize=8, color=INK2)
        style(ax, title, unit, "seconds")
        ax.legend(frameon=False, fontsize=9, loc="best")
        save(fig, name)


def chart_camera(m):
    d = m["camera_modes_zero_ov5647"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    width = 0.38
    for k, (key, label, colour) in enumerate((("rated_fps", "Rated by the sensor", BLUE), ("measured_fps", "Measured", ORANGE))):
        bars = ax.bar([i + (k - 0.5) * width for i in range(len(d["modes"]))], d[key], width - 0.04, color=colour, label=label)
        label_bars(ax, bars)
    ax.set_xticks(range(len(d["modes"])), d["modes"])
    style(ax, "Camera v1 (ov5647) on the Pi Zero 2W: every mode reaches 99-100 % of its rated speed", "pictures per second")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "camera_modes.png")


def chart_h264(m):
    d = m["h264_zero"]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    width = 0.38
    labels = [str(a) + " Mbps" for a in d["asked_mbps"]]
    for k, (key, label, colour) in enumerate((("asked_mbps", "Asked", BLUE), ("got_mbps", "Got", ORANGE))):
        bars = ax.bar([i + (k - 0.5) * width for i in range(len(labels))], d[key], width - 0.04, color=colour, label=label)
        label_bars(ax, bars)
    ax.set_xticks(range(len(labels)), labels)
    style(ax, "Hardware H.264 at 1080p30 on the Pi Zero 2W: about 96 % of each bitrate", "Mbps")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "h264_bitrate.png")


def chart_detectors(m):
    d = m["detectors_test_photo"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.4))
    bars = axes[0].bar(d["names"], d["people_found"], 0.55, color=[BLUE, ORANGE])
    label_bars(axes[0], bars)
    axes[0].axhline(d["people_real"], color=MUTED, linewidth=1, linestyle="--")
    axes[0].annotate("people in the photo: " + str(d["people_real"]), (1.3, d["people_real"]), xytext=(0, 4),
                     textcoords="offset points", ha="right", fontsize=8, color=INK2)
    axes[0].set_ylim(0, d["people_real"] + 1)
    style(axes[0], "People found (higher is better)", "people")
    bars = axes[1].bar(d["names"], d["ms_laptop"], 0.55, color=[BLUE, ORANGE])
    label_bars(axes[1], bars)
    style(axes[1], "Time per picture on the laptop", "milliseconds")
    save(fig, "detectors.png")


def chart_faces(m):
    d = m["face_by_resolution"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.4))
    bars = axes[0].bar(d["sizes"], d["faces_found"], 0.55, color=BLUE)
    label_bars(axes[0], bars)
    axes[0].set_ylim(0, 1.6)
    style(axes[0], "Faces found in the street photo", "faces")
    bars = axes[1].bar(d["sizes"], d["ms_laptop"], 0.55, color=BLUE)
    label_bars(axes[1], bars)
    style(axes[1], "Time to find faces (laptop)", "milliseconds")
    save(fig, "face_resolution.png")


def chart_delay():
    # Worst-case time from "walks in" to "page changes", by design (config values), one stacked bar
    # A waterfall: one row per step, each bar starts where the one above ends
    parts = [("Wait for the next picture", 5), ("2nd matching picture", 1.5), ("Report to the laptop", 3),
             ("Server's 10 s buffer", 10), ("Public page refresh", 10)]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    left = 0
    for row, (label, seconds) in enumerate(parts):
        ax.barh([row], [seconds], left=left, color=BLUE, height=0.55)
        ax.text(left + seconds + 0.3, row, str(seconds) + " s", va="center", fontsize=8, color=INK2)
        left += seconds
    ax.set_yticks(range(len(parts)), [label for label, _ in parts])
    ax.invert_yaxis()
    ax.set_xlim(0, left + 3)
    style(ax, "Arrival to public page, worst case by design: about " + str(round(left)) + " s", "", "seconds")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    save(fig, "update_delay.png")


def main():
    boards = load_boards()
    if boards:
        chart_steps(boards)
        chart_sustained(boards)
    else:
        print("benchmark JSON files not found in", BENCH, "- board charts skipped")
    chart_camera(MEASURED)
    chart_h264(MEASURED)
    chart_detectors(MEASURED)
    chart_faces(MEASURED)
    chart_delay()


if __name__ == "__main__":
    main()
