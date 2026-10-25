# Claude codes

The cabin device's software, written step by step from 25 Oct 2026. The plan, with a check for every step, is in [PLAN.md](PLAN.md). After every step the code is copied to the Pi and started, so the update shows on its web page.

**Web page:** http://192.168.137.207:8000 (the Pi on the laptop hotspot)

## Step 1: register a user

On the page, type a name and press **Start registering**, then:

| Step | What happens | Skip? |
|---|---|---|
| 1 Face | **Record my face**: 10 photos of the one face in view, kept only as numbers | yes |
| 2 Card | **Tap my card**: the card's full UID | yes |
| 3 Bluetooth | **Add a device**: pair the phone / laptop / watch (up to 5), only its identity is kept | yes |
| 4 Save | shows what was recorded. **Save** needs at least one of the three | – |

Refused: a name that's already registered, a card or device that belongs to someone else, and a face that matches someone else. **Cancel** forgets the whole registration and unpairs its devices. **Delete** removes a user and unpairs their devices.

## Where it is saved (on the Pi, `~/claude/data/`)

| File | Holds |
|---|---|
| `users.csv` | `user_id, name, card_uid, face_photos, registered` |
| `devices.csv` | `user_id, address, device_name, added` (one row per device) |
| `faces/<user_id>.npy` | the face as numbers: 10 photos × 128 (NumPy). No photos are kept |

## Files

| File | Does |
|---|---|
| `main.py` | starts the threads and the web page |
| `config.py` | every setting |
| `shared.py` | what the threads and the page share (the registration being filled in) |
| `storage.py` | reads and writes the CSV and .npy files |
| `face.py` | camera, YuNet + SFace, the 10 photos |
| `rfid.py` | RC522, reads the card's UID |
| `bluetooth.py` | pairing window, detect-only guard |
| `register.py` | the steps: start, skip, next, back, save, cancel, delete |
| `web.py`, `page.html` | the page |

## Run

From the laptop (copies, starts, prints the address):

    cd "pi board codes"
    powershell -ExecutionPolicy Bypass -File .\deploy_to_pi.ps1 -Folder "claude codes"

On the Pi by hand: `cd ~/claude && sudo python3 main.py`. On a laptop without hardware: `python main.py --sim`.
