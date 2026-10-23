# Installs all the libraries Smart Cabin needs.
# Run once:  python install_requirements.py
# It uses the same Python you run it with, so the libraries end up in the right place.

import os
import subprocess
import sys

# Library name for pip -> name used in "import"
LIBRARIES = {
    "opencv-python": "cv2",
    "numpy": "numpy",
    "ultralytics": "ultralytics",
}


def check_python():
    # ultralytics needs Python 3.8 or newer
    if sys.version_info < (3, 8):
        print("Python 3.8 or newer is needed. You have", sys.version.split()[0])
        sys.exit(1)
    print("Python", sys.version.split()[0], "- OK")


def install_all():
    folder = os.path.dirname(os.path.abspath(__file__))
    req_file = os.path.join(folder, "requirements.txt")

    print("\nUpdating pip...")
    subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    print("\nInstalling libraries from requirements.txt...")
    result = subprocess.call([sys.executable, "-m", "pip", "install", "-r", req_file])
    if result != 0:
        print("\npip reported a problem. Check the messages above.")


def check_imports():
    # Try importing each library to make sure it really works
    print("\nChecking libraries:")
    all_ok = True
    for pip_name, import_name in LIBRARIES.items():
        try:
            __import__(import_name)
            print("  [OK]     ", pip_name)
        except ImportError:
            print("  [MISSING]", pip_name)
            all_ok = False

    if all_ok:
        print("\nAll libraries installed. You are ready to go.")
    else:
        print("\nSome libraries are missing. Try: python -m pip install <name>")


if __name__ == "__main__":
    check_python()
    install_all()
    check_imports()
