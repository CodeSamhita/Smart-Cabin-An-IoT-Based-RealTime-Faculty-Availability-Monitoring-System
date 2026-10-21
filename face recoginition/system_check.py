"""
system_check.py - diagnostic report for the face recognition project (face_app.py).

Run it BEFORE face_app.py (or whenever something breaks):
    python system_check.py

It only reads information. It changes nothing on your computer.
It uses only Python's standard library, so it works even if torch/opencv are missing.
"""

import importlib
import importlib.metadata as md
import os
import pickle
import platform
import shutil
import subprocess
import sys
from pathlib import Path

DB_FILE = Path("known_faces.pkl")  # same file face_app.py uses (looked up in the current folder)

# Packages face_app.py needs, and the version limits facenet-pytorch 2.6.0 declares.
PACKAGES = ["torch", "torchvision", "facenet-pytorch", "opencv-python", "numpy", "pillow"]
FACENET_LIMITS = {
    "torch": ">=2.2.0,<2.3.0",
    "torchvision": ">=0.17.0,<0.18.0",
    "numpy": ">=1.24.0,<2.0.0",
    "pillow": ">=10.2.0,<10.3.0",
}

problems = []  # collected so we can print a summary at the end


def section(title: str) -> None:
    print(f"\n=== {title} " + "=" * (60 - len(title)))


