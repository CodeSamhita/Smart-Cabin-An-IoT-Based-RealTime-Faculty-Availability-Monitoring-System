# Smart Cabin – Research papers

Plain-language summaries of papers on **faculty / lecturer availability**, with how each one relates to Smart Cabin.
Numbers continue from the reference list in `README.md` section 9 (papers 1–5 are listed there and still need summaries).

Scope (agreed 21 Oct 2026): faculty availability systems, cabin/door status displays, faculty presence by face recognition, and timetable-based availability. **2020 or newer only.**

**Read status keys:** *Abstract checked* = details confirmed from the journal page. *Full text read* = whole paper read.
Always read the full paper yourself before citing it in the report.

> **Note on venues:** papers on faculty availability mostly appear in smaller open-access journals, not IEEE/Springer. That's fine for the literature survey, but check each journal's standing before citing it in the final research paper. It also suggests the topic is **under-studied in major venues**, which is good for your contribution.

---

## 6. SILA – real-time lecturer availability with ESP32 (2024)

| | |
|---|---|
| Citation | N. Mohamad Nor, S. Zubir, M. S. Shahrudin, "Leveraging IoT to Enhance Real-Time Lecturer Accessibility in Higher Education," *International Journal of Academic Research in Business and Social Sciences*, vol. 14, no. 10, pp. 2990–2999, 2024. DOI: 10.6007/IJARBSS/v14-i10/22959 |
| Link | https://hrmars.com/ijarbss/article/view/22959/Leveraging-IoT-to-Enhance-Real-Time-Lecturer-Accessibility-in-Higher-Education |
| Topic area | Faculty availability system |
| Read status | Abstract checked (full PDF still to read for hardware details and survey numbers) |

- **Problem:** Students waste time looking for lecturers who are not in their rooms.
- **Method:** SILA ("Synced Information on Lecturer Availability") uses ESP32 boards and a web page. **Lecturers update their own status**, and students see it in real time.
- **Evaluation:** User testing for usefulness, satisfaction and usability. The abstract gives no numbers.
- **Limitations:** Fully manual. If the lecturer forgets to update it, the status is wrong. There is no sensing and no timetable.

**Relevance to Smart Cabin:** The **closest match to our problem**. SILA is the manual approach; our staff override and future hardware buttons do the same job. Smart Cabin adds **automatic detection by camera** and **timetable context**, so the status stays right even when nobody updates it. Its usability evaluation is a good template for our user survey.

---

## 7. Faculty presence detection and alert system – face recognition (2025)

| | |
|---|---|
| Citation | K. Soppari, Varun D, R. Eedula, A. Manchala, "Faculty presence detection and alert system," *International Journal of Science and Research Archive*, vol. 14, no. 1, pp. 1244–1251, 2025. DOI: 10.30574/ijsra.2025.14.1.0203 |
| Link | https://ijsra.net/content/faculty-presence-detection-and-alert-system |
| Topic area | Faculty presence via face recognition |
| Read status | Abstract checked |

- **Problem:** Check whether a faculty member is present, cheaply and automatically.
- **Method:**
  - Uses the computer's **built-in webcam**, with no Raspberry Pi or external camera.
  - **OpenCV with a Haar Cascade** for real-time face detection and recognition.
  - A **Flask web interface** shows the result, with live detection and alerts.
- **Evaluation:** Tested under different conditions for accuracy, speed and scalability. The abstract gives no numbers.
- **Limitations:**
  - Haar Cascade is an old method that struggles with side angles and poor lighting.
  - It records video, with no privacy measures mentioned.
  - Presence only, with no timetable or return time.

**Relevance to Smart Cabin:**
- **Very close to our current setup**: laptop webcam, Python, OpenCV and a web page.
- It supports our laptop-first choice.
- Our planned face matching (InsightFace/ArcFace embeddings) is a clear **technical improvement** over Haar Cascade. Comparing the two would make a good experiment for the report.
- Our design also differs on privacy: **snapshots only, and the frame is deleted after checking**.

---

