# Smart Cabin server - the SQLite database: the tables, and three small helpers to use them.
# Every helper opens its own connection, so it is safe to call from any web request.
# Times are stored as Unix seconds (time.time()), so they are easy to compare.

import sqlite3

import config

TABLES = """
CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL,              -- 'admin' or 'faculty'
    name          TEXT NOT NULL,
    position      TEXT DEFAULT 'Faculty',     -- Faculty / HOD / Dean
    designation   TEXT DEFAULT '',            -- e.g. Assistant Professor
    school        TEXT DEFAULT '',
    department    TEXT DEFAULT '',
    email         TEXT DEFAULT '',
    active        INTEGER DEFAULT 1,
    created       REAL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,              -- the cookie value is never stored, only its hash
    account_id INTEGER NOT NULL,
    expires    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cabins (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,               -- e.g. Block A, Room 204
    owner_id     INTEGER UNIQUE,              -- the faculty member of this cabin
    token_hash   TEXT,                        -- the cabin device's secret (hashed)
    setup_code   TEXT,                        -- 6-digit code typed on the Pi to get the token
    code_expires REAL,
    enrol_until  REAL DEFAULT 0,              -- the owner logged in on the Pi: setup allowed until then
    device_id    TEXT,                        -- the one device linked to this cabin (the Pi's hardware serial)
    device_name  TEXT,
    last_report  REAL DEFAULT 0,
    created      REAL
);

CREATE TABLE IF NOT EXISTS device_requests (
    device_id  TEXT PRIMARY KEY,              -- a Pi waiting to be added (it says hello every few seconds)
    name       TEXT,                          -- its hostname, e.g. cabin-zero
    model      TEXT,                          -- e.g. Raspberry Pi Zero 2 W Rev 1.0
    ip         TEXT,
    pin        TEXT,                          -- 4 digits, also shown on the Pi's own page: the admin checks they match
    first_seen REAL,
    last_seen  REAL,
    cabin_id   INTEGER,                       -- set when the admin approves it
    token      TEXT                           -- handed to the Pi once on its next hello, then the request is deleted
);

CREATE TABLE IF NOT EXISTS cards (
    uid        TEXT PRIMARY KEY,              -- RFID card id, e.g. A1B2C3D4
    account_id INTEGER NOT NULL,
    added      REAL
);

CREATE TABLE IF NOT EXISTS bt_devices (
    address    TEXT PRIMARY KEY,              -- Bluetooth address, e.g. AA:BB:CC:DD:EE:FF
    account_id INTEGER NOT NULL,
    name       TEXT,
    added      REAL
);

CREATE TABLE IF NOT EXISTS timetable_sheets (
    id         INTEGER PRIMARY KEY,           -- one person can have several timetables (one per school / branch)
    account_id INTEGER NOT NULL,
    name       TEXT NOT NULL,                 -- e.g. "School of Engineering - CSE"
    template   TEXT DEFAULT 'A',              -- A or B (where lunch is)
    saturday   INTEGER DEFAULT 0,             -- 1 = Saturday is a working day
    slots      TEXT DEFAULT '[]',             -- JSON: the day times, e.g. [{"kind": "hour", "start": "09:00", ...}]
    cells      TEXT DEFAULT '{}',             -- JSON: the grid, e.g. {"0-1": {"activity": "Class", ...}}
    updated    REAL
);

CREATE TABLE IF NOT EXISTS timetable (
    id         INTEGER PRIMARY KEY,           -- entries made from all of a person's grids when one is saved
    account_id INTEGER NOT NULL,
    sheet      TEXT DEFAULT '',               -- which timetable it came from
    day        INTEGER NOT NULL,              -- 0 = Monday ... 5 = Saturday
    start      TEXT NOT NULL,                 -- "09:00"
    end        TEXT NOT NULL,                 -- "09:50"
    activity   TEXT NOT NULL,                 -- Class / Lab / Meeting / Break / Office hours / Other
    title      TEXT DEFAULT '',               -- class code or name, e.g. CSE301
    place      TEXT DEFAULT ''                -- e.g. "J block, 4th floor, Room 3"
);

CREATE TABLE IF NOT EXISTS overrides (
    account_id  INTEGER PRIMARY KEY,          -- one active manual button per person
    status      TEXT NOT NULL,                -- green / yellow / red
    reason      TEXT DEFAULT '',
    source      TEXT DEFAULT 'web',           -- web / button
    set_at      REAL,
    until       REAL,                         -- ends by itself at this time
    saw_in      INTEGER DEFAULT 0,            -- the device saw the person in since the button was pressed
    saw_meeting INTEGER DEFAULT 0,            -- the device counted 2 or more since the button was pressed
    low_since   REAL DEFAULT 0                -- headcount <= 1 since this time (for ending "In a meeting")
);

CREATE TABLE IF NOT EXISTS cabin_state (
    cabin_id    INTEGER PRIMARY KEY,          -- the latest evidence from the cabin device
    faculty_in  INTEGER DEFAULT 0,
    headcount   INTEGER DEFAULT 0,
    phone_near  INTEGER DEFAULT 0,
    face_photos INTEGER DEFAULT 0,
    sensors     TEXT DEFAULT '{}',            -- JSON: which sensors work
    updated     REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS status_now (
    account_id     INTEGER PRIMARY KEY,
    status         TEXT DEFAULT 'grey',       -- what is shown: green / yellow / red / grey
    reason         TEXT DEFAULT '',           -- where, e.g. "In class, Room 204"
    until_text     TEXT DEFAULT '',           -- e.g. "until 11:00" or "back around 11:00"
    manual         INTEGER DEFAULT 0,
    since          REAL DEFAULT 0,
    pending_status TEXT DEFAULT '',           -- a new status waiting for the 10 s buffer
    pending_since  REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    time       REAL NOT NULL,
    account_id INTEGER,
    cabin_id   INTEGER,
    kind       TEXT NOT NULL,                 -- arrive, leave, card_login, status, button ...
    detail     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS watches (
    id         INTEGER PRIMARY KEY,
    watcher_id INTEGER NOT NULL,              -- who wants to be told
    target_id  INTEGER NOT NULL,              -- about whom
    created    REAL,
    fired      REAL DEFAULT 0,                -- when the person turned green (0 = not yet)
    shown      INTEGER DEFAULT 0              -- the alert was shown in the watcher's browser
);
"""


def connect():
    conn = sqlite3.connect(config.DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row               # rows can be read like dictionaries: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first version: an older smart_cabin.db gets them on the next start
NEW_COLUMNS = {"cabins": [("device_id", "TEXT"), ("device_name", "TEXT")]}


def create_tables():
    conn = connect()
    conn.execute("PRAGMA journal_mode = WAL")    # lets pages read while a report is being written
    conn.executescript(TABLES)
    for table, columns in NEW_COLUMNS.items():
        have = [r["name"] for r in conn.execute("PRAGMA table_info(" + table + ")")]
        for name, kind in columns:
            if name not in have:
                conn.execute("ALTER TABLE " + table + " ADD COLUMN " + name + " " + kind)
    conn.commit()
    conn.close()


def rows(sql, params=()):
    # All matching rows, as a list of dictionaries
    conn = connect()
    result = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return result


def row(sql, params=()):
    # The first matching row as a dictionary, or None
    found = rows(sql, params)
    return found[0] if found else None


def run(sql, params=()):
    # INSERT / UPDATE / DELETE. Returns the id of a new row.
    conn = connect()
    cursor = conn.execute(sql, params)
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id
