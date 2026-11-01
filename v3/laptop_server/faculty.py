# Smart Cabin laptop server - faculty logins (faculty_accounts.csv, faculty_sessions.csv).
#   suggest_username() : a username from a name: title dropped, lower case, first name of 3+ letters, "." and the
#                        initials of the other words (pravinthraja, shakkeera.l, duraipandian.n)
#   create_all()       : the admin makes everyone's login at once with one default password (valid a few days)
#   login()            : one box: username, server id (f805) or ID card number (digits), told apart by its form
#   set_password()     : the first login (from the default) or a change (current password first)
# Passwords are salted PBKDF2 hashes (security.py); session tokens are stored only as hashes.

import re
import time

import csv_store
import logbook
import people
import security
import settings
from security import UserError

ACCOUNT_COLUMNS = ["person_id", "username", "id_card_number", "password_hash", "must_change", "default_until", "created"]
SESSION_COLUMNS = ["token_hash", "person_id", "expires"]
USERNAME_RULE = re.compile(r"^[a-z0-9.]{3,30}$")
TITLES = re.compile(r"^(dr\.|prof\.|mr\.|ms\.|mrs\.|justice)\s*", re.IGNORECASE)


def accounts():
    return csv_store.read("faculty_accounts.csv")


def account_of(person_id):
    return next((a for a in accounts() if a["person_id"] == person_id), None)


def suggest_username(name):
    words = re.sub(r"[^a-z\s]", " ", TITLES.sub("", name).lower()).split()
    if not words:
        return "user"
    main = next((w for w in words if len(w) >= 3), words[0])
    rest = "".join(w[0] for w in words if w != main)
    return main + "." + rest if rest else main


def suggestions():
    # A unique suggested username for every person (a number added when a name is taken)
    used, result = set(), {}
    for person in people.all_people():
        base = suggest_username(person["name"])
        name, n = base, 1
        while name in used:
            n += 1
            name = base + str(n)
        used.add(name)
        result[person["id"]] = name
    return result


def kind_of(text):
    # What the login box holds: only digits = ID card number, "f" + digits = server id, anything else = username
    if text.isdigit():
        return "card"
    if re.fullmatch(r"[fF]\d+", text):
        return "server"
    return "username"


def check_names(rows):
    # rows: [{person_id, username, id_card_number}]. Raises UserError on the first problem.
    seen_names, seen_cards = {}, {}
    for row in rows:
        person = people.get(row["person_id"])
        if person is None:
            raise UserError("No person " + row["person_id"] + " in the faculty list.")
        name = row["username"].strip().lower()
        if not USERNAME_RULE.match(name) or kind_of(name) != "username":
            raise UserError(person["name"] + ": a username needs 3-30 characters, only a-z, 0-9 and \".\", and not "
                            "only digits or \"f\" + digits.")
        if name in seen_names:
            raise UserError("\"" + name + "\" is used by " + seen_names[name] + " and " + person["name"] + ".")
        seen_names[name] = person["name"]
        card = row.get("id_card_number", "").strip()
        if card:
            if not card.isdigit() or len(card) > 20:
                raise UserError(person["name"] + ": the ID card number must be digits only.")
            if card in seen_cards:
                raise UserError("ID card number " + card + " is used by " + seen_cards[card] + " and " + person["name"] + ".")
            seen_cards[card] = person["name"]


def create_all(rows, default_password, days):
    # The admin's table: every row gets its username / ID card number; everyone who has not set their own password
    # yet gets the default password (valid `days` days) and must change it at the first login.
    if len(default_password) < 8:
        raise UserError("The default password needs 8+ characters.")
    if int(days) not in settings.DEFAULT_PASSWORD_DAYS:
        raise UserError("Valid for: 1, 3, 7 or 14 days.")
    check_names(rows)
    default_hash = security.hash_password(default_password)
    until = time.time() + int(days) * 86400
    with csv_store.lock:
        old = {a["person_id"]: a for a in accounts()}
        result = []
        for row in rows:
            account = old.get(row["person_id"]) or {"person_id": row["person_id"], "must_change": "yes",
                                                     "created": logbook.now_text()}
            account["username"] = row["username"].strip().lower()
            account["id_card_number"] = row.get("id_card_number", "").strip()
            if account.get("must_change", "yes") == "yes":           # still on a default: give the new one
                account.update(password_hash=default_hash, must_change="yes", default_until=until)
            result.append(account)
        csv_store.write("faculty_accounts.csv", result, ACCOUNT_COLUMNS)
    logbook.event("admin", "faculty logins made / updated for %d people (default password for %s days)" % (len(result), days))
    return len(result)


