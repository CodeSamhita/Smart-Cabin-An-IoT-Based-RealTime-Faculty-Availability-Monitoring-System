# Smart Cabin server - passwords, browser logins (sessions) and cabin device tokens.
#
# Passwords: stored as "pbkdf2$rounds$salt$hash". The real password is never stored.
# Sessions:  after login the browser gets a random token in a cookie. The database keeps only its hash,
#            so a stolen database file can't be used to log in.
# Devices:   each cabin Pi gets its own random token, sent in the X-Device-Token header.

import hashlib
import hmac
import secrets
import time

from fastapi import Header, HTTPException, Request

import config
import database

COOKIE = "sc_session"


# ---------- Passwords ----------
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), config.PASSWORD_ROUNDS).hex()
    return "pbkdf2$" + str(config.PASSWORD_ROUNDS) + "$" + salt + "$" + digest


def check_password(password, stored):
    try:
        _, rounds, salt, digest = stored.split("$")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
    return hmac.compare_digest(test, digest)      # compares in constant time


def password_problem(password):
    # Returns a message if the password is too weak, else ""
    if len(password) < config.MIN_PASSWORD_LENGTH:
        return "Password must be at least " + str(config.MIN_PASSWORD_LENGTH) + " characters."
    return ""


# ---------- Tokens ----------
def new_token():
    return secrets.token_urlsafe(32)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_setup_code():
    return str(secrets.randbelow(1_000_000)).zfill(6)


# ---------- Browser logins ----------
def login(username, password):
    # Returns (account, cookie token) or (None, None)
    account = database.row("SELECT * FROM accounts WHERE username = ? AND active = 1", (username.strip().lower(),))
    if account is None or not check_password(password, account["password_hash"]):
        return None, None
    token = new_token()
    database.run("INSERT INTO sessions (token_hash, account_id, expires) VALUES (?, ?, ?)",
                 (token_hash(token), account["id"], time.time() + config.SESSION_HOURS * 3600))
    database.run("DELETE FROM sessions WHERE expires < ?", (time.time(),))    # tidy up old logins
    return account, token


def logout(token):
    if token:
        database.run("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))


def account_from_request(request):
    # The logged-in account for this browser request, or None
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return database.row(
        "SELECT a.* FROM sessions s JOIN accounts a ON a.id = s.account_id "
        "WHERE s.token_hash = ? AND s.expires > ? AND a.active = 1", (token_hash(token), time.time()))


# FastAPI "dependencies": put one in a route's parameters and the route only runs for the right people
def need_login(request: Request):
    account = account_from_request(request)
    if account is None:
        raise HTTPException(401, "Please log in.")
    return account


def need_admin(request: Request):
    account = need_login(request)
    if account["role"] != "admin":
        raise HTTPException(403, "Only the admin can do this.")
    return account


def need_faculty(request: Request):
    account = need_login(request)
    if account["role"] != "faculty":
        raise HTTPException(403, "Only faculty accounts can do this.")
    return account


# ---------- Cabin devices ----------
def need_device(x_device_token: str = Header(default="")):
    # The cabin of the Pi that sent this request
    cabin = database.row("SELECT * FROM cabins WHERE token_hash = ?", (token_hash(x_device_token),)) \
        if x_device_token else None
    if cabin is None:
        raise HTTPException(401, "Unknown cabin device. Connect it again with a code from the admin page.")
    return cabin
