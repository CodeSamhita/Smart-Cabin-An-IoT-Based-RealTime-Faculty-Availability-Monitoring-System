# Smart Cabin – Research papers

Plain-language summaries of papers related to the project, with how each one is relevant to Smart Cabin.
Numbers continue from the reference list in `README.md` section 9 (papers 1–5 are listed there and still need summaries).

**Read status keys:** *Abstract checked* = details confirmed from the publisher or arXiv page. *Full text read* = whole paper read.
Always read the full paper yourself before citing it in the report.

---

## 6. SILA – real-time lecturer availability with ESP32 (2024)

| | |
|---|---|
| Citation | N. Mohamad Nor, S. Zubir, M. S. Shahrudin, "Leveraging IoT to Enhance Real-Time Lecturer Accessibility in Higher Education," *International Journal of Academic Research in Business and Social Sciences*, vol. 14, no. 10, pp. 2990–2999, 2024. DOI: 10.6007/IJARBSS/v14-i10/22959 |
| Link | https://hrmars.com/ijarbss/article/view/22959/Leveraging-IoT-to-Enhance-Real-Time-Lecturer-Accessibility-in-Higher-Education |
| Read status | Abstract checked (the PDF could not be read here, so hardware details and survey numbers are still to be checked) |

- **Problem:** Students waste time looking for lecturers who are not in their rooms.
- **Method:** SILA ("Synced Information on Lecturer Availability") uses ESP32 boards and a web interface. **Lecturers update their own status**, and students see it in real time.
- **Evaluation:** Tested with users for usefulness, satisfaction and usability. The abstract gives no numbers.
- **Limitations:** Fully manual. If the lecturer forgets to update it, the status is wrong. There is no sensing or timetable link.

**Relevance to Smart Cabin:** This is the **closest paper to our exact problem** in a university setting. It is the "manual status" baseline. Our staff override and future hardware buttons do the same job, but Smart Cabin adds **automatic detection (camera) and timetable context**, so it still works when nobody presses anything. Its usability evaluation (usefulness, satisfaction, usability) is a good model for our user survey.

---

## 7. Edge-based classroom occupancy with camera + Raspberry Pi (2022)

| | |
|---|---|
| Citation | L. Monti, R. Tse, S.-K. Tang, S. Mirri, G. Delnevo, V. Maniezzo, P. Salomoni, "Edge-Based Transfer Learning for Classroom Occupancy Detection in a Smart Campus Context," *Sensors*, vol. 22, no. 10, art. 3692, 2022. DOI: 10.3390/s22103692 |
| Link | https://pmc.ncbi.nlm.nih.gov/articles/PMC9143913/ (open access) |
| Read status | Abstract checked (details taken from the open-access article page) |

- **Problem:** Count people in campus classrooms without training a new model for every room.
- **Method:**
  - Intel RealSense D415 camera and a Raspberry Pi 4B. **One snapshot every 5 minutes.**
  - A simplified YOLOv3, fine-tuned with transfer learning on their own classroom images plus COCO.
  - **Only the count and a timestamp leave the device.** A Flask web app shows the counts.
- **Data:** About 2,000 images from 2 classrooms for training, and 1,100 test images from 8 other classrooms.
- **Results:** Accuracy of 94–97% in small rooms and 91–96% in large rooms. Mean absolute error (MAE) between 0.21 and 1.23 people.
- **Limitations:**
  - It over-counts when there are more than 30 people, because people far away (8–12 m) look tiny.
  - Tested on one campus only, and the dataset is not public.

**Relevance to Smart Cabin:** **Very close to our design**: periodic snapshots instead of video, an edge device, YOLO, and only a count stored. That matches our "status, not footage" rule. It also gives us a ready **evaluation method** (accuracy, MAE, RMSE against a manual count). A faculty cabin is small, with 1–5 people a few metres away, so we should avoid their main error source. It also supports a Raspberry Pi as a possible standalone device.

---

## 8. Occupancy detection survey + privacy-preserving camera counting (2018/2021)

| | |
|---|---|
| Citation | J. Ahmad, H. Larijani, R. Emmanuel, M. Mannion, A. Javed, "Occupancy detection in non-residential buildings – A survey and novel privacy preserved occupancy monitoring solution," *Applied Computing and Informatics*, vol. 17, no. 2, pp. 279–295, 2021 (online 2018). DOI: 10.1016/j.aci.2018.12.001 |
| Link | https://www.emerald.com/aci/article/17/2/279-295/6028 (open access) |
| Read status | Abstract checked (details taken from the open-access article page) |

- **Survey:** Compares 6 ways of detecting occupancy:
  - **Cameras:** detailed, but raise privacy problems.
  - **PIR:** cheap, but only yes/no, and it misses people sitting still.
  - **Ultrasonic:** prone to false "on" readings.
  - **RF/RFID:** affected by radio conditions.
  - **Sensor fusion:** accurate, but costly.
  - **Wi-Fi/Bluetooth:** reuses existing networks, but gives false positives.
- **Their solution:** An overhead camera finds people by background subtraction, then **scrambles (encrypts) only the regions where people are**. It tracks and counts people crossing a line while the image stays encrypted.
- **Results:** Encryption added only about 1 ms per frame, and they say counting accuracy did not change.
- **Limitations:** No overall counting accuracy is reported, and the security test used a single frame with one person.

**Relevance to Smart Cabin:**
- Useful for the **literature review table** and for justifying our sensor choices. It shows PIR misses people sitting still, which is why we rejected PIR.
- It shows cameras need explicit privacy measures.
- Their "protect the image" approach is an alternative to ours. We **delete the frame right after counting** and never show it, which is simpler and stronger for a status display.

