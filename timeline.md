# Smart Cabin – Timeline

A day-by-day log of what was done, what was tried, and what worked. Newest entry first.

Template for each entry:

```
## YYYY-MM-DD – short title
**Done:**
**Tried / tested:**
**What worked:**
**What didn't / why:**
**Next:**
```

---

## 2026-10-21 – Pi Zero 2W back: live camera web stream

**Done:**
- The user is using the Pi Zero 2W again over SSH.
- New `pi/` folder: `config.py`, `camera.py`, `stream_server.py`, `main.py`, `README.md`.
  - The camera runs in a background thread and keeps the newest frame as a JPEG. It supports the Pi Camera (picamera2) or a USB webcam (OpenCV).
  - Uses the built-in `http.server`, so there's nothing to pip install. Routes: `/` (page), `/stream.mjpg` (live MJPEG), `/snapshot.jpg` (one frame, for laptop YOLO later, like the old ESP32 `/capture`).
  - Open from the laptop at `http://localhost:8000` via SSH tunnel (`ssh -L 8000:localhost:8000 ...`) or at `http://<pi-ip>:8000`.

**Tried / tested:**
- On the laptop with a fake frame: page 200, snapshot returned, stream sends `--frame` parts.

**What didn't / why:**
- Not yet run on the real Pi or camera.

**Next:**
- Run on the Pi and check the FPS at 640x480. If it's slow, lower the size or FPS in `config.py`.
- Laptop reads `/snapshot.jpg` → YOLOv8n headcount.

---

## 2026-10-21 – Rescope to laptop-only, demo web UI

