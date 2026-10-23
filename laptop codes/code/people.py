# Reads the people list, timetable and programmes from the CSV files in the data folder.

import csv
import os
import time

import config


def read_csv(file_name):
    # Returns a list of rows, each row is a dictionary (column name -> value)
    path = os.path.join(config.DATA_FOLDER, file_name)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_people():
    # people.csv columns: id, name, designation, role, school, department, cabin
    return read_csv("people.csv")


def load_programs():
    # programs.csv columns: school, program, degree, level, duration
    return read_csv("programs.csv")


def load_timetable():
    # timetable.csv columns: person_id, day, start, end, activity
    # Returned as a dictionary: person id -> list of that person's rows (faster to look up)
    timetable = {}
    for row in read_csv("timetable.csv"):
        timetable.setdefault(row["person_id"], []).append(
            {"day": row["day"], "start": row["start"], "end": row["end"], "activity": row["activity"]})
    return timetable


def timetable_for(person_id, timetable):
    # All timetable rows for one person
    return timetable.get(person_id, [])


def current_class(person_id, timetable):
    # The row happening right now for this person, or None
    today = time.strftime("%A")      # e.g. "Monday"
    now = time.strftime("%H:%M")     # e.g. "09:30"
    for row in timetable_for(person_id, timetable):
        if row["day"] == today and row["start"] <= now < row["end"]:
            return row
    return None