---

## 9. Building occupancy estimation and detection – review (2018)

| | |
|---|---|
| Citation | Z. Chen, C. Jiang, L. Xie, "Building occupancy estimation and detection: A review," *Energy and Buildings*, vol. 169, pp. 260–270, 2018. DOI: 10.1016/j.enbuild.2018.03.084 |
| Link | https://pure.bit.edu.cn/en/publications/building-occupancy-estimation-and-detection-a-review |
| Read status | Abstract checked |

- **Coverage:** Reviews occupancy estimation (how many people) and detection (anyone there or not), grouped by sensor type. It also covers systems that **fuse several sensors** and compares the sensor types.
- **Why it matters:** A widely cited review (around 200+ citations), from Nanyang Technological University. The main motivation in this field is building energy use, since buildings use about 40% of global energy.
- **Limitations:** Focused on energy and HVAC, not on showing a person's availability. It was published before the newer lightweight detectors (YOLOv5/v8).

**Relevance to Smart Cabin:** The standard **background citation** for occupancy sensing and sensor fusion. It supports our design of combining several sources of evidence (camera, timetable, RFID, buttons) into one status. It also shows that our use of occupancy, telling people *who* is available, is a less common application, which helps define our research gap.

---

## 10. Real-time people counting with overhead camera on a low-power edge PC (2024)

| | |
|---|---|
| Citation | I. Ahamed, C. D. Ranathunga, D. S. Udayantha, B. K. K. Ng, C. Yuen, "Real-Time AI-Driven People Tracking and Counting Using Overhead Cameras," accepted at IEEE TENCON 2024. arXiv:2411.10072 |
| Link | https://arxiv.org/abs/2411.10072 |
| Read status | Abstract checked, HTML version skimmed |

- **Problem:** Count people entering and leaving a room accurately, even with several people at once.
- **Method:**
  - A Wi-Fi camera with infrared night mode above a doorway.
  - An **SSD MobileNet** detector (not YOLO), with one model for day and one for low light.
  - Their own tracking and line-crossing counting.
  - Runs on an **Intel NUC mini PC using only the CPU**, with no GPU.
- **Results:** About 97% accuracy in live tests, and 92% in a two-day lab test. Speed was 20–27 frames per second.
- **Limitations:** Speed drops as more people appear. The 97% and 92% figures are not reconciled, and the dataset size is not given.

**Relevance to Smart Cabin:**
- It shows **real-time counting is possible on a small CPU-only computer**, which is useful evidence for the deferred standalone device decision.
- It suggests trying a **light detector like MobileNet-SSD** alongside YOLOv8n in our detector comparison.
- Its entry/exit counting at the door is an alternative to our snapshot approach. It needs continuous video, though, which goes against our privacy rules, so it's a point to discuss in the report.

---

## Comparison table (papers 6–10)

| # | Paper | Sensing | Automatic? | Identifies the person? | Timetable aware? | Privacy approach | Runs on | Evaluation |
|---|---|---|---|---|---|---|---|---|
| 6 | SILA 2024 | None (manual) | No | Yes (self-report) | No | No data collected | ESP32 + web | Usability survey |
| 7 | Monti 2022 | Depth/RGB camera, snapshots | Yes | No (count only) | No | Only count + time leave the device | Raspberry Pi 4 | Accuracy, MAE, RMSE |
| 8 | Ahmad 2021 | Overhead camera | Yes | No | No | Encrypt the person regions | PC (MATLAB) | Security metrics |
| 9 | Chen 2018 | Review of many sensors | – | – | – | – | – | Review |
| 10 | Ahamed 2024 | Overhead IR camera, video | Yes | No | No | Not discussed | Intel NUC (CPU) | Accuracy, FPS |
| – | **Smart Cabin** | Camera snapshots + timetable (+ RFID, buttons later) | **Yes** | **Yes, enrolled staff only** | **Yes** | Frame deleted after counting, status only | Laptop now, edge device later | Headcount accuracy, false-green rate, delay |

## Research gap (draft for Review 1 slides)

- **Occupancy papers (7–10)** detect or count people to save energy or manage rooms. They count *how many* people, not *whether a specific faculty member is available*, and they don't use timetables.
- **Availability papers (6, and the IIUM and Benin works in README)** show a lecturer's status, but rely on manual updates or simple sensors (proximity, PIR) that can't tell the lecturer from a visitor.
- **No paper here combines** automatic camera-based presence of a *specific* person with **timetable context**, a **return-time estimate**, and a **privacy-first design** (snapshots only, frames deleted) for faculty availability. That combination is the gap Smart Cabin fills.

## Also worth a look (not summarised yet)

- A. Gharib, E. Abusamra, "A Microcontroller-Based Face Recognition Attendance System," *International Journal of Engineering Research* (Sirte University), 2024. Face recognition on an ESP32-CAM, relevant if face matching moves onto the board. https://journal.su.edu.ly/index.php/ijer/article/view/2702
- M. Aszkowski, M. Piechocki, "Thermo Presence," PP-RAI 2022. People detection with a low-resolution thermal camera on a Raspberry Pi 4, relevant to privacy and liveness. https://wydawnictwo.umg.edu.pl/pp-rai2022/pdfs/11_pp-rai-2022-094.pdf

## Still to do

- Summarise papers 1–5 from README section 9 in the same format.
- Read the full PDFs of papers 6 and 10 to fill in hardware details and survey numbers.
- Pick candidate IEEE/Springer conferences with deadlines before or around December 2026.
