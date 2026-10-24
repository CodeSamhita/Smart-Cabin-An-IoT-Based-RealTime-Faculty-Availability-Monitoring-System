# Smart Cabin server - installs the Python libraries the server needs, the first time only.
# SQLite needs nothing: it is part of Python.

import importlib
import subprocess
import sys

# import name -> pip name
NEEDED = {"fastapi": "fastapi", "uvicorn": "uvicorn", "jinja2": "jinja2"}


def missing_libraries():
    missing = []
    for module, pip_name in NEEDED.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pip_name)
    return missing


def install_missing():
    missing = missing_libraries()
    if not missing:
        return
    print("First run: installing", ", ".join(missing), "(needs internet, about a minute)...")
    result = subprocess.run([sys.executable, "-m", "pip", "install"] + missing)
    if result.returncode != 0:
        sys.exit("Could not install " + ", ".join(missing) + ". Check the internet connection and run again.")
    importlib.invalidate_caches()
    print("Installed.")
