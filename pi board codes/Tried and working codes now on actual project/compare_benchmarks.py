# Smart Cabin - compare the benchmark results of two Pi boards and draw graphs.
#
# Reads the JSON files that pi_benchmark.py saves (benchmarks/benchmark_*.json), prints a comparison
# table with "how many times faster", and saves one picture with 6 graphs: benchmarks/board_comparison.png
#
# Run on the laptop (installs matplotlib if missing):
#   python compare_benchmarks.py                       newest result of each board in benchmarks/
#   python compare_benchmarks.py a.json b.json         compare these two files
#   python compare_benchmarks.py --no-show             only save the picture, don't open a window

import glob
import json
import os
import subprocess
import sys

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmarks")
PICTURE = os.path.join(FOLDER, "board_comparison.png")

# Colours: first two categorical colours of the chart palette, plus text / grid colours
COLORS = ["#2a78d6", "#eb6834"]          # board 1 blue, board 2 orange
HATCHES = ["", "//"]                     # board 2 also gets stripes, so it is clear without colour / in print
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"


def install_missing_libraries():
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("Installing matplotlib...")
        subprocess.run([sys.executable, "-m", "pip", "install", "matplotlib"], check=True)


install_missing_libraries()
import matplotlib                       # noqa: E402
if "--no-show" in sys.argv:
    matplotlib.use("Agg")               # no window needed
import matplotlib.pyplot as plt         # noqa: E402


# ---------- Reading the results ----------
def short_name(model):
    # "Raspberry Pi Zero 2 W Rev 1.0" -> "Pi Zero 2 W"
    name = model.replace("Raspberry ", "").split(" Rev")[0]
    return name.replace(" Model B", "")


def load_results():
    files = [arg for arg in sys.argv[1:] if arg.endswith(".json")]
    if not files:
        # Newest file of each board model
        newest = {}
        for path in sorted(glob.glob(os.path.join(FOLDER, "benchmark_*.json")), key=os.path.getmtime):
            with open(path, encoding="utf-8") as f:
                newest[json.load(f)["system"]["model"]] = path
        files = list(newest.values())
    if len(files) != 2:
        sys.exit("Need results of exactly 2 boards, found " + str(len(files)) + " in " + FOLDER +
                 ". Or give two files: python compare_benchmarks.py a.json b.json")

    boards = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["name"] = short_name(data["system"]["model"])
        boards.append(data)
    # Slower board first, so "how many times faster" is always about the second (faster) board
    boards.sort(key=lambda b: b["sustained"]["fps"])
    print("Comparing:", boards[0]["name"], "vs", boards[1]["name"])
    return boards


def median(board, size, step):
    return board["face"][size][step]["median_ms"]


# Every row: (label, function giving the value, unit, True if a higher value is better)
METRICS = [
    ("Detect faces 640x480", lambda b: median(b, "640x480", "detect"), "ms", False),
    ("Embed 1 face 640x480", lambda b: median(b, "640x480", "embed_per_face"), "ms", False),
    ("Whole frame 640x480", lambda b: median(b, "640x480", "whole_frame_1_face"), "ms", False),
    ("Whole frame 320x240", lambda b: median(b, "320x240", "whole_frame_1_face"), "ms", False),
    ("Sustained FPS", lambda b: b["sustained"]["fps"], "FPS", True),
    ("Max FPS 320x240", lambda b: b["face"]["320x240"]["max_fps"], "FPS", True),
    ("Load models", lambda b: b["face"]["model_load_s"], "s", False),
    ("Python loop (1M)", lambda b: b["cpu_storage"]["python_loop_1M"]["median_ms"], "ms", False),
    ("numpy 256x256 multiply", lambda b: b["cpu_storage"]["numpy_matmul_256"]["median_ms"], "ms", False),
    ("SD card write", lambda b: b["cpu_storage"]["sd_write_mb_per_s"], "MB/s", True),
    ("Max temperature", lambda b: b["sustained"]["temp_max_c"], "C", False),
    ("RAM still free", lambda b: b["face"]["ram_available_mb"], "MB", True),
    ("Arrive -> laptop page", lambda b: b["update_delay"]["laptop_page_worst_s"], "s", False),
    ("Suggested FPS", lambda b: b["update_delay"]["recommended_fps"], "FPS", True),
]

# The rows used for the "how many times faster" graph (speed only)
SPEED_ROWS = ["Detect faces 640x480", "Embed 1 face 640x480", "Whole frame 640x480", "Whole frame 320x240",
              "Sustained FPS", "Load models", "Python loop (1M)", "numpy 256x256 multiply", "SD card write"]


def times_faster(slow_value, fast_value, higher_is_better):
    return fast_value / slow_value if higher_is_better else slow_value / fast_value


def print_table(boards):
    slow, fast = boards
    print("\n" + "Measure".ljust(26) + slow["name"].rjust(14) + fast["name"].rjust(14) + "   " + fast["name"] + " is")
    print("-" * 80)
    for label, get, unit, higher_is_better in METRICS:
        a, b = get(slow), get(fast)
        ratio = times_faster(a, b, higher_is_better)
        note = format(ratio, ".1f") + "x better" if ratio >= 1 else format(1 / ratio, ".1f") + "x worse"
        print(label.ljust(26) + (str(a) + " " + unit).rjust(14) + (str(b) + " " + unit).rjust(14) + "   " + note)


# ---------- Graphs ----------
def style(ax, title, unit):
    ax.set_title(title, loc="left", fontsize=11, color=TEXT, pad=10)
    ax.set_ylabel(unit, color=MUTED, fontsize=9)
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9, length=0)


