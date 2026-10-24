# Smart Cabin server - the web pages. Each page is its own HTML file in templates/.
# A page that needs a login sends you to /login first, and back afterwards.
#
#   /              everyone's status (public)                 status.html
#   /person/{id}   one person (more details when logged in)   person.html
#   /login         staff login (first start: create admin)    login.html
#   /register      admin: register faculty                    register.html
#   /admin         admin: cabins and cabin devices, activity  admin.html
#   /me            faculty: my status buttons, devices        me.html
#   /timetable     timetable editor (admin: ?person=ID)       timetable.html

import os

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

import config
import security
from api_account import admin_exists

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(config.FOLDER, "templates"))


def page(request, name, title, active, **extra):
    account = security.account_from_request(request)
    values = {"request": request, "account": account, "page_title": title, "active": active,
              "site_title": config.SITE_TITLE, "site_subtitle": config.SITE_SUBTITLE}
    values.update(extra)
    return templates.TemplateResponse(request, name, values)


def go_login(request):
    return RedirectResponse("/login?next=" + request.url.path + ("?" + request.url.query if request.url.query else ""))


@router.get("/")
def status_page(request: Request):
    if not admin_exists():
        return RedirectResponse("/login")          # first start: create the admin account first
    return page(request, "status.html", "Status", "status")


@router.get("/person/{person_id}")
def person_page(request: Request, person_id: int):
    return page(request, "person.html", "Person", "status", person_id=person_id)


@router.get("/login")
def login_page(request: Request):
    return page(request, "login.html", "Login", "login", first_run=not admin_exists())


@router.get("/register")
def register_page(request: Request):
    account = security.account_from_request(request)
    if account is None or account["role"] != "admin":
        return go_login(request)
    return page(request, "register.html", "Register faculty", "register", positions=config.POSITIONS)


@router.get("/admin")
def admin_page(request: Request):
    account = security.account_from_request(request)
    if account is None or account["role"] != "admin":
        return go_login(request)
    return page(request, "admin.html", "Cabins", "admin")


@router.get("/me")
def my_page(request: Request):
    account = security.account_from_request(request)
    if account is None or account["role"] != "faculty":
        return go_login(request)
    return page(request, "me.html", "My page", "me", away_reasons=config.AWAY_REASONS)


@router.get("/timetable")
def timetable_page(request: Request, person: int = 0):
    account = security.account_from_request(request)
    if account is None:
        return go_login(request)
    if account["role"] != "admin":
        person = account["id"]                     # faculty edit only their own
    if not person:
        return RedirectResponse("/register")       # the admin picks a person on the register page
    return page(request, "timetable.html", "Timetable", "me" if account["role"] == "faculty" else "register",
                person_id=person)
