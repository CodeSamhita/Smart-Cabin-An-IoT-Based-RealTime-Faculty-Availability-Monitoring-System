# Smart Cabin laptop server - security.
#   passwords   : salted PBKDF2 hash, never stored as text
#   admin login : a random token in a cookie, only its hash is kept (admin_sessions.csv)
#   setup PINs  : 6 digits for registering a person at a device, 15 min, one use (setup_pins.csv)
#   device keys : made by devices.py with new_token(); only their hash is stored
#   certificate : a self-signed HTTPS certificate, made at the first start

import datetime
import hashlib
import hmac
import ipaddress
import os
import secrets
import socket
import subprocess
import sys
import time

import csv_store
import settings

ADMIN_COLUMNS = ["username", "password_hash", "created"]
SESSION_COLUMNS = ["token_hash", "username", "expires"]
PIN_COLUMNS = ["pin_hash", "device", "expires", "used"]


class UserError(Exception):
    # A mistake by the user (wrong password, missing field). The message is shown on the page as it is.
    pass


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def new_token():
    return secrets.token_urlsafe(32)


def same(a, b):
    return hmac.compare_digest(str(a), str(b))         # takes the same time whether it matches or not


# ---------- passwords ----------
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), settings.PASSWORD_ROUNDS)
    return "pbkdf2$" + str(settings.PASSWORD_ROUNDS) + "$" + salt + "$" + digest.hex()


def check_password(password, stored):
    try:
        _, rounds, salt, digest = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return same(test.hex(), digest)
    except ValueError:
        return False


# ---------- the admin account ----------
def admin_exists():
    return len(csv_store.read("admin_account.csv")) > 0


def create_admin(username, password):
    if admin_exists():
        raise UserError("The admin account already exists. Log in instead.")
    username = username.strip()
    if len(username) < 3 or len(password) < 8:
        raise UserError("Username needs 3+ characters and the password 8+ characters.")
    csv_store.write("admin_account.csv", [{"username": username, "password_hash": hash_password(password),
                                          "created": time.strftime("%Y-%m-%d %H:%M:%S")}], ADMIN_COLUMNS)


def is_admin_name(username):
    return any(same(row["username"], username.strip()) for row in csv_store.read("admin_account.csv"))


def login(username, password):
    # Returns a new session token, or raises UserError
    for row in csv_store.read("admin_account.csv"):
        if same(row["username"], username.strip()) and check_password(password, row["password_hash"]):
            token = new_token()
            sessions = [s for s in csv_store.read("admin_sessions.csv") if float(s["expires"]) > time.time()]
            sessions.append({"token_hash": sha256(token), "username": row["username"],
                             "expires": time.time() + settings.SESSION_HOURS * 3600})
            csv_store.write("admin_sessions.csv", sessions, SESSION_COLUMNS)
            return token
    time.sleep(1)                                      # slows down password guessing
    raise UserError("Wrong username or password.")


def session_user(token):
    # The admin's username for this cookie token, or "" if not logged in
    if not token:
        return ""
    for s in csv_store.read("admin_sessions.csv"):
        if same(s["token_hash"], sha256(token)) and float(s["expires"]) > time.time():
            return s["username"]
    return ""


def logout(token):
    rows = [s for s in csv_store.read("admin_sessions.csv") if not same(s["token_hash"], sha256(token or ""))]
    csv_store.write("admin_sessions.csv", rows, SESSION_COLUMNS)


# ---------- setup PINs ----------
def make_pin(device):
    pin = "%06d" % secrets.randbelow(1000000)
    rows = [r for r in csv_store.read("setup_pins.csv") if float(r["expires"]) > time.time() and r["used"] != "yes"]
    rows.append({"pin_hash": sha256(device + ":" + pin), "device": device,
                 "expires": time.time() + settings.PIN_MINUTES * 60, "used": "no"})
    csv_store.write("setup_pins.csv", rows, PIN_COLUMNS)
    return pin


def check_pin(device, pin, use_it=False):
    # Raises UserError if the PIN is wrong, expired or used. use_it=True marks it used (at the final save).
    rows = csv_store.read("setup_pins.csv")
    for row in rows:
        if row["device"] == device and same(row["pin_hash"], sha256(device + ":" + str(pin).strip())):
            if row["used"] == "yes":
                raise UserError("This setup PIN was already used. Ask the admin for a new one.")
            if float(row["expires"]) < time.time():
                raise UserError("This setup PIN has expired. Ask the admin for a new one.")
            if use_it:
                row["used"] = "yes"
                csv_store.write("setup_pins.csv", rows, PIN_COLUMNS)
            return True
    time.sleep(1)
    raise UserError("Wrong setup PIN for this device.")


# ---------- HTTPS certificate ----------
def laptop_addresses():
    found = {"127.0.0.1", "192.168.137.1"}                 # 192.168.137.1 = the Windows hotspot address
    try:
        for address in socket.gethostbyname_ex(socket.gethostname())[2]:
            found.add(address)
    except OSError:
        pass
    return sorted(found)


def make_certificate():
    # A self-signed certificate for this laptop (browsers warn once; the Pis remember it)
    if os.path.exists(settings.CERT_FILE) and os.path.exists(settings.KEY_FILE):
        return
    try:
        from cryptography import x509
    except ImportError:
        print("Installing 'cryptography' (needed once, to make the HTTPS certificate)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"], check=True)
        from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Smart Cabin server")])
    names = [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(a)) for a in laptop_addresses()]
    start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(start)
            .not_valid_after(start + datetime.timedelta(days=5 * 365))
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .sign(key, hashes.SHA256()))
    os.makedirs(os.path.dirname(settings.CERT_FILE), exist_ok=True)
    with open(settings.KEY_FILE, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                  serialization.NoEncryption()))
    with open(settings.CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
