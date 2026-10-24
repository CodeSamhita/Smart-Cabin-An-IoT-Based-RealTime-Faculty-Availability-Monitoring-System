# Smart Cabin - builds the animated presentation "Smart Cabin vs existing work".
# Run:  python make_presentation.py        (installs python-pptx the first time)
# Output: Smart_Cabin_vs_existing_work.pptx in this folder.
#
# One slide per paper: the paper's method on the left; on the right, each drawback appears on a click,
# then Smart Cabin's answer wipes in next to it. Every slide stands alone, so any slide can be copied
# into another deck (PowerPoint keeps its animations when a slide is copied).
# Paper details: the PDFs in Documents/Refrence Paper/ and research/papers.md ("abstract only" is marked).

import importlib
import os
import subprocess
import sys

for module, package in (("pptx", "python-pptx"), ("lxml", "lxml")):
    try:
        importlib.import_module(module)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)

from lxml import etree                                   # noqa: E402
from pptx import Presentation                            # noqa: E402
from pptx.dml.color import RGBColor                      # noqa: E402
from pptx.enum.shapes import MSO_SHAPE                   # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN          # noqa: E402
from pptx.oxml.ns import qn                              # noqa: E402
from pptx.util import Inches, Pt                         # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Smart_Cabin_vs_existing_work.pptx")

# Colours: the Smart Cabin navy dominates; the status colours carry meaning (red = drawback, green = answer)
NAVY = RGBColor(0x1F, 0x3B, 0x5A)
NAVY_LIGHT = RGBColor(0xE8, 0xEE, 0xF5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x22, 0x22, 0x22)
MUTED = RGBColor(0x5A, 0x5A, 0x5A)
RED = RGBColor(0xC6, 0x3A, 0x3A)
RED_LIGHT = RGBColor(0xFB, 0xEC, 0xEC)
GREEN = RGBColor(0x2E, 0x8B, 0x45)
GREEN_LIGHT = RGBColor(0xE9, 0xF6, 0xEC)
YELLOW = RGBColor(0xE0, 0xA8, 0x00)
HEAD, BODY = "Cambria", "Calibri"

