# Smart Cabin server - logging in and out, the first admin account, changing your password.

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

import config
import database
import security
from models import FirstAdmin, Login, NewPassword

router = APIRouter()


def admin_exists():
    return database.row("SELECT 1 FROM accounts WHERE role = 'admin'") is not None


def clean_username(text):
    # Usernames are stored in lower case without spaces, so "Dr.Rao " and "dr.rao" are the same
    return text.strip().lower().replace(" ", "")


@router.post("/api/setup")
def create_first_admin(data: FirstAdmin):
    # Only works once: when there is no admin yet
    if admin_exists():
        raise HTTPException(403, "An admin already exists. Log in instead.")
    problem = security.password_problem(data.password)
    if problem:
        raise HTTPException(400, problem)
    if not clean_username(data.username) or not data.name.strip():
        raise HTTPException(400, "Fill in a username and a name.")
    database.run("INSERT INTO accounts (username, password_hash, role, name, position, created) "
                 "VALUES (?, ?, 'admin', ?, 'Admin', ?)",
                 (clean_username(data.username), security.hash_password(data.password), data.name.strip(), time.time()))
    return {"ok": True}


@router.post("/api/login")
def login(data: Login, response: Response):
    account, token = security.login(clean_username(data.username), data.password)
    if account is None:
        time.sleep(1)                                  # slows down password guessing
        raise HTTPException(401, "Wrong username or password.")
    response.set_cookie(security.COOKIE, token, max_age=config.SESSION_HOURS * 3600, httponly=True, samesite="lax")
    return {"ok": True, "role": account["role"], "name": account["name"]}


@router.post("/api/logout")
def logout(request: Request, response: Response):
    security.logout(request.cookies.get(security.COOKIE))
    response.delete_cookie(security.COOKIE)
    return {"ok": True}


@router.get("/api/me")
def who_am_i(account=Depends(security.need_login)):
    return {"id": account["id"], "username": account["username"], "role": account["role"], "name": account["name"]}


@router.post("/api/me/password")
def change_password(data: NewPassword, account=Depends(security.need_login)):
    if not security.check_password(data.old_password, account["password_hash"]):
        raise HTTPException(400, "Your current password is wrong.")
    problem = security.password_problem(data.new_password)
    if problem:
        raise HTTPException(400, problem)
    database.run("UPDATE accounts SET password_hash = ? WHERE id = ?",
                 (security.hash_password(data.new_password), account["id"]))
    return {"ok": True}
