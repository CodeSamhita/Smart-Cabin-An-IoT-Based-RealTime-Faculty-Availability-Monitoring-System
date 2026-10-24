# Smart Cabin server - the status of everyone, for the public page (no login needed).
# Public: name, position, designation, school, department, cabin, status, where, until when. Nothing else.
# Logged-in staff also get: today's and this week's timetable, and when the person is expected back.

from fastapi import APIRouter, HTTPException, Request

import config
import database
import security
import status_engine
import timetable

router = APIRouter()


def public_card(person):
    # The status timer in main.py keeps status_now fresh, so pages only read it
    shown = database.row("SELECT * FROM status_now WHERE account_id = ?", (person["id"],)) \
        or status_engine.refresh(person["id"])
    return {"id": person["id"], "name": person["name"], "position": person["position"],
            "designation": person["designation"], "school": person["school"], "department": person["department"],
            "cabin": person["cabin"] or "", "status": shown["status"], "label": status_engine.LABELS[shown["status"]],
            "reason": shown["reason"], "until": shown["until_text"], "manual": bool(shown["manual"])}


PEOPLE_SQL = ("SELECT a.id, a.name, a.position, a.designation, a.school, a.department, c.name AS cabin "
              "FROM accounts a LEFT JOIN cabins c ON c.owner_id = a.id WHERE a.role = 'faculty' AND a.active = 1 ")


@router.get("/api/people")
def everyone(request: Request):
    people = [public_card(p) for p in database.rows(PEOPLE_SQL + "ORDER BY a.name")]
    account = security.account_from_request(request)
    return {"people": people, "logged_in": account is not None}


@router.get("/api/people/{person_id}")
def one_person(person_id: int, request: Request):
    person = database.row(PEOPLE_SQL + "AND a.id = ?", (person_id,))
    if person is None:
        raise HTTPException(404, "Person not found.")
    card = public_card(person)
    account = security.account_from_request(request)
    card["logged_in"] = account is not None
    if account is None:
        return card

    # Extra details for logged-in staff
    week = timetable.week(person_id)
    for e in week:
        e["day_name"] = config.DAYS[e["day"]]
        e["text"] = timetable.describe(e)
        del e["account_id"]
    today_day, _ = timetable.day_and_minutes()
    current = timetable.current_item(person_id)
    upcoming = timetable.next_item(person_id)
    card["week"] = week
    card["today"] = [e for e in week if e["day"] == today_day]
    card["today_name"] = config.DAYS[today_day]
    card["now"] = timetable.describe(current) + " until " + current["end"] if current else ""
    card["next"] = timetable.describe(upcoming) + " at " + upcoming["start"] if upcoming else ""
    card["back_at"] = timetable.back_at(person_id)
    watch = database.row("SELECT fired FROM watches WHERE watcher_id = ? AND target_id = ? AND fired = 0",
                         (account["id"], person_id))
    card["watching"] = watch is not None
    card["is_me"] = account["id"] == person_id
    return card