PAPERS = [
    {"short": "Osemwengie (2026)", "tag": "Base work: PIR + buttons + door display",
     "cite": "G. O. Osemwengie, M.Eng thesis, University of Benin, 2026",
     "method": "PIR motion sensor detects a person in the office; 4 status buttons; ESP-NOW link to a door display.",
     "result": "Functional tests only.",
     "pairs": [("PIR can't tell who is there, and misses people sitting still",
                "Owner's face (YuNet + SFace) + phone keeps presence while seated; leave only after 180 s"),
               ("Messages unencrypted; ESP-NOW pairs by MAC address",
                "Device token from a one-time 6-digit code; only hashes stored; no pictures sent"),
               ("No reason or return time when away",
                "Timetable: \"In class CSE301, J block, Room 3, back around 11:40\"")]},
    {"short": "Za'bah & Mohamad (2021)", "tag": "Ultrasonic sensor + Raspberry Pi + Firebase",
     "cite": "N. F. Za'bah, A. Mohamad, J. Inf. Syst. Digit. Technol. 3(1), 2021",
     "method": "Ultrasonic distance sensor at the desk, Raspberry Pi, Firebase, mobile app.",
     "result": "65 - 80 % of readings correct; missed a seated lecturer about 1 reading in 5.",
     "pairs": [("Distance only: no identity, fooled by anyone at the desk",
                "Only the enrolled owner turns the status green (cosine similarity >= 0.36, 2 pictures)"),
               ("Status refreshed every 5 minutes",
                "Evidence every 3 s; about 30 s worst case to the public page"),
               ("No timetable context",
                "Several timetables per person, merged; where + back around")]},
    {"short": "Callemein et al. (2020)", "tag": "Low-resolution ceiling camera, on-device count",
     "cite": "T. Callemein, K. Van Beeck, T. Goedeme, arXiv:2007.04934, 2020",
     "method": "Omnidirectional low-resolution camera on the ceiling counts people on the device itself.",
     "result": "Room occupancy; privacy through low resolution.",
     "pairs": [("Counts people, but never knows if THE faculty member is there",
                "Headcount AND owner recognition: green alone, yellow with visitors"),
               ("Occupancy number, not an availability status",
                "Four clear statuses + manual buttons that end by themselves"),
               ("Privacy only by blurring the picture",
                "Pictures never leave the Pi; face data stays on the Pi; public page shows 12 fields")]},
    {"short": "Mannino et al. (2019)", "tag": "Ceiling camera counting line crossings",
     "cite": "A. Mannino et al., Int. J. Safety & Security Eng. 9(4), 2019",
     "method": "Raspberry Pi + ceiling camera; background model and virtual lines count people crossing into rooms (digital twin).",
     "result": "About 71 % detection; 80 % of crossings with more than 2 people counted wrong.",
     "pairs": [("Counts crossings: errors pile up when groups or fast walkers pass",
                "Counts who is in the cabin in each snapshot; steady after 3 pictures agree"),
               ("No identity: occupancy for facility management",
                "Owner recognition for availability, not for building energy"),
               ("People stopping under the sensor are counted in two rooms",
                "No line crossing: each snapshot counts each person once, wherever they stand")]},
    {"short": "SILA (2024)", "tag": "Lecturer updates their own status (ESP32 + web)",
     "cite": "N. Mohamad Nor, S. Zubir, M. S. Shahrudin, IJARBSS 14(10), 2024 (abstract)",
     "method": "ESP32 boards and a web page; the lecturer sets the status, students see it live.",
     "result": "Usability testing; no numbers in the abstract.",
     "pairs": [("Fully manual: wrong as soon as the lecturer forgets",
                "Automatic: camera + RFID + phone; buttons only correct it"),
               ("A forgotten manual status stays forever",
                "Buttons end by themselves (leave, visitors gone, time up)")]},
    {"short": "Soppari et al. (2025)", "tag": "Webcam + Haar cascade face recognition",
     "cite": "K. Soppari et al., IJSRA 14(1), 2025 (abstract)",
     "method": "Laptop webcam, OpenCV Haar cascade face detection and recognition, Flask web page.",
     "result": "Tested for accuracy and speed; no numbers in the abstract.",
     "pairs": [("Haar cascades struggle with angles and poor light",
                "YuNet detector + SFace 128-number embeddings"),
               ("Live video, privacy not discussed",
                "Snapshots every 5 s, picture discarded, owner-only face data on the Pi"),
               ("Presence only: no timetable, no return time",
                "Timetable merge: where they are and when they are back")]},
    {"short": "IJSRED (2026)", "tag": "RFID tags read around campus + mobile app",
     "cite": "IoT-Based Faculty Tracking Using RFID and Mobile App, IJSRED 9(2), 2026 (abstract)",
     "method": "Faculty carry RFID tags; ESP32 readers across campus; Spring Boot + MySQL; Flutter app.",
     "result": "Qualitative claims only.",
     "pairs": [("A tag proves the card was there, not the person",
                "A card login must be confirmed by face or phone within 120 s"),
               ("Last place a tag was read is not 'in the cabin and free'",
                "Status in the cabin: alone (green) or with visitors (yellow)")]},
    {"short": "Saxena et al. (2024)", "tag": "RFID tracking of students and professors",
     "cite": "S. Saxena, S. Saxena, P. Chauhan, KUEY 30(6S), 2024 (abstract)",
     "method": "RFID tags record where students and professors are; search by name.",
     "result": "\"Positive results\"; no numbers.",
     "pairs": [("Tracks everyone's location around campus",
                "No tracking: only one status per cabin; visitors are counted, never identified"),
               ("No measured accuracy",
                "80 / 80 automatic checks; measured Pi benchmarks; event log CSV for evaluation")]},
    {"short": "CNLAS (2026)", "tag": "Campus navigation + lecturer availability app",
     "cite": "F. O. Busola et al., Int. J. Computer Techniques 13(4), 2026 (abstract; weak references)",
     "method": "Flutter app, Node.js + PostgreSQL; maps and \"real-time\" availability.",
     "result": "Usability testing; no numbers; the data source is unclear.",
     "pairs": [("Where availability comes from is not explained",
                "Every status has a reason: sensors, timetable or 'set by them'"),
               ("No way to know if the data is old",
                "Grey 'Unknown' when the cabin device is silent for 60 s")]},
]

# Capability matrix: Y = yes, P = partly, N = no
CAPABILITIES = ["Automatic", "Knows the person", "Visitors / meeting", "Timetable reason", "Return time",
                "Privacy by design", "Measured"]
MATRIX = {
    "Osemwengie": "YNNPNNN", "Za'bah": "PNNNNNY", "Callemein": "YNPNNYY", "Mannino": "YNNNNPY",
    "SILA": "NYPNNYN", "Soppari": "YYNNNNN", "IJSRED": "YPNNNNN", "Saxena": "YPNNNNN", "CNLAS": "PPNNNNN",
    "Smart Cabin": "YYYYYYP",     # measured: tests + benchmarks done; real-hardware accuracy evaluation still to come
}


