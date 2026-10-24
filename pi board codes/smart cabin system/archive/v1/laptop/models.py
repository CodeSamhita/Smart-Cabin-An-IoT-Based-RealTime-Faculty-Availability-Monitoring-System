# Smart Cabin server - the shape of the data that pages and cabin devices send.
# FastAPI checks every request against these: a missing or wrong field is refused with a clear message,
# before our code runs. (These are the only classes in the project: it is how FastAPI describes data.)

from pydantic import BaseModel


# ---------- Logins ----------
class Login(BaseModel):
    username: str
    password: str


class FirstAdmin(BaseModel):
    username: str
    password: str
    name: str


class NewPassword(BaseModel):
    old_password: str = ""        # needed when you change your own password
    new_password: str


# ---------- Admin ----------
class Faculty(BaseModel):
    username: str
    password: str = ""            # needed when adding, empty = keep when editing
    name: str
    position: str = "Faculty"     # Faculty / HOD / Dean
    designation: str = ""
    school: str = ""
    department: str = ""
    email: str = ""
    active: bool = True


class Cabin(BaseModel):
    name: str
    owner_id: int | None = None
    device_id: str | None = None  # the linked device's ID (Pi serial); typed in advance from the box label, or None


# ---------- Faculty ----------
class StatusButton(BaseModel):
    mode: str                     # available / meeting / away / auto
    reason: str = ""              # for "away": Busy / On a break / Meeting outside / On leave
    minutes: int = 60             # for "away": how long


class Slot(BaseModel):
    kind: str                     # hour / tea / lunch
    label: str                    # "Hour 1", "Tea break"
    start: str                    # "09:00"
    end: str                      # "09:50"


class Cell(BaseModel):
    activity: str                 # Class / Lab / Meeting / Office hours / Other
    title: str = ""               # class code or name, e.g. CSE301
    building: str = ""            # A ... T
    floor: int = 0                # 0 = ground floor
    number: int = 0               # room or lab number
    continues: bool = False       # True = the 2nd hour of a lab above


class SheetName(BaseModel):
    name: str                     # e.g. "School of CS - BCA"


class TimetableGrid(BaseModel):
    name: str                     # the timetable's name
    template: str                 # A or B
    saturday: bool = False
    slots: list[Slot]
    cells: dict[str, Cell] = {}   # "day-slot", e.g. "0-3" = Monday, 4th slot of the day


# ---------- Cabin device (Pi) ----------
class Claim(BaseModel):
    code: str                     # the 6-digit code from the admin page (fallback way to connect)


class Hello(BaseModel):
    device_id: str                # made once on the Pi, saved in its data folder
    name: str = ""                # hostname
    model: str = ""               # board model
    pin: str = ""                 # 4 digits shown on the Pi's page


class Approve(BaseModel):
    cabin_id: int | None = None   # an existing cabin ...
    new_cabin: str = ""           # ... or the name of a new one, e.g. "J block, 4th floor, Cabin 12"
    owner_id: int | None = None   # the registered faculty member who sits there (optional)


class DeviceEvent(BaseModel):
    kind: str                     # arrive, leave, card_login, card_logout, card_unknown, headcount, button ...
    detail: str = ""
    time: float = 0


class Report(BaseModel):
    faculty_in: bool
    headcount: int
    phone_near: bool = False
    face_photos: int = 0
    sensors: dict = {}            # e.g. {"camera": "ok", "rfid": "error: not responding"}
    button: str = ""              # hardware button pressed since the last report: available / meeting / away / auto
    events: list[DeviceEvent] = []


class EnrolLogin(BaseModel):
    username: str
    password: str


class CardLink(BaseModel):
    uid: str


class BluetoothDevice(BaseModel):
    address: str
    name: str = ""