## 8. IoT-based faculty tracking with RFID and a mobile app (2026)

| | |
|---|---|
| Citation | "Design and Implementation of an IoT-Based Faculty Tracking System Using RFID and Mobile Application," *International Journal of Scientific Research and Engineering Development (IJSRED)*, vol. 9, no. 2, pp. 2544–2559, 2026. Paper ID IJSRED-V9I2P376 |
| Link | https://www.ijsred.com/volume9/issue2/paper-details/IJSRED-V9I2P376.html |
| Topic area | Faculty availability system (RFID) |
| Read status | Abstract checked. **The author list differs between the page and its "How to cite" box, so confirm the authors from the PDF before citing.** |

- **Problem:** Students can't find faculty because of changing schedules, meetings and empty cabins. The authors say fixed timetables and asking around are slow and unreliable.
- **Method:**
  - Each faculty member carries an **RFID tag**, and **readers are placed around campus**.
  - An **ESP32** sends each scan to a Spring Boot server with a MySQL database.
  - Students see the faculty member's last location and availability in a **Flutter mobile app**.
- **Evaluation:** Only qualitative claims (saves time, user friendly). No accuracy, delay or user numbers.
- **Limitations:**
  - It shows only *where the tag was last read*, which isn't the same as being in the cabin and free.
  - A forgotten or shared tag gives wrong results.
  - There's no measured evaluation.
  - Future work lists GPS, notifications and AI scheduling.

**Relevance to Smart Cabin:**
- It confirms the **same real problem** in an Indian college setting.
- It shows the main **weakness of RFID-only systems**: a tag proves the card was there, not the person, and not whether they're busy with visitors.
- This is why our design treats **RFID as supporting evidence only**, with the camera as the main check.
- Its point that fixed timetables alone don't work supports our approach of **timetable plus sensing**.

---

## 9. RFID-based real-time tracking of students and professors (2024)

| | |
|---|---|
| Citation | S. Saxena, S. Saxena, P. Chauhan, "RFID-Based Tracking System For Real-Time Monitoring Of Students And Professors," *Educational Administration: Theory and Practice (KUEY)*, vol. 30, no. 6(S), 2024. DOI: 10.53555/kuey.v30i6(S).5370 |
| Link | https://kuey.net/index.php/kuey/article/view/5370 |
| Topic area | Faculty availability system (RFID, campus) |
| Read status | Abstract checked (from the journal listing and search results; full text not yet read) |

- **Problem:** Students and professors find it hard to locate each other on campus.
- **Method:** RFID tags record where people are in real time, and the data goes to a central store. A **search by name** lets students find professors and the other way round.
- **Evaluation:** "Positive results" from initial trials, with no numbers in the abstract.
- **Limitations:** Tracks students as well as staff, which is a bigger privacy question. No accuracy figures, and the same tag-not-person problem as paper 8.

**Relevance to Smart Cabin:**
- Another **RFID-based locator** from an Indian university (Silver Oak University, Ahmedabad).
- Its **name search** is the same idea as our keyword search across 839 faculty.
- It tracks *location* continuously. Smart Cabin only shows a *status* (available / with visitors / away / unknown) and tracks no one around campus, which is a **stronger privacy position** to highlight in the report.

---

## 10. Campus navigation and lecturer availability app – CNLAS (2026)

| | |
|---|---|
| Citation | F. O. Busola, O. Mayowa, O. O. Adebakin, O. Fabiyi, O. J. Adelowo, U. Alfred, "A Mobile Application for Campus Navigation and Lecturer Availability System (CNLAS)," *International Journal of Computer Techniques*, vol. 13, no. 4, pp. 287–291, 2026 |
| Link | https://ijctjournal.org/mobile-application-campus-navigation-lecturer-availability-system-cnlas/ |
| Topic area | Faculty availability system (app) |
| Read status | Abstract checked. **Weak source:** some of its references look like placeholders (an example.org link and a dummy Zenodo DOI). Use it only as an example of current app-based work, not as strong evidence. |