# ---------- Drawing helpers ----------
def box(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=""):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.08
    if name:
        s.name = name
    return s


def text(shape_or_slide, content, size=14, color=INK, bold=False, font=BODY, align=PP_ALIGN.LEFT,
         x=None, y=None, w=None, h=None, anchor=MSO_ANCHOR.TOP, name="", italic=False):
    # Writes into a shape, or adds a text box when x/y/w/h are given. content: str or list of str (paragraphs)
    if x is not None:
        shape = shape_or_slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        if name:
            shape.name = name
    else:
        shape = shape_or_slide
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = Inches(0.06)
    for i, line in enumerate([content] if isinstance(content, str) else content):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.name = font
        run.font.color.rgb = color
    return shape


def title(slide, words, dark=False):
    return text(slide, words, size=30, bold=True, font=HEAD, color=WHITE if dark else NAVY,
                x=0.6, y=0.35, w=12.1, h=0.8, name="Title")


def background(slide, colour):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = colour


def symbol(slide, x, y, char, colour, name):
    # The motif: a small coloured circle with a symbol (x = drawback, check = answer)
    c = box(slide, x, y, 0.42, 0.42, colour, shape=MSO_SHAPE.OVAL, name=name)
    text(c, char, size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    c.text_frame.margin_left = c.text_frame.margin_right = 0
    return c


# ---------- Animations (written into the slide XML) ----------
P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def add_animations(slide, clicks):
    # clicks: list of steps; each step is a list of (shape, effect) shown together on one click.
    # effect: "fade" or "wipe" (from the left). Also adds a fade transition between slides.
    ids = iter(range(3, 10_000))
    steps = []
    for step in clicks:
        effects = []
        for k, (shape, effect) in enumerate(step):
            spid = str(shape.shape_id)
            filt = "fade" if effect == "fade" else "wipe(left)"
            preset = "10" if effect == "fade" else "22"
            subtype = "0" if effect == "fade" else "8"
            node = "clickEffect" if k == 0 else "withEffect"
            a, b, c = next(ids), next(ids), next(ids)
            effects.append(
                f'<p:par><p:cTn id="{a}" presetID="{preset}" presetClass="entr" presetSubtype="{subtype}" fill="hold" '
                f'nodeType="{node}"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
                f'<p:set><p:cBhvr><p:cTn id="{b}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
                f'</p:cTn><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility'
                f'</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
                f'<p:animEffect transition="in" filter="{filt}"><p:cBhvr><p:cTn id="{c}" dur="500"/><p:tgtEl>'
                f'<p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect></p:childTnLst></p:cTn></p:par>')
        outer, inner = next(ids), next(ids)
        steps.append(f'<p:par><p:cTn id="{outer}" fill="hold"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>'
                     f'<p:childTnLst><p:par><p:cTn id="{inner}" fill="hold"><p:stCondLst><p:cond delay="0"/>'
                     f'</p:stCondLst><p:childTnLst>{"".join(effects)}</p:childTnLst></p:cTn></p:par></p:childTnLst>'
                     f'</p:cTn></p:par>')
    timing = (f'<p:timing xmlns:p="{P}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
              f'<p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq">'
              f'<p:childTnLst>{"".join(steps)}</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0">'
              f'<p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0">'
              f'<p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par>'
              f'</p:tnLst></p:timing>')
    root = slide._element
    root.append(etree.fromstring(f'<p:transition xmlns:p="{P}" spd="med"><p:fade/></p:transition>'))
    if steps:
        root.append(etree.fromstring(timing))


# ---------- Slides ----------
def title_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, NAVY)
    t = text(s, "Smart Cabin vs existing work", size=44, bold=True, font=HEAD, color=WHITE, x=0.8, y=2.2, w=11.7, h=1.0)
    sub = text(s, "How each drawback of nine published systems is answered", size=22, color=WHITE, x=0.8, y=3.25, w=11.7, h=0.7)
    dots = []
    for i, (colour, label) in enumerate(((GREEN, "Available"), (YELLOW, "In a meeting"), (RED, "Not available"))):
        d = box(s, 0.8 + i * 2.6, 4.6, 0.32, 0.32, colour, shape=MSO_SHAPE.OVAL, name="Status " + label)
        lab = text(s, label, size=16, color=WHITE, x=1.2 + i * 2.6, y=4.52, w=2.0, h=0.5, name="Label " + label)
        dots.append([(d, "fade"), (lab, "fade")])
    foot = text(s, "M.Tech Data Science · Presidency University, Bengaluru", size=14, color=WHITE,
                x=0.8, y=6.6, w=11.7, h=0.5)
    add_animations(s, [[(t, "fade"), (sub, "fade")], dots[0] + dots[1] + dots[2]])
    s.notes_slide.notes_text_frame.text = "Nine systems from the literature survey, one slide each, then a comparison and our measured results."