def run(cmd: list[str]) -> str | None:
    """Run a command, return its text output, or None if it fails / doesn't exist."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------- 1. Python / OS
def check_python_os() -> None:
    section("Python and operating system")
    print(f"Python version : {platform.python_version()}")
    print(f"Python path    : {sys.executable}")
    print(f"Architecture   : {platform.architecture()[0]} ({platform.machine()})")
    print(f"OS             : {platform.system()} {platform.release()} (build {platform.version()})")
    print(f"Processor      : {platform.processor()}")
    print(f"Current folder : {os.getcwd()}")
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    print(f"Virtual env    : {'YES (you wanted none!)' if in_venv else 'no (global Python)'}")

    if sys.version_info < (3, 10):
        problems.append("Python is older than 3.10; current PyTorch needs 3.10 or newer.")


# ---------------------------------------------------------------- 2. RAM / disk
def check_memory_disk() -> None:
    section("Memory and disk")
    # RAM: psutil is optional; fall back to a Windows command if it's missing.
    try:
        import psutil
        vm = psutil.virtual_memory()
        print(f"RAM total/free : {vm.total / 1e9:.1f} GB / {vm.available / 1e9:.1f} GB")
        print(f"CPU cores      : {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count()} logical")
    except ImportError:
        print(f"CPU cores      : {os.cpu_count()} logical (install psutil for RAM details)")
    total, used, free = shutil.disk_usage(Path.cwd().anchor or "/")
    print(f"Disk free      : {free / 1e9:.1f} GB on {Path.cwd().anchor or '/'}")
    if free < 3e9:
        problems.append("Less than 3 GB free disk space; PyTorch needs a few GB.")


# ---------------------------------------------------------------- 3. NVIDIA driver
def check_nvidia() -> None:
    section("NVIDIA GPU and driver (nvidia-smi)")
    out = run([
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu",
        "--format=csv,noheader",
    ])
    if out is None:
        print("nvidia-smi not found or failed.")
        problems.append("nvidia-smi not available: NVIDIA driver missing or not on PATH.")
        return
    for line in out.splitlines():
        name, driver, mem_total, mem_used, temp = [x.strip() for x in line.split(",")]
        print(f"GPU            : {name}")
        print(f"Driver version : {driver}")
        print(f"VRAM used/total: {mem_used} / {mem_total}")
        print(f"Temperature    : {temp} C")
    # The header of plain `nvidia-smi` shows the highest CUDA version the driver supports.
    full = run(["nvidia-smi"]) or ""
    for part in full.splitlines():
        if "CUDA Version" in part:
            cuda = part.split("CUDA Version:")[1].split("|")[0].strip()
            print(f"Max CUDA (driver supports): {cuda}")
            break


# ---------------------------------------------------------------- 4. Packages
def version_of(pkg: str) -> str | None:
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return None


def check_packages() -> None:
    section("Installed packages")
    for pkg in PACKAGES:
        v = version_of(pkg)
        print(f"{pkg:16}: {v or 'NOT INSTALLED'}")
        if v is None:
            problems.append(f"Package '{pkg}' is not installed.")

    # Compare against facenet-pytorch's declared limits.
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
        for pkg, spec in FACENET_LIMITS.items():
            v = version_of(pkg)
            if v and Version(v.split("+")[0]) not in SpecifierSet(spec):
                print(f"  note: facenet-pytorch officially wants {pkg} {spec} (you have {v})")
    except ImportError:
        print("  (install 'packaging' to compare versions against facenet-pytorch's limits)")


# ---------------------------------------------------------------- 5. PyTorch + GPU
def check_torch() -> None:
    section("PyTorch and GPU test")
    try:
        import torch
    except ImportError:
        print("torch cannot be imported.")
        problems.append("torch is not installed, so face_app.py cannot run.")
        return
    print(f"torch version  : {torch.__version__}")
    print(f"Built for CUDA : {torch.version.cuda}")
    available = torch.cuda.is_available()
    print(f"CUDA available : {available}")
    if not available:
        problems.append(
            "torch cannot see the GPU (face_app.py will use the slow CPU). "
            "Usually a CPU-only torch build was installed; reinstall with the cuXXX index URL."
        )
        return
    print(f"GPU name       : {torch.cuda.get_device_name(0)}")
    # Tiny real computation on the GPU to prove it works end to end.
    try:
        a = torch.randn(1000, 1000, device="cuda")
        _ = (a @ a).sum().item()
        print("GPU math test  : passed")
    except Exception as e:  # noqa: BLE001
        print(f"GPU math test  : FAILED ({e})")
        problems.append("GPU is visible but a simple calculation failed.")


# ---------------------------------------------------------------- 6. Imports used by face_app.py
def check_imports() -> None:
    section("Can face_app.py's imports load?")
    for module in ["cv2", "numpy", "PIL", "torch", "facenet_pytorch"]:
        try:
            importlib.import_module(module)
            print(f"import {module:16}: OK")
        except Exception as e:  # noqa: BLE001
            print(f"import {module:16}: FAILED -> {type(e).__name__}: {e}")
            problems.append(f"'import {module}' fails: {e}")


# ---------------------------------------------------------------- 7. Webcam
def check_webcam() -> None:
    section("Webcams (tries camera index 0 to 3)")
    try:
        import cv2
    except ImportError:
        print("opencv not installed, skipping.")
        return
    found = False
    for idx in range(4):
        # CAP_DSHOW is the Windows camera backend face_app.py uses.
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        cap = cv2.VideoCapture(idx, backend)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                h, w = frame.shape[:2]
                print(f"Camera {idx}: working, {w}x{h}")
                found = True
            else:
                print(f"Camera {idx}: opens but returns no frames (used by another app?)")
        cap.release()
    if not found:
        problems.append("No working webcam found. Close Zoom/Teams/Camera app, or check privacy settings.")


# ---------------------------------------------------------------- 8. Model weights and saved faces
def check_project_data() -> None:
    section("Face model weights and registered faces")
    cache = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch")) / "checkpoints"
    weights = list(cache.glob("*vggface2*")) if cache.exists() else []
    if weights:
        for w in weights:
            print(f"Model weights  : {w.name} ({w.stat().st_size / 1e6:.0f} MB)")
    else:
        print("Model weights  : not downloaded yet (face_app.py downloads ~100 MB on first run)")

    if DB_FILE.exists():
        with open(DB_FILE, "rb") as f:
            db = pickle.load(f)
        print(f"Database file  : {DB_FILE.resolve()}")
        print(f"People saved   : {len(db)}")
        for name, vectors in db.items():  # this is the 'dataset' face_app.py matches against
            print(f"  - {name}: {len(vectors)} samples")
    else:
        print(f"Database file  : {DB_FILE} not found in this folder (no one registered yet)")


# ---------------------------------------------------------------- Summary
def summary() -> None:
    section("SUMMARY")
    if not problems:
        print("No problems found. You can run: python face_app.py")
    else:
        print(f"{len(problems)} problem(s) found:")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")


if __name__ == "__main__":
    check_python_os()
    check_memory_disk()
    check_nvidia()
    check_packages()
    check_torch()
    check_imports()
    check_webcam()
    check_project_data()
    summary()