- **Problem:** Large campuses make it hard to find buildings and to know whether a lecturer is available.
- **Method:** A Flutter mobile app with a Node.js/Express backend and PostgreSQL, combining **campus maps** and **"real-time lecturer availability"**. The abstract doesn't say where availability data comes from (manual, timetable or sensor).
- **Evaluation:** Functionality, speed and usability testing. Users reported spending less time finding lecturers. No numbers or sample size.
- **Limitations:** Unclear availability source, no measured results, and doubtful references.

**Relevance to Smart Cabin:** It shows the problem is **still being worked on in 2026**, but with apps that rely on unclear or manual data. It supports our argument that availability needs **automatic, explainable evidence**. Our "How we know" panel shows exactly why each status was given.

---

## Comparison table (papers 6–10 and Smart Cabin)

| # | Paper | How presence is known | Automatic? | Knows it's the right person? | Uses timetable? | Shows busy / visitors? | Return time? | Privacy | Measured results? |
|---|---|---|---|---|---|---|---|---|---|
| 6 | SILA 2024 | Lecturer updates it | No | Yes (self-report) | No | Only if lecturer sets it | No | No data collected | Usability survey |
| 7 | Soppari 2025 | Webcam + Haar face recognition | Yes | Yes (face) | No | No | No | Not discussed (video) | Not in abstract |
| 8 | IJSRED 2026 | RFID tag read at campus points | Yes | Tag only | No | No | No | Location tracking | No |
| 9 | Saxena 2024 | RFID tags | Yes | Tag only | No | No | No | Tracks staff and students | No numbers |
| 10 | CNLAS 2026 | Not stated | Unclear | Unclear | Unclear | No | No | Not discussed | No numbers |
| – | **Smart Cabin** | **Camera snapshots + timetable (+ RFID, buttons later)** | **Yes** | **Yes (face match, enrolled staff only)** | **Yes** | **Yes (headcount)** | **Yes (planned)** | **Snapshots only, frame deleted, status shown, no footage** | **Planned: accuracy, false-green rate, delay** |

## Research gap (draft for Review 1 slides)

1. **Manual systems (SILA, CNLAS)** go wrong as soon as the lecturer forgets to update them.
2. **RFID systems (papers 8, 9)** prove a card was read, not that the person is in the cabin and free. They also track people around campus.
3. **Face recognition systems (paper 7)** detect the person, but use old methods (Haar Cascade), record video, and ignore the timetable.
4. **None of the 2020+ papers found uses the class timetable** to explain *why* someone is away or *when* they'll be back, even though paper 8 names schedules as the root problem.
5. **None reports measured accuracy** (false "available" rate, delay).

**Smart Cabin's contribution:** an automatic, privacy-first faculty availability system that combines **camera-based presence of the specific faculty member** (modern face embeddings plus a headcount for "with visitors"), **timetable context** (reason and expected return), and optional RFID and buttons. It is evaluated with **measured accuracy, false-green rate and update delay**.

## Also found (not included)

- *Availability and Attendance Monitoring System for Faculty using IoT* (IJRDST, around 2023). RFID + NodeMCU, aimed at faculty missing from the staff room. **Could not be opened** (unreadable PDF), so authors and year are not confirmed. Worth getting from the library. https://ijrdst.org/public/uploads/paper/239431684907211.pdf
- *In-Classroom Faculty Attendance Monitoring System based on UHF RFID with Captured Image Cross-verification* (Indian Journal of Science and Technology). RFID plus a photo to confirm the right person. The site blocked access, so the year is not confirmed. https://indjst.org/articles/in-classroom-faculty-attendance-monitoring-system-based-on-ultra-high-frequency-uhf-radio-frequency-identification-rfid-with-captured-image-cross-verification-mechanism
- No 2020+ paper was found that uses **timetables** for faculty availability. This is a gap in itself.

## Still to do

- Summarise papers 1–5 from README section 9 in the same format.
- Get the full PDFs of papers 6–10 and fill in hardware details and numbers.
- Try Google Scholar / IEEE Xplore through the university library for "faculty availability" and "lecturer availability". Those databases aren't reachable from here.