def overview_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    title(s, "Six gaps that keep coming back")
    gaps = [("Not automatic", "SILA and CNLAS depend on someone updating them"),
            ("Doesn't know who", "PIR, ultrasonic and room counters only see 'someone'"),
            ("Card is not the person", "RFID systems trust a tag that can be lent or forgotten"),
            ("No reason, no return time", "None of the nine uses the class timetable"),
            ("Privacy", "Live video or campus-wide tracking"),
            ("Not measured", "Most report no accuracy or delay numbers")]
    steps = []
    for i, (head, body) in enumerate(gaps):
        col, row = i % 3, i // 3
        x, y = 0.6 + col * 4.1, 1.8 + row * 2.4
        card = box(s, x, y, 3.85, 2.0, NAVY_LIGHT, name="Gap " + head)
        text(card, [head, body], size=16, color=INK, anchor=MSO_ANCHOR.MIDDLE)
        card.text_frame.paragraphs[0].runs[0].font.bold = True
        card.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
        card.text_frame.margin_left = Inches(0.25)
        card.text_frame.margin_right = Inches(0.7)                  # room for the mark on the right
        mark = symbol(s, x + 3.3, y + 0.15, "✕", RED, "Gap mark " + str(i))
        steps.append([(card, "fade"), (mark, "fade")])
    add_animations(s, steps)
    s.notes_slide.notes_text_frame.text = "Click to reveal each recurring gap. The next slides take the papers one by one."


def paper_slide(prs, paper, number):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    title(s, paper["short"] + ": " + paper["tag"])

    # Left: the paper
    card = box(s, 0.6, 1.45, 4.3, 5.4, NAVY_LIGHT, name="Paper card")
    text(card, ["THE PAPER", paper["cite"], "", "Method", paper["method"], "", "Result", paper["result"]], size=14)
    paras = card.text_frame.paragraphs
    paras[0].runs[0].font.size = Pt(12)
    paras[0].runs[0].font.bold = True
    paras[0].runs[0].font.color.rgb = MUTED
    paras[1].runs[0].font.italic = True
    paras[1].runs[0].font.size = Pt(12)
    for i in (3, 6):
        paras[i].runs[0].font.bold = True
        paras[i].runs[0].font.color.rgb = NAVY
    card.text_frame.margin_left = card.text_frame.margin_right = Inches(0.25)
    card.text_frame.margin_top = Inches(0.25)

    # Right: drawback -> answer rows
    head_d = text(s, "Drawback", size=14, bold=True, color=RED, x=5.3, y=1.4, w=3.4, h=0.4, name="Head drawback")
    head_a = text(s, "Smart Cabin's answer", size=14, bold=True, color=GREEN, x=9.15, y=1.4, w=3.6, h=0.4, name="Head answer")
    steps = []
    row_h = 1.55 if len(paper["pairs"]) == 3 else 2.2
    for i, (drawback, answer) in enumerate(paper["pairs"]):
        y = 1.9 + i * (row_h + 0.15)
        d_box = box(s, 5.3, y, 3.45, row_h, RED_LIGHT, name="Drawback " + str(i + 1))
        text(d_box, drawback, size=14, anchor=MSO_ANCHOR.MIDDLE)
        d_box.text_frame.margin_left = Inches(0.55)
        d_mark = symbol(s, 5.4, y + row_h / 2 - 0.21, "✕", RED, "Drawback mark " + str(i + 1))
        arrow = box(s, 8.8, y + row_h / 2 - 0.18, 0.3, 0.36, NAVY, shape=MSO_SHAPE.RIGHT_ARROW, name="Arrow " + str(i + 1))
        a_box = box(s, 9.15, y, 3.6, row_h, GREEN_LIGHT, name="Answer " + str(i + 1))
        text(a_box, answer, size=14, anchor=MSO_ANCHOR.MIDDLE)
        a_box.text_frame.margin_left = Inches(0.55)
        a_mark = symbol(s, 9.25, y + row_h / 2 - 0.21, "✓", GREEN, "Answer mark " + str(i + 1))
        steps.append([(d_box, "fade"), (d_mark, "fade")])
        steps.append([(arrow, "wipe"), (a_box, "wipe"), (a_mark, "fade")])
    add_animations(s, [[(head_d, "fade"), (head_a, "fade")]] + steps)
    s.notes_slide.notes_text_frame.text = ("Paper " + str(number) + ". Click: each drawback appears, then Smart Cabin's answer. "
                                           + ("Details from the abstract only; read the full paper before citing."
                                              if "abstract" in paper["cite"] else "Details from the full PDF."))


