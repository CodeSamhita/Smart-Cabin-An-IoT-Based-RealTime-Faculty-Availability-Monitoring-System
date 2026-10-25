# Claude codes – plan

Written **before** coding. Each step says what, why, the expected outcome, and has checkboxes that are ticked only once checked. After every step the code is copied to the Pi and started (`pi board codes/deploy_to_pi.ps1 -Folder "claude codes"`), so the update shows on the Pi's web page.

Code style: small files of plain functions, one `main.py`, short comments.

---

## Step 1 – register a user on the edge device (25 Oct 2026)

- **What:** a web page on the Pi (port 8000) that registers a user, in this order:
  1. **Name** (needed)
  2. **Face:** 10 photos of the one face in view (YuNet + SFace, 128 numbers each). **Skip** allowed.
  3. **RFID card:** tap the card, its full UID (4 or 7 bytes) is kept. **Skip** allowed.
  4. **Bluetooth:** pair the phone / laptop / watch (up to 5), only the identity is kept. **Skip** allowed.
  5. **Save:** only possible when **at least one** of face, card or device was registered.
- **Stored on the Pi** (user's request: CSV for RFID and Bluetooth):
  - `data/users.csv`: `user_id, name, card_uid, face_photos, registered` (one row per user)
  - `data/devices.csv`: `user_id, address, device_name, added` (one row per Bluetooth device, 0 – 5 per user)
  - `data/faces/<user_id>.npy`: the face as numbers, a 10 × 128 NumPy array (one row per photo). **No photos are kept**, only these numbers, which can't be turned back into a picture.
- **Checks while registering:**
  - a card or device already used by another user is refused
  - a face that matches another user is refused
  - a name that is already registered is refused
  - **Cancel** forgets everything of this registration (and unpairs its devices)
- **Registered users** list with **Delete** (also unpairs their devices).
- **Bluetooth stays detect-only:** after pairing the device is untrusted and disconnected, and a guard drops any other connection every 3 s (same as test 10).
- **Files:** `config.py`, `shared.py`, `storage.py`, `face.py`, `rfid.py`, `bluetooth.py`, `register.py`, `web.py`, `page.html`, `main.py`.
- **`--sim`** runs it on a laptop without hardware: photos, card tap and nearby devices are pretended.
- **Why:** every later step (presence, confidence, status) needs to know who the user is and what their face, card and phone are.
- **Outcome:** a user can be registered with any mix of the three, and the values are saved on the Pi.
- **Check:** [x] full flow in `--sim` (all three, only one, none refused) [x] duplicate card / device / name / face refused [x] cancel and delete [x] page at phone width [x] deployed and running on the Pi (camera, RFID, Bluetooth all ready) [ ] face, card and phone registered on the real Pi
- **Tested 25 Oct 2026:** simulation 26 / 26 (whole flow, CSV rows, 10 × 128 face file, refusals, cancel, delete) + 3 / 3 direct checks (duplicate card, same face matched, different face not matched).