**Done:**
- Decided to build on the laptop only for now. No ESP32 or Pi camera. External hardware comes later.
- Decided to keep the code simple and modular: small files of plain functions plus one `main.py`.
- Built the demo web UI in plain HTML/CSS/JS (`web/`). It runs without a server.
  - `index.html`: public status page (status card, reason, expected return, last checked, today's timetable, "How we know" evidence, system health and sensors, colour legend, demo buttons, privacy note).
  - `hod.html`: HOD panel (demo login, manual override with expiry, timetable editor with CSV upload, status history).
  - The sensors panel shows RFID, fingerprint, face recognition, BLE and thermal as "planned (future)".
- Python launches and feeds the page (`code/`): `config.py`, `demo_data.py`, `webpage.py`, `main.py`.
  - Python writes `web/data.js`, and the page re-reads it every 10 s.
- Added `.gitignore` and this `timeline.md`.
- Added `code/requirements.txt` and `code/install_requirements.py`. The script checks the Python version, installs the libraries with pip, then checks that each one imports.
- Added "Hardware buttons" as a planned sensor in the UI, because physical Available / Busy / Back soon buttons may come in future. The HOD panel notes that its override buttons can later also come from hardware.

- **UI redesign (same day):** made it simpler and changed it from one HOD to many HODs and faculty across departments.
  - People and timetables now come from `data/people.csv` and `data/timetable.csv`, read by the new `code/people.py`.
  - `index.html` is now a grid of cards grouped by department, with keyword search (every typed word must match the name, role, department, cabin or status) and a department filter.
  - New `person.html?id=...` page per person.
  - `hod.html` replaced by `staff.html`: any HOD or faculty member picks their name and logs in (demo password `staff123`).
  - Sensors, health and demo buttons moved to a separate `system.html`, so the public pages show only status.
  - Shared helpers moved into `web/common.js`, with one small JS file per page.
  - Demo: `main.py` gives everyone a status, then changes one random person every 10 s. If the timetable says they're in class right now, they show as Away with the class as the reason.

- **Real university data (same day):** loaded Presidency University, Bengaluru faculty and programmes from presidencyuniversity.in.
  - New `code/fetch_presidency_data.py` reads the 11 school faculty pages and 10 department pages: 839 faculty (11 Deans, 23 HODs, 805 faculty) and 114 programmes, saved to `data/people.csv` and `data/programs.csv`.
  - New columns: designation (full title from the website), role (Dean / HOD / Faculty, worked out from the designation), and school.
  - The website has no cabin numbers or timetables, so cabin is empty and `data/timetable.csv` is a random **demo** timetable (2 classes a day).
  - Home page now has School and Role filters, with department headings like "Physics - Engineering (21)". New `programs.html` page.
  - `main.py` now changes 5 random people every 10 s. The timetable is grouped per person so lookups stay fast.
  - The user likes the flat UI, so it stays as it is for now.
  - Replaced the School and Role drop-downs with quick select buttons (rounded "chips"; the chosen one is dark). One click filters, and the choice stays when the page auto-refreshes. Tested: HODs + Computer Science and Engineering → 4 people.
  - My shortened school names ("AI and Advanced Computing", "Physics - Engineering") confused the user. Switched to the **official names from the website**: `people.csv` and `programs.csv` now store e.g. "Presidency School of Artificial Intelligence and Advanced Computing" and "Department of Physics". Buttons and headings show them without "Presidency" (e.g. "School of Law", "Department of Physics - School of Engineering"). Schools now appear in the same order as on the website. The AI school page's 136 faculty were already included, so no one was removed.
  - Added a header to every page that stays at the top while scrolling: Smart Cabin, Presidency University, Bengaluru, and links (Faculty status / Programmes / Staff login / System; the current page is highlighted). The links moved up from the bottom of the page. Added the same footer to every page (privacy note + project line). On phones the subtitle is hidden so the 4 links fit on one row.
  - Tested: the header stays at the top after scrolling, all pages show the header and footer, and there's no sideways scroll at 375 px.
  - **Programmes divided by degree:** `fetch_presidency_data.py` now works out each programme's degree and level from its name (`degree_of()` with a simple lookup list). All 114 were classified, none left as "Other": 72 Bachelor's (B.Tech 19, B.A. 21, BBA 6, B.Com 6, ...), 18 Master's (M.Tech 6, MBA 5, ...), 18 Ph.D, 6 Diploma. The programmes page now groups by degree, with Level and Degree quick select buttons. Picking a level shows only that level's degrees.
  - Bug found: some programme names from the website contained HTML (`<br> <span ...>`). Fixed `clean()` to remove HTML tags; checked that no `<` is left in the CSV files.
  - Tested: Master's → 18 (7 degree buttons), M.Tech → 6, search "data" → 8 across B.Tech / BCA / B.Sc / M.Tech / M.Sc / PG Diploma.

**Tried / tested (real data):**
- Searches on 839 people take 1–11 ms. "physics" → 21, HOD filter → 23, Dean filter → 11, Engineering school → 229.
- Programmes page: 114 shown, "m.tech" → 5.
- Staff login lists all 839 people; an override works for Dr. Nakul Ramanna Sanjeevaiah.
- Bug found: on Windows, `os.replace` on `data.js` failed with "Access is denied" when another program had the file open, which crashed `main.py`. Fixed by retrying up to 10 times, then skipping that cycle instead of crashing.
- `data.js` is now about 1 MB. That's fine for a local file.

- **Research papers:** found and checked 5 more papers (numbers 6–10), written up in `research/papers.md` with a summary, relevance to Smart Cabin, comparison table and draft research gap:
  - 6: SILA 2024 (ESP32 lecturer availability, manual)
  - 7: Monti 2022 (camera snapshots + Raspberry Pi + YOLOv3, count only)
  - 8: Ahmad 2021 (occupancy survey + privacy-preserving camera)
  - 9: Chen 2018 (occupancy review)
  - 10: Ahamed 2024 (edge CPU people counting, TENCON)
  - Added to README references. Details confirmed from publisher/arXiv pages. Full PDFs of 6 and 10 are still to be read.
  - **User feedback: papers 7–10 were not related to the topic.** They were about counting people in buildings to save energy, not faculty availability. Agreed scope: faculty availability systems, cabin/door status displays, faculty presence by face recognition, timetable-based availability, 2020+ only.
  - Replaced papers 7–10 (kept 6, SILA) with: 7 Soppari 2025 (faculty presence by webcam face recognition), 8 IJSRED 2026 (faculty tracking with RFID + app), 9 Saxena 2024 (RFID tracking of students and professors), 10 CNLAS 2026 (lecturer availability app, weak source). Rewrote the comparison table and research gap.
  - Finding: faculty availability papers are mostly in smaller journals, none of the 2020+ ones uses timetables, and none reports measured accuracy. Both points go into the research gap.
  - Also confirmed the title of README paper 2 (Za'bah & Mohamad 2021, IIUM). Two more candidates (IJRDST, INDJST) couldn't be opened, so they're listed as "to get from library".

**Tried / tested (redesign):**
- Search: "hod" → 4 HODs, "computer available" → 1, "cabin 104" → 1, "xyz" → "No one matches".
- Staff login as Dr. B. Rao, set "In a meeting, back at 15:00" → his card and page show Away with "Set manually".
- System page: demo set and clear-all work, and the counts and sensor list show.
- `main.py` loop (run without opening a browser for 3 cycles) → 3 changes written to `data.js` and to history.
- Phone width → cards stack in one column, with no sideways scrolling.

**Tried / tested:**
- Demo buttons (green / yellow / red / grey) → the card, icon, reason and evidence all update.
- HOD override "In meeting, back at 15:00" → the status page shows it with the "Set manually" tag.
- Python wrote a new status while the page was open → the page updated within 10 s, with no reload and no server.
- Phone width (375 px) → the layout stacks, with no sideways scrolling.

**What worked:**
- Loading data through `<script src="data.js">` instead of `fetch()`. Browsers block `fetch()` on files opened directly (`file://`), but a script tag works.
- Writing `data.js` to a temp file first and then swapping it in, so the page never reads a half-written file.

**What didn't / why:**
- The CSS class `.hidden` was being overridden by `.tag`, so "Set manually" always showed. Fixed with `!important` on `.hidden`.
- Overrides and timetable edits are saved in the browser (localStorage), so Python can't see them yet. That's fine for the demo; a small server comes later.

**Next:**
- Read the research papers: summaries plus relevance in `research/papers.md`.
- Bring back the camera headcount (webcam) as modules (`camera.py`, `detector.py`) and feed the real count into `write_status()`.
- Simple status rules + timetable CSV in Python.

**Deferred (decide after Review 1):**
- Standalone compact device: ESP32-S3 / ESP32-CAM vs Raspberry Pi. Also which detector can run on it (YOLOv8n is too heavy for a plain ESP32).

---

## 2026-10 (before 21 Oct) – Raspberry Pi Zero 2W tried

**Tried / tested:** Raspberry Pi Zero 2W as the camera / processing device.
**What didn't / why:** Remote sessions (SSH / remote desktop) were troublesome to work with.
**Decision:** Pi set aside for now. Build the prototype on the laptop first.
**Also found:** the ESP32 with camera can both send and receive (snapshots over HTTP), so it remains an option.

---

## 2026-10 – Iteration 0: snapshot → headcount

**Done:** `code/import time.py`: the laptop asks the ESP32-CAM for a JPEG every 10 s (`GET /capture` with an `X-Token` header), and YOLOv8n counts the people in it.
**What worked:** counting with the YOLOv8 nano model (person class, confidence 0.4). A new count is only accepted after 3 readings in a row agree, which stops flicker.
**What didn't / notes:** the camera IP and token are hardcoded, and debug mode needs a screen. To be cleaned up when the camera code is restructured.

---

## 2026-10-08 – Design document v0.1

**Done:** wrote the full design in `README.md`: problem and aim, design principles, architecture, status model, technology register, security and privacy, iteration roadmap, evaluation plan, references.

---

## 2026-09-29 to 10-02 – Review 0

**Done:** topic, problem identification and literature survey presented. Review 0 complete.