def matrix_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    title(s, "Side by side: Smart Cabin covers what the others miss")
    names = list(MATRIX)
    rows, cols = len(names) + 1, len(CAPABILITIES) + 1
    table = s.shapes.add_table(rows, cols, Inches(0.6), Inches(1.45), Inches(12.1), Inches(5.3)).table
    table.columns[0].width = Inches(2.2)
    for j in range(1, cols):
        table.columns[j].width = Inches((12.1 - 2.2) / (cols - 1))
    symbols = {"Y": ("✓", GREEN), "P": ("~", YELLOW), "N": ("✕", RED)}
    for j, cap in enumerate([""] + CAPABILITIES):
        cell = table.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.text = cap
        run = cell.text_frame.paragraphs[0].runs[0] if cap else None
        if run:
            run.font.size, run.font.bold, run.font.color.rgb, run.font.name = Pt(12), True, WHITE, BODY
        cell.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    for i, name in enumerate(names, start=1):
        last = name == "Smart Cabin"
        for j in range(cols):
            cell = table.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = GREEN_LIGHT if last else (WHITE if i % 2 else NAVY_LIGHT)
            value = name if j == 0 else symbols[MATRIX[name][j - 1]][0]
            cell.text = value
            run = cell.text_frame.paragraphs[0].runs[0]
            run.font.size, run.font.name = Pt(13 if j == 0 else 16), BODY
            run.font.bold = last or j > 0
            run.font.color.rgb = INK if j == 0 else symbols[MATRIX[name][j - 1]][1]
            cell.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    key = text(s, "✓ yes   ~ partly   ✕ no   (from our reading; papers marked 'abstract' in the notes still need the full text)",
               size=12, color=MUTED, x=0.6, y=6.85, w=12.1, h=0.4, name="Key")
    frame = [sh for sh in s.shapes if sh.has_table][0]
    add_animations(s, [[(frame, "fade"), (key, "fade")]])
    s.notes_slide.notes_text_frame.text = ("The last row is Smart Cabin. Partly = covered in a limited way. Smart Cabin's "
                                           "'Measured' is partly: tests and benchmarks are done, the real-hardware accuracy "
                                           "evaluation (false-green rate, delay) comes next.")


def results_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, NAVY)
    title(s, "Measured, not just built", dark=True)
    stats = [("80 / 80", "automatic server checks pass"),
             ("161 ms", "per picture on a Pi 4 (354 ms on a Zero 2W)"),
             ("~30 s", "worst case from arrival to the public page"),
             ("0", "pictures leave the cabin")]
    steps = []
    for i, (number, label) in enumerate(stats):
        x = 0.6 + i * 3.1
        tile = box(s, x, 2.0, 2.85, 3.0, WHITE, name="Stat " + number)
        text(tile, [number, label], size=16, color=INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        tile.text_frame.paragraphs[0].runs[0].font.size = Pt(44)
        tile.text_frame.paragraphs[0].runs[0].font.bold = True
        tile.text_frame.paragraphs[0].runs[0].font.color.rgb = NAVY
        tile.text_frame.paragraphs[0].runs[0].font.name = HEAD
        steps.append([(tile, "fade")])
    note = text(s, "Server tested with a fresh database; Pi app tested in simulation; board numbers from pi_benchmark.py. "
                   "Real-hardware evaluation (accuracy, false-green rate) comes next.",
                size=14, color=WHITE, x=0.6, y=5.5, w=12.1, h=1.0, name="Results note")
    steps.append([(note, "fade")])
    add_animations(s, steps)
    s.notes_slide.notes_text_frame.text = "Honest status: what is measured now, and what the real-hardware evaluation will add."


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    prs.core_properties.title = "Smart Cabin vs existing work"
    prs.core_properties.author = "Smart Cabin project"
    title_slide(prs)
    overview_slide(prs)
    for n, paper in enumerate(PAPERS, start=1):
        paper_slide(prs, paper, n)
    matrix_slide(prs)
    results_slide(prs)
    prs.save(OUT)
    print("saved", OUT, "-", len(prs.slides), "slides")


if __name__ == "__main__":
    main()
