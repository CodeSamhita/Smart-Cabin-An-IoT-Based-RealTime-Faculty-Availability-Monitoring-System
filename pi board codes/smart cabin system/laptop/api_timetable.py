# Smart Cabin server - the timetable editor's data. A faculty member edits their own timetables;
# the admin can edit anyone's. One person can have several timetables (one per school / branch).
# (BUILD_PLAN.md section 2b)

from fastapi import APIRouter, Depends, HTTPException

import config
import database
import security
import timetable
from models import SheetName, TimetableGrid

router = APIRouter()


def allowed_person(person_id, account):
    # Who may edit these timetables: the person themselves, or the admin
    if account["role"] != "admin" and account["id"] != person_id:
        raise HTTPException(403, "You can only edit your own timetable.")
    person = database.row("SELECT id, name, school, department FROM accounts WHERE id = ? AND role = 'faculty'", (person_id,))
    if person is None:
        raise HTTPException(404, "Person not found.")
    return person


def their_sheet(person_id, sheet_id):
    sheet = database.row("SELECT id FROM timetable_sheets WHERE id = ? AND account_id = ?", (sheet_id, person_id))
    if sheet is None:
        raise HTTPException(404, "Timetable not found.")


@router.get("/api/timetable/{person_id}")
def get_timetables(person_id: int, account=Depends(security.need_login)):
    person = allowed_person(person_id, account)
    if not timetable.sheets(person_id):
        # The first timetable is named after their school / department
        timetable.new_sheet(person_id, " - ".join(x for x in (person["school"], person["department"]) if x) or "My timetable")
    busy = [{"sheet": e["sheet"], "day": e["day"], "start": e["start"], "end": e["end"], "text": timetable.describe(e)}
            for e in timetable.week(person_id) if e["activity"] != "Break"]
    return {"person": person, "sheets": timetable.sheets(person_id), "busy": busy,
            "templates": {name: timetable.make_slots(name) for name in config.TEMPLATES},
            "lengths": {"hour": config.CLASS_MINUTES, "tea": config.TEA_MINUTES, "lunch": config.LUNCH_MINUTES},
            "days": config.DAYS[:6], "activities": config.ACTIVITIES, "buildings": config.BUILDINGS,
            "floors": [{"value": f, "label": timetable.floor_text(f)} for f in config.FLOORS],
            "numbers": config.ROOM_NUMBERS}


@router.post("/api/timetable/{person_id}/sheets")
def add_sheet(person_id: int, data: SheetName, account=Depends(security.need_login)):
    allowed_person(person_id, account)
    if not data.name.strip():
        raise HTTPException(400, "Give the timetable a name, e.g. School of CS - BCA.")
    new_id = timetable.new_sheet(person_id, data.name.strip()[:60])
    return {"ok": True, "id": new_id}


@router.put("/api/timetable/{person_id}/sheets/{sheet_id}")
def save_sheet(person_id: int, sheet_id: int, data: TimetableGrid, account=Depends(security.need_login)):
    allowed_person(person_id, account)
    their_sheet(person_id, sheet_id)
    if data.template not in config.TEMPLATES:
        raise HTTPException(400, "Pick template A or B.")
    if not data.name.strip():
        raise HTTPException(400, "Give the timetable a name.")
    slots = [s.model_dump() for s in data.slots]
    problem = timetable.check_slots(slots)
    if problem:
        raise HTTPException(400, problem)

    cells = {}
    for key, cell in data.cells.items():
        try:
            day, slot = [int(n) for n in key.split("-")]
        except ValueError:
            raise HTTPException(400, "Bad grid cell: " + key)
        if not 0 <= day <= 5 or not 0 <= slot < len(slots) or slots[slot]["kind"] not in config.NUMBERED:
            continue                                   # ignore cells outside the grid
        if cell.activity not in config.ACTIVITIES:
            raise HTTPException(400, "Unknown activity: " + cell.activity)
        if cell.building and cell.building not in config.BUILDINGS:
            raise HTTPException(400, "Unknown block: " + cell.building)
        if cell.floor not in config.FLOORS or (cell.number and cell.number not in config.ROOM_NUMBERS):
            raise HTTPException(400, "Unknown floor or room number.")
        cells[key] = cell.model_dump()

    timetable.save_sheet(sheet_id, data.name.strip()[:60], data.template, data.saturday, slots, cells)
    clashes = timetable.rebuild(person_id)
    return {"ok": True, "entries": len(timetable.week(person_id)), "clashes": clashes}


@router.delete("/api/timetable/{person_id}/sheets/{sheet_id}")
def delete_sheet(person_id: int, sheet_id: int, account=Depends(security.need_login)):
    allowed_person(person_id, account)
    their_sheet(person_id, sheet_id)
    database.run("DELETE FROM timetable_sheets WHERE id = ?", (sheet_id,))
    timetable.rebuild(person_id)
    return {"ok": True}