def save_names(person_id, username, id_card_number):
    # The admin changes one person's username / ID card number
    rows = accounts()
    account = next((a for a in rows if a["person_id"] == person_id), None)
    if account is None:
        raise UserError("This person has no login yet. Make the logins on the Faculty logins page first.")
    account["username"], account["id_card_number"] = username, id_card_number
    check_names(rows)
    account["username"] = username.strip().lower()
    csv_store.write("faculty_accounts.csv", rows, ACCOUNT_COLUMNS)


def reset_to_default(person_id, default_password, days=7):
    # Put one person back on a default password (forgotten password, or the default ran out)
    if len(default_password) < 8:
        raise UserError("The default password needs 8+ characters.")
    rows = accounts()
    account = next((a for a in rows if a["person_id"] == person_id), None)
    if account is None:
        raise UserError("This person has no login yet. Make the logins on the Faculty logins page first.")
    account.update(password_hash=security.hash_password(default_password), must_change="yes",
                   default_until=time.time() + int(days) * 86400)
    csv_store.write("faculty_accounts.csv", rows, ACCOUNT_COLUMNS)
    logbook.event("admin", "password reset to a default for " + person_id, "", person_id)


def find(text):
    text = text.strip()
    kind = kind_of(text)
    for a in accounts():
        if (kind == "card" and a["id_card_number"] == text) or (kind == "server" and a["person_id"] == text.lower()) \
                or (kind == "username" and a["username"] == text.lower()):
            return a
    return None


def check(text, password):
    # The account if the username / server id / ID card number and password are right, else None (no session made).
    # Used when a faculty member proves who they are while registering at a device.
    account = find(str(text or ""))
    if account and security.check_password(str(password or ""), account["password_hash"]):
        if account["must_change"] == "yes" and float(account["default_until"] or 0) < time.time():
            return None                                    # an expired default password no longer works
        return account
    time.sleep(1)                                          # slows down password guessing
    return None


def login(text, password):
    # Returns (token, must_change) or raises UserError
    account = find(text)
    if account and security.check_password(password, account["password_hash"]):
        if account["must_change"] == "yes" and float(account["default_until"] or 0) < time.time():
            time.sleep(1)
            raise UserError("Your default password has run out. Ask the admin to reset it.")
        token = security.new_token()
        sessions = [s for s in csv_store.read("faculty_sessions.csv") if float(s["expires"]) > time.time()]
        sessions.append({"token_hash": security.sha256(token), "person_id": account["person_id"],
                         "expires": time.time() + settings.FACULTY_SESSION_HOURS * 3600})
        csv_store.write("faculty_sessions.csv", sessions, SESSION_COLUMNS)
        logbook.event("faculty", "logged in" + (" with the default password" if account["must_change"] == "yes" else ""),
                      "", account["person_id"])
        return token, account["must_change"] == "yes"
    time.sleep(1)                                          # slows down password guessing
    raise UserError("Wrong username or password.")


def session_person(token):
    if not token:
        return ""
    for s in csv_store.read("faculty_sessions.csv"):
        if security.same(s["token_hash"], security.sha256(token)) and float(s["expires"]) > time.time():
            return s["person_id"]
    return ""


def logout(token):
    rows = [s for s in csv_store.read("faculty_sessions.csv") if not security.same(s["token_hash"], security.sha256(token or ""))]
    csv_store.write("faculty_sessions.csv", rows, SESSION_COLUMNS)


def set_password(person_id, current, new, again, first_login=False):
    if len(new) < 8:
        raise UserError("The new password needs 8+ characters.")
    if new != again:
        raise UserError("The two new passwords are not the same.")
    rows = accounts()
    account = next((a for a in rows if a["person_id"] == person_id), None)
    if account is None:
        raise UserError("No login for this person.")
    if first_login:
        if account["must_change"] != "yes":
            raise UserError("Your password is already set.")
    elif not security.check_password(current, account["password_hash"]):
        time.sleep(1)
        raise UserError("The current password is wrong.")
    if security.check_password(new, account["password_hash"]):
        raise UserError("The new password must be different from the old one.")
    account.update(password_hash=security.hash_password(new), must_change="no", default_until="")
    csv_store.write("faculty_accounts.csv", rows, ACCOUNT_COLUMNS)
    logbook.event("faculty", "password changed", "", person_id)


def login_state(account):
    if account is None:
        return "none"
    return "change" if account["must_change"] == "yes" else "active"
