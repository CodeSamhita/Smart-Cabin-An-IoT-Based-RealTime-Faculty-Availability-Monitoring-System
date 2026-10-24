# Smart Cabin cabin device - talking to the laptop server (HTTP + JSON, Python's built-in urllib only).
# Every call carries this device's secret token (X-Device-Token), got once with the 6-digit code.

import json
import urllib.error
import urllib.request

import config
import storage


def token():
    return storage.load("device.json", {}).get("token", "")


def server_url():
    return storage.load("device.json", {}).get("server", config.SERVER_URL)


def call(method, path, data=None, timeout=8, base=None):
    # Returns (ok, answer). answer is the JSON reply, or {"detail": message} when it failed.
    # base: another server address to use (pairing tries the address heard in the broadcast)
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request((base or server_url()) + path, data=body, method=method,
                                     headers={"Content-Type": "application/json", "X-Device-Token": token()})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            answer = json.loads(error.read())
        except ValueError:
            answer = {"detail": "server error " + str(error.code)}
        answer["http_status"] = error.code               # 401 = the server doesn't accept this device's token
        return False, answer
    except (OSError, ValueError) as error:
        return False, {"detail": "Can't reach the laptop at " + (base or server_url()) + " (" + str(error) + "). Is the server "
                                 "running, and does the laptop's firewall allow port 8080?"}


def claim(code, server=None):
    # The 6-digit code from the admin page -> this device's token (saved in data/device.json)
    if server:
        storage.save("device.json", {"server": server.rstrip("/")})
    ok, answer = call("POST", "/api/device/claim", {"code": code})
    if ok:
        storage.save("device.json", {"server": server_url(), "token": answer["token"], "cabin": answer["cabin"]})
    return ok, answer


def get_config():
    return call("GET", "/api/device/config")


def report(evidence):
    return call("POST", "/api/device/report", evidence)


def enrol(username, password):
    return call("POST", "/api/device/enrol", {"username": username, "password": password})


def end_enrol():
    return call("POST", "/api/device/enrol/end", {})


def link_card(uid):
    return call("POST", "/api/device/enrol/card", {"uid": uid})


def add_phone(address, name):
    return call("POST", "/api/device/enrol/phone", {"address": address, "name": name})
