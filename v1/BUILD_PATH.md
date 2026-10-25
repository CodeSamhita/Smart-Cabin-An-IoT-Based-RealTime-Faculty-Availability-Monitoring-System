# Smart Cabin v1 – build plan (from scratch)

Written 24 Oct 2026, **before any code**. Revised the same day with the user's changes (see *Change log*). A box is ticked only after it was checked on the real hardware or in the browser.

**Primary goal:** is the person **in their cabin or not**, shown correctly. Everything else comes after.

This is a **research prototype**: every part must really work and be easy to troubleshoot, but it is not a finished product. The laptop is the server.

---

## 1. The idea in short

- **Edge devices** (Pi + camera + RC522 + NeoPixel + built-in Bluetooth) stay fixed in a **location** (a cabin / room). A device has **no owner**: the admin **assigns a person** to it, and can move that person to another device any time. The old assignment is kept as history.
- Each device works out on the Pi: **face seen (F), card tapped in (R), phone near (B), headcount**, and sends only these numbers to the laptop. No pictures leave the Pi.
- The laptop combines them into **one confidence** (the F × R × B table from today's test 10) and a status: Available / In a meeting / Not available / Unknown.
- **Three pages:** admin (login), person (login, works on a phone), public lookup (no login).
- **No database.** Everything is kept in **CSV files**, one per kind of data, named after what they hold.
- **Data science:** confidence from the sensors (learned from logs), a steady status (no flicker), and predictions (when the person usually comes back / is usually available).
- **Later:** a small OLED / LCD on the device for the return time.

---

## 2. Registration (simple, works on a phone)

1. The person opens `http://<laptop>:8080/register` on their phone.
2. Types their name: the page finds them in the **university list** (`people.csv`, 839 faculty already collected from the website) and fills in designation, school and department. Not in the list → they type the details.
3. Chooses a username and password → saved in `accounts.csv` (password as a hash, never as text).
4. The admin assigns them to a device (location).
5. Standing at that device, they press **Link my card**, **Register my face**, **Add my phone** on their phone. The device does it and shows the progress on their page ("photo 3 of 10", then done / the reason it failed).

---

## 3. CSV files (laptop, folder `data/`)

| File | Holds |
|---|---|
| `people.csv` | the university faculty list (id, name, designation, role, school, department), from the website. **Existing** |
| `programs.csv` | schools and their programmes (B.Tech, M.Tech, …). **Existing** |
| `timetable.csv` | person, day, start, end, activity, room. **Existing demo data**, replaced person by person as real timetables are entered |
| `accounts.csv` | person id, username, password hash, role (admin / person), phone-friendly contact, created |
| `devices.csv` | device id (Pi serial), name, location (block, floor, room), model (Zero 2W / Pi 4), added |
| `device_assignments.csv` | device id, person id, from, to (empty = current). History of who sat where |
| `rfid_cards.csv` | card id, person id, added |
| `bluetooth_phones.csv` | Bluetooth address, phone name, person id, added (up to 5 each) |
| `face_registrations.csv` | person id, device id, photos, registered (the face itself stays on the Pi) |
| `manual_status.csv` | person id, status set by hand, until when |
| `status_now.csv` | person id, status, confidence, where, until, updated (what the pages show) |
| `presence_log.csv` | every report: time, device, person, F, R, B, headcount, confidence, status. **The data for the machine learning and the paper** |
| `device_health.csv` | device id, time, temperature, CPU, memory, each part's state, last error |
| `events_log.csv` | arrive, leave, tap, assignment, manual status, errors, in words |

**On the Pi** (folder `data/`): `faces/<person id>.npy` (10 × 128 numbers, no photos), plus copies of the assigned person's card and phones so it works when the laptop is off.

CSV safety: one lock per file, writes go to a temporary file that then replaces the old one (Windows "access denied" retry, found earlier), and `presence_log.csv` only ever has rows added.

---

## 4. Machine learning (the data-science part)

| Where | Algorithm | What it gives | Data |
|---|---|---|---|
| **Presence confidence** | start: the F R B table from test 10 (8 rows, 2 % – 99 %). Then **Naive Bayes / logistic regression** trained on `presence_log.csv` with ground truth | "in the cabin, 92 % sure" instead of a hand-set guess | ground-truth notes from test days |
| **Steady status** | **hysteresis + time window** (in only above 70 %, out only below 30 %, held for a few reports); later a 2-state **Hidden Markov Model** if time allows | no flicker when a face is missed for a moment | the same log |
| **Prediction** | per person: **availability by weekday × hour** (from the log and timetable), then **logistic regression / random forest** (features: weekday, hour, timetable activity, minutes since leaving) | "usually back around 11:40", "usually available Tue 14:00–16:00" on the public page | `presence_log.csv` + `timetable.csv`. Until real logs exist, a clearly labelled **synthetic log** made from the timetable |
| **Evaluation** | accuracy, precision / recall of "in", time to correct status, what each sensor adds (ablation of F, R, B) | numbers for the paper | the logs |

Library: scikit-learn on the laptop only (the Pi does no learning).

---

## 5. Keeping the Pi cool

No video. **One picture every 5 s** when nothing happens, every 1.5 s for 30 s after a change. Headcount on every picture (MobileNet-SSD on the Zero, YOLOv8n on the Pi 4). Face check only when someone is in the picture and only every 30 s once the person is confirmed in, searched inside person boxes only. OpenCV on 2 cores. Above 70 °C half as many pictures, above 78 °C vision pauses. Heatsink, no desktop. A 30-minute temperature run on each board for the paper.

---

## 6. Troubleshooting, everywhere

- Every file starts with a comment saying what it does.
- Every button: "Working…" → green message or red message with the reason.
- Every page request: 10 s limit → "the server did not answer".
- Every server route and every Pi part in try / except; answers are always `ok` + a message.
- Page errors show in a red bar. Each Pi part shows OK / PROBLEM + reason; the rest keeps running.
- Device health on the admin page; `logs/server.log`, `logs/edge.log`; a read-only status page on each Pi (port 8000).

---

## 7. Folders

```
v1/
├─ BUILD_PATH.md
├─ for laptop/server/   main.py, settings.py, csv_store.py, accounts.py, devices.py,
│                       confidence.py, status.py, predict.py, pages/, static/, data/, logs/
└─ for pi board/
   ├─ RFID/             hardware check (kept)
   └─ edge/             main.py, settings.py, health.py, link.py, camera.py, people.py,
                        face.py, rfid.py, bluetooth.py, led.py, jobs.py, status_page.py
```

---

## 8. Steps

| # | What | Done when |
|---|---|---|
| 1 | Server skeleton: CSV store, logs, error handling, `/health` | [ ] starts, errors show as messages, server off → page says so |
| 2 | Registration (phone) + login + admin page (people, devices, assignments) | [ ] register from a phone [ ] admin assigns and moves a person, history kept |
| 3 | Edge skeleton: hello, health, status page, reports | [ ] both Pis appear on the admin page with temperature and part states |
| 4 | Sensors on the Pi: RFID, LED, camera, Bluetooth | [ ] each OK on both boards, unplugged part → PROBLEM, rest runs |
| 5 | Setup from the phone: card, face, phone | [ ] each job shows progress and done / reason on the real Pi |
| 6 | Vision + F R B + confidence + steady status | [ ] in / out right in a real cabin [ ] 30-minute temperature run |
| 7 | Public lookup page (search, school / department / programme, status, today's timetable) | [ ] works on a phone, only allowed fields |
| 8 | Whole system on both boards, rehearsal | [ ] full scenario before Review 1 |
| 9 | After Review 1: learned confidence, predictions, evaluation | [ ] numbers in the paper come from the logs |

**Dates:** steps 1–2 by 26 Oct, 3–4 by 29 Oct, 5 by 31 Oct, 6–7 by 2 Nov, 8 on 2 Nov, **Review 1 on 3–6 Nov**, step 9 and the paper by **Review 2 on 8–11 Dec**.

---

## Change log

- 24 Oct 2026 – first path (module by module) written, then replaced by a from-scratch plan.
- 24 Oct 2026 – **user's changes:** no database, CSV files with clear names; a device has no owner, a person is assigned to it and can be moved; primary goal = in the cabin or not; easy registration from a phone; use `people.csv`, `programs.csv`, `timetable.csv`; integrate the F × R × B confidence; add machine learning (confidence, steady status, prediction); OLED later; one single system. Waiting for approval before any code.
