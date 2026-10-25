# Smart Cabin laptop server - reads and writes the CSV files in data/.
# One lock for all files, so two requests never write at the same time.
# A whole-file write goes to a temporary file first, which then replaces the old one,
# so a crash never leaves a half-written file.

import csv
import os
import threading
import time

import settings

lock = threading.RLock()


def path(name):
    return os.path.join(settings.DATA_FOLDER, name)


def read(name):
    # All rows as a list of dictionaries (empty list if the file doesn't exist yet)
    with lock:
        if not os.path.exists(path(name)):
            return []
        with open(path(name), newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))


def write(name, rows, columns):
    # Replace the whole file
    with lock:
        temporary = path(name) + ".tmp"
        with open(temporary, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        for _ in range(20):                       # Windows: the file may be open in Excel for a moment
            try:
                os.replace(temporary, path(name))
                return
            except PermissionError:
                time.sleep(0.1)
        raise RuntimeError(name + " is locked by another program. Close it in Excel and try again.")


def append(name, row, columns):
    # Add one row at the end (used for the logs)
    with lock:
        new_file = not os.path.exists(path(name))
        try:
            with open(path(name), "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
                if new_file:
                    writer.writeheader()
                writer.writerow(row)
        except PermissionError:
            raise RuntimeError(name + " is locked by another program. Close it in Excel and try again.")