def grouped_bars(ax, boards, labels, values_per_board, title, unit, decimals=1):
    # One group per label, one bar per board, value written above each bar
    width = 0.38
    for i, board in enumerate(boards):
        x = [n + (i - 0.5) * width for n in range(len(labels))]
        bars = ax.bar(x, values_per_board[i], width, color=COLORS[i], hatch=HATCHES[i],
                      edgecolor=SURFACE, linewidth=2, label=board["name"])
        for bar, value in zip(bars, values_per_board[i]):
            ax.annotate(format(value, "." + str(decimals) + "f"), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, color=TEXT_SECONDARY)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.margins(y=0.15)
    style(ax, title, unit)


def draw(boards):
    plt.rcParams["hatch.linewidth"] = 1
    fig, axes = plt.subplots(2, 3, figsize=(16, 9.5))
    fig.patch.set_facecolor(SURFACE)
    fig.suptitle("Smart Cabin - " + boards[0]["name"] + " vs " + boards[1]["name"] +
                 " (same code: YuNet + SFace, 1 face, median)", x=0.01, ha="left", fontsize=14, color=TEXT)

    # 1. Time for each step of the face pipeline
    steps = [("detect", "Detect"), ("embed_per_face", "Embed"), ("match_20_people", "Match 20"),
             ("jpeg_encode", "JPEG")]
    grouped_bars(axes[0][0], boards, [label for key, label in steps],
                 [[median(b, "640x480", key) for key, label in steps] for b in boards],
                 "Time per step, 640x480 (lower is better)", "ms")

    # 2. Whole frame at both picture sizes
    grouped_bars(axes[0][1], boards, ["640x480", "320x240"],
                 [[median(b, size, "whole_frame_1_face") for size in ["640x480", "320x240"]] for b in boards],
                 "Whole frame, 1 face (lower is better)", "ms")

    # 3. Frames per second
    grouped_bars(axes[0][2], boards, ["Max\n640x480", "Max\n320x240", "Sustained\n60 s", "Suggested\nsetting"],
                 [[b["face"]["640x480"]["max_fps"], b["face"]["320x240"]["max_fps"], b["sustained"]["fps"],
                   b["update_delay"]["recommended_fps"]] for b in boards],
                 "Frames per second (higher is better)", "FPS")

    # 4. Temperature during the 60 s sustained run
    ax = axes[1][0]
    for i, board in enumerate(boards):
        s = board["sustained"]
        seconds = [0] + [10 * (n + 1) for n in range(len(s["temp_every_10s_c"]))]
        temps = [s["temp_start_c"]] + s["temp_every_10s_c"]
        ax.plot(seconds, temps, color=COLORS[i], linewidth=2, marker="o", markersize=5,
                markeredgecolor=SURFACE, markeredgewidth=1.5, linestyle="-" if i == 0 else "--", label=board["name"])
        ax.annotate(str(temps[-1]) + " C", (seconds[-1], temps[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=TEXT_SECONDARY)
    ax.axhline(80, color=MUTED, linewidth=1, linestyle=":")
    ax.annotate("80 C: the Pi starts slowing down", (0, 80), xytext=(2, -12), textcoords="offset points",
                fontsize=8, color=MUTED)
    ax.set_xlabel("seconds of full load", color=MUTED, fontsize=9)
    ax.set_ylim(40, 85)
    ax.set_xlim(-2, 70)
    style(ax, "Temperature under full load (no throttling on either)", "C")

    # 5. Update delay
    grouped_bars(axes[1][1], boards, ["Arrive -> Pi page", "Arrive -> laptop page"],
                 [[b["update_delay"]["pi_page_worst_s"], b["update_delay"]["laptop_page_worst_s"]] for b in boards],
                 "Worst-case update delay at suggested FPS (lower is better)", "seconds", decimals=2)

    # 6. How many times faster the faster board is
    ax = axes[1][2]
    rows = [m for m in METRICS if m[0] in SPEED_ROWS]
    ratios = [times_faster(get(boards[0]), get(boards[1]), higher) for label, get, unit, higher in rows]
    y = list(range(len(rows)))[::-1]
    ax.barh(y, ratios, color=COLORS[1], hatch=HATCHES[1], edgecolor=SURFACE, linewidth=2, height=0.6)
    for yy, ratio in zip(y, ratios):
        ax.annotate(format(ratio, ".1f") + "x", (ratio, yy), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=8, color=TEXT_SECONDARY)
    ax.axvline(1, color=MUTED, linewidth=1, linestyle=":")
    ax.set_yticks(y)
    ax.set_yticklabels([row[0] for row in rows])
    ax.set_xlim(0, max(ratios) * 1.18)
    style(ax, "How many times faster is the " + boards[1]["name"], "")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel("x faster (1x = same)", color=MUTED, fontsize=9)

    # One legend for the whole picture
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2, frameon=False, fontsize=10, labelcolor=TEXT)
    fig.text(0.01, 0.01, "Data: pi_benchmark.py, " + boards[0]["system"]["time"] + " and " + boards[1]["system"]["time"] +
             ". Same OS (Debian 13 trixie), Python 3.13, OpenCV 4.10, Camera v2 (imx219).",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(PICTURE, dpi=150, facecolor=SURFACE)
    print("\nGraph saved to", PICTURE)


def main():
    boards = load_results()
    print_table(boards)
    draw(boards)
    if "--no-show" not in sys.argv:
        plt.show()


if __name__ == "__main__":
    main()
