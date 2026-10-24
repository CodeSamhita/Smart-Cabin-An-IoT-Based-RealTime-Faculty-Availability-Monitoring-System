# Smart Cabin cabin device - its own small files in data/. Nothing here ever goes to the server
# except what server_link.py sends on purpose (never the face data).
#
#   device.json  : the device token (from the 6-digit code) and the cabin name
#   faces.json   : the owner's face (128 numbers per photo) - stays on this device only
#   zones.json   : ignore zones for the people counter (photos / posters on the wall)
#   cache.json   : copy of the owner, cards and phones from the server, for when the laptop is off

import json
import os

import config


def path(name):
    os.makedirs(config.DATA_FOLDER, exist_ok=True)
    return os.path.join(config.DATA_FOLDER, name)


def load(name, default):
    try:
        with open(path(name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(name, data):
    # Write to a temporary file first, then swap it in, so a power cut never leaves half a file
    temp = path(name) + ".tmp"
    with open(temp, "w") as f:
        json.dump(data, f)
    os.replace(temp, path(name))


def delete(name):
    if os.path.exists(path(name)):
        os.remove(path(name))
