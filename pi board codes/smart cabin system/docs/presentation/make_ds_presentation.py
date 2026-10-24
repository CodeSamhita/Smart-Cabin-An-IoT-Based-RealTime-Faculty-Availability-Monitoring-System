# Smart Cabin - builds the animated presentation "Data Science in Smart Cabin" (BUILD_PLAN.md step 10).
# Run:  python make_ds_presentation.py      Output: Smart_Cabin_data_science.pptx in this folder.
#
# Same look and slide helpers as make_presentation.py. No results exist yet: example visuals say
# "illustration - not real data", and numbers are either already measured or marked as targets.

import os

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from make_presentation import (GREEN, GREEN_LIGHT, INK, MUTED, NAVY, NAVY_LIGHT, RED, RED_LIGHT, WHITE, YELLOW, HEAD,
                               add_animations, background, box, symbol, text, title)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Smart_Cabin_data_science.pptx")
NOTE = "Illustration - not real data"


def new_slide(prs, dark=False):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, NAVY if dark else WHITE)
    return s


def card(slide, x, y, w, h, heading, body, fill=NAVY_LIGHT, name="", size=14):
    c = box(slide, x, y, w, h, fill, name=name or heading)
    text(c, [heading] + ([body] if isinstance(body, str) else body), size=size, color=INK)
    first = c.text_frame.paragraphs[0].runs[0]
    first.font.bold, first.font.size, first.font.color.rgb = True, Pt(size + 3), NAVY
    c.text_frame.margin_left = c.text_frame.margin_right = Inches(0.2)
    c.text_frame.margin_top = Inches(0.15)
    return c


def tag(slide, x, y, words, colour, name):
    t = box(slide, x, y, 0.95, 0.32, colour, name=name)
    text(t, words, size=11, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    t.text_frame.margin_left = t.text_frame.margin_right = 0
    return t


def arrow(slide, x, y, name, colour=NAVY):
    return box(slide, x, y, 0.35, 0.4, colour, shape=MSO_SHAPE.RIGHT_ARROW, name=name)


# ---------- Slides ----------
def s_title(prs):
    s = new_slide(prs, dark=True)
    t = text(s, "Data Science in Smart Cabin", size=44, bold=True, font=HEAD, color=WHITE, x=0.8, y=2.3, w=11.7, h=1.0)
    sub = text(s, "From sensor logs to predictions you can trust", size=22, color=WHITE, x=0.8, y=3.35, w=11.7, h=0.7)
    foot = text(s, "M.Tech Data Science · Presidency University, Bengaluru", size=14, color=WHITE, x=0.8, y=6.6, w=11.7, h=0.5)
    add_animations(s, [[(t, "fade"), (sub, "fade")]])
    s.notes_slide.notes_text_frame.text = "The IoT system is the data source; this deck is about what we learn from its data."


def s_data(prs):
    s = new_slide(prs)
    title(s, "The data the system already collects")
    sources = [("Camera", ["Headcount (steady)", "Owner's face seen", "Every 5 s, 1.5 s after a change"]),
               ("RFID card", ["Login / logout taps", "Unknown cards"]),
               ("Bluetooth phone", ["Owner's phone near / away", "l2ping every 15 s"]),
               ("Timetable + buttons", ["Class, lab, meeting, break", "Manual corrections = labels"])]
    steps = []
    for i, (head, body) in enumerate(sources):
        c = card(s, 0.6 + i * 3.1, 1.6, 2.85, 2.9, head, body)
        steps.append([(c, "fade")])
    note = card(s, 0.6, 4.85, 12.1, 1.6, "Every change is logged with its time",
                "events table (arrive, leave, card, headcount, phone, button, status) → CSV export. "
                "Nothing else is needed to start: the data collects itself while the system runs.",
                fill=GREEN_LIGHT, name="Logging note")
    steps.append([(note, "fade")])
    add_animations(s, steps)
    s.notes_slide.notes_text_frame.text = "Four evidence sources plus the timetable. Corrections by faculty are free labelled errors."


def s_pipeline(prs):
    s = new_slide(prs)
    title(s, "The pipeline: log → features → models → results")
    stages = [("Collect", ["Pi reports", "every 3 s"]), ("Store", ["SQLite", "events +", "evidence_log"]),
              ("Features", ["weekday, time,", "activity, room,", "own history"]),
              ("Models", ["regression,", "survival, HMM"]), ("Results", ["accuracy, MAE,", "false-green rate"])]
    steps = []
    for i, (head, body) in enumerate(stages):
        x = 0.6 + i * 2.5
        c = card(s, x, 2.4, 2.0, 1.75, head, body, fill=GREEN_LIGHT if head == "Results" else NAVY_LIGHT)
        group = [(c, "fade")]
        if i < len(stages) - 1:
            group.append((arrow(s, x + 2.05, 3.08, "Arrow " + str(i)), "wipe"))
        steps.append(group)
    foot = text(s, "Python: pandas, scikit-learn, lifelines (survival), hmmlearn / own Bayesian update, matplotlib",
                size=14, color=MUTED, x=0.6, y=4.6, w=12.1, h=0.5, name="Libraries")
    steps.append([(foot, "fade")])
    add_animations(s, steps)
    s.notes_slide.notes_text_frame.text = "evidence_log is the planned 30 s snapshot table; events only records changes."


def s_overview(prs):
    s = new_slide(prs)
    title(s, "Six data-science parts")
    parts = [("Return-time prediction", "When will they be back, with a range", True),
             ("Probabilistic status", "P(present) from noisy sensors, vs rules", True),
             ("Sensor ablation", "Which sensor adds how much accuracy", True),
             ("Best time to visit", "Weekly availability heatmap for students", False),
             ("Data-driven tuning", "Thresholds and buffers from ROC / trade-offs", False),
             ("Anomaly detection", "Outdated timetables, silent devices", False)]
    steps = []
    for i, (head, body, core) in enumerate(parts):
        col, row = i % 3, i // 3
        x, y = 0.6 + col * 4.1, 1.7 + row * 2.55
        c = card(s, x, y, 3.85, 2.25, head, body, fill=GREEN_LIGHT if core else NAVY_LIGHT)
        c.text_frame.margin_top = Inches(0.55)
        t = tag(s, x + 0.2, y + 0.15, "CORE" if core else "EXTRA", GREEN if core else MUTED, "Tag " + str(i))
        steps.append([(c, "fade"), (t, "fade")])
    add_animations(s, steps)
    s.notes_slide.notes_text_frame.text = "Core = the M.Tech contribution; extras if time allows."


def s_return_time(prs):
    s = new_slide(prs)
    title(s, "Core 1: when will they be back?")
    q = card(s, 0.6, 1.5, 3.8, 2.4, "The question", ["Away now. Back when?", "Today: only the end of the timetable entry (a guess)"])
    m = card(s, 4.65, 1.5, 4.0, 4.9, "Method", ["1. Baseline: end of the class / lab", "2. Regression: gradient boosting",
                                                "3. Survival analysis: Kaplan-Meier, Cox model (handles 'not back yet')",
                                                "Features: weekday, time, activity, room, person's past delays"])
    r = card(s, 8.9, 1.5, 3.85, 2.4, "Measured by", ["MAE in minutes", "How often the real return falls inside the range"],
             fill=GREEN_LIGHT)
    ex = box(s, 0.6, 4.2, 3.8, 2.2, WHITE, line=NAVY, name="Example")
    text(ex, ["Back around 11:40", "80 % chance before 11:55", NOTE], size=16, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    ex.text_frame.paragraphs[0].runs[0].font.bold = True
    ex.text_frame.paragraphs[0].runs[0].font.size = Pt(22)
    ex.text_frame.paragraphs[2].runs[0].font.size = Pt(11)
    ex.text_frame.paragraphs[2].runs[0].font.color.rgb = MUTED
    labels = card(s, 8.9, 4.2, 3.85, 2.2, "Free labels", "The camera sees every real return: each absence is a training example",
                  fill=NAVY_LIGHT)
    add_animations(s, [[(q, "fade")], [(m, "fade")], [(r, "fade"), (labels, "fade")], [(ex, "fade")]])
    s.notes_slide.notes_text_frame.text = "None of the nine papers predicts a return time; this is new. The example is an illustration."


def s_probabilistic(prs):
    s = new_slide(prs)
    title(s, "Core 2: a probabilistic status engine")
    # Hidden states
    in_cabin = box(s, 1.0, 2.0, 2.2, 1.2, GREEN, shape=MSO_SHAPE.OVAL, name="State in")
    text(in_cabin, "In cabin", size=18, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    away = box(s, 4.6, 2.0, 2.2, 1.2, RED, shape=MSO_SHAPE.OVAL, name="State away")
    text(away, "Away", size=18, color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    link = box(s, 3.35, 2.4, 1.1, 0.4, NAVY, shape=MSO_SHAPE.LEFT_RIGHT_ARROW, name="Transitions")
    hidden = text(s, "Hidden states (what is really true)", size=13, color=MUTED, x=1.0, y=1.5, w=5.8, h=0.4, name="Hidden label")
    obs = []
    for i, (name, note) in enumerate((("Camera", "misses a turned face"), ("Phone", "reaches through walls"),
                                      ("Card", "may be lent"))):
        o = card(s, 0.7 + i * 2.15, 4.1, 2.0, 1.6, name, note, size=13)
        obs.append((o, "fade"))
    obs_label = text(s, "Noisy observations", size=13, color=MUTED, x=0.7, y=5.8, w=6.3, h=0.4, name="Obs label")
    out = card(s, 7.5, 1.6, 5.25, 2.3, "Output", ["P(present) = 0.93", "Green only above a threshold chosen to keep false-green low"],
               fill=GREEN_LIGHT)
    cmp = card(s, 7.5, 4.1, 5.25, 2.3, "Compared with today's rules",
               ["Accuracy, false-green rate (costliest error), update delay", "Same logged data, two engines"])
    add_animations(s, [[(hidden, "fade"), (in_cabin, "fade"), (away, "fade"), (link, "wipe")],
                       obs + [(obs_label, "fade")], [(out, "fade")], [(cmp, "fade")]])
    s.notes_slide.notes_text_frame.text = "Hidden Markov Model / Bayesian update: sensors are evidence with known error rates, learned from the log."


def s_ablation(prs):
    s = new_slide(prs)
    title(s, "Core 3: which sensor adds how much?")
    configs = ["Camera only", "+ Phone", "+ RFID", "All + timetable"]
    steps = []
    for i, name in enumerate(configs):
        h = 1.2 + i * 0.9
        bar = box(s, 0.9 + i * 2.2, 6.3 - h, 1.6, h, NAVY if i < 3 else GREEN, shape=MSO_SHAPE.RECTANGLE, name="Bar " + str(i))
        lab = text(s, name, size=14, color=INK, align=PP_ALIGN.CENTER, x=0.6 + i * 2.2, y=6.35, w=2.2, h=0.5, name="Label " + str(i))
        q = text(s, "?", size=28, bold=True, color=WHITE, align=PP_ALIGN.CENTER, x=0.9 + i * 2.2, y=6.3 - h + 0.1, w=1.6, h=0.6,
                 name="Unknown " + str(i))
        steps.append([(bar, "wipe"), (lab, "fade"), (q, "fade")])
    why = card(s, 9.6, 1.6, 3.15, 4.7, "Why it matters", ["Shows the value of each sensor with numbers",
                                                          "Tells a cheaper build what it can drop",
                                                          "Accuracy and false-green rate per configuration"],
               fill=GREEN_LIGHT)
    note = text(s, NOTE + ": bar heights only show the idea; real values come from the trial", size=11, color=MUTED,
                x=0.6, y=0.95, w=8.8, h=0.4, name="Note")
    add_animations(s, [[(note, "fade")]] + steps + [[(why, "fade")]])
    s.notes_slide.notes_text_frame.text = "Re-run the same log with sensors switched off in software; compare against ground truth."


def s_extras(prs):
    s = new_slide(prs)
    title(s, "Extras: heatmap, tuning, anomalies")
    heat = card(s, 0.6, 1.5, 4.6, 5.0, "Best time to visit", [""], size=14)
    import random
    from pptx.dml.color import RGBColor
    random.seed(4)
    shades = [WHITE, RGBColor(0x9E, 0xD1, 0xA8), GREEN]       # one hue, light -> dark = less -> more often free
    cells = []
    for d in range(6):
        for h in range(7):
            c = box(s, 0.95 + h * 0.56, 2.3 + d * 0.5, 0.52, 0.45, random.choice(shades), shape=MSO_SHAPE.RECTANGLE,
                    name="Cell %d-%d" % (d, h))
            cells.append((c, "fade"))
    hn = text(s, ["Mon-Sat × hours, darker = more often free", NOTE], size=11, color=MUTED, x=0.8, y=5.4, w=4.2, h=0.8, name="Heat note")
    tune = card(s, 5.45, 1.5, 7.3, 2.35, "Data-driven tuning", ["Face threshold from an ROC curve (equal error rate)",
                                                                "Stillness threshold from real sitting-still data",
                                                                "Buffers: flicker vs delay trade-off"])
    anom = card(s, 5.45, 4.15, 7.3, 2.35, "Anomaly detection", ["'Class' in the timetable but in the cabin every week → outdated timetable",
                                                                "Devices that go silent",
                                                                "z-scores, isolation forest"])
    add_animations(s, [[(heat, "fade")] + cells + [(hn, "fade")], [(tune, "fade")], [(anom, "fade")]])
    s.notes_slide.notes_text_frame.text = "The heatmap colours are random: illustration only."


def s_data_plan(prs):
    s = new_slide(prs)
    title(s, "The data plan")
    items = [("Snapshot logging", "New table evidence_log: one row per cabin every 30 s (in / out, headcount, phone, face score, activity)"),
             ("Ground truth", "Short manual trial log + faculty corrections as weak labels + camera-seen returns as free labels"),
             ("Synthetic data first", "Simulated faculty days from the real timetables, to build and test models before real data"),
             ("Volume", "2-3 weeks in a few cabins is enough for the core parts")]
    steps = []
    for i, (head, body) in enumerate(items):
        y = 1.55 + i * 1.3
        mark = symbol(s, 0.7, y + 0.3, str(i + 1), NAVY, "Num " + str(i))
        c = card(s, 1.3, y, 11.45, 1.1, head, body, size=14)
        c.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        c.text_frame.margin_top = Inches(0.05)
        steps.append([(mark, "fade"), (c, "fade")])
    add_animations(s, steps)
    s.notes_slide.notes_text_frame.text = "Privacy: the log holds statuses and counts only, never pictures."


def s_metrics(prs):
    s = new_slide(prs)
    title(s, "How results will be measured")
    rows = [("Status accuracy", "system status vs ground truth", "≥ 90 % (target)"),
            ("False-green rate", "shown available when not", "< 5 % (target)"),
            ("Return-time error", "MAE, minutes", "≤ 10 min (target)"),
            ("Prediction range", "real return inside the range", "≈ 80 % (target)"),
            ("Update delay", "arrival → public page", "≤ 30 s (by design, to measure)"),
            ("Face match", "true / false match rates", "from the ROC curve")]
    table = s.shapes.add_table(len(rows) + 1, 3, Inches(0.6), Inches(1.5), Inches(12.1), Inches(4.6)).table
    for j, w in enumerate((3.6, 4.6, 3.9)):
        table.columns[j].width = Inches(w)
    for j, head in enumerate(("Metric", "What it means", "Target")):
        cell = table.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.text = head
        r = cell.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb = Pt(14), True, WHITE
    for i, row in enumerate(rows, start=1):
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if i % 2 else NAVY_LIGHT
            cell.text = value
            r = cell.text_frame.paragraphs[0].runs[0]
            r.font.size, r.font.color.rgb = Pt(14), INK
            r.font.bold = j == 0
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame = [sh for sh in s.shapes if sh.has_table][0]
    note = text(s, "Targets are goals, not results. Already measured: 161 ms per picture (Pi 4), 354 ms (Pi Zero 2W).",
                size=12, color=MUTED, x=0.6, y=6.3, w=12.1, h=0.4, name="Targets note")
    add_animations(s, [[(frame, "fade")], [(note, "fade")]])
    s.notes_slide.notes_text_frame.text = "False-green is the costliest error: a student walks over for nothing."


def s_timeline(prs):
    s = new_slide(prs, dark=True)
    title(s, "Timeline", dark=True)
    phases = [("Now → Review 1", "3-6 Nov", ["Snapshot logging", "Synthetic data generator", "Baselines"]),
              ("November", "data collection", ["2-3 weeks of real logs", "Return-time models", "HMM engine"]),
              ("Review 2", "8-11 Dec", ["Ablation + metrics", "Charts in the report", "Research paper"])]
    steps = []
    for i, (head, when, body) in enumerate(phases):
        x = 0.6 + i * 4.1
        c = box(s, x, 2.0, 3.85, 3.2, WHITE, name="Phase " + str(i))
        text(c, [head, when, ""] + body, size=15, color=INK)
        p = c.text_frame.paragraphs
        p[0].runs[0].font.bold, p[0].runs[0].font.size, p[0].runs[0].font.color.rgb = True, Pt(22), NAVY
        p[1].runs[0].font.color.rgb = MUTED
        c.text_frame.margin_left = c.text_frame.margin_right = Inches(0.25)
        c.text_frame.margin_top = Inches(0.25)
        group = [(c, "fade")]
        if i < 2:
            group.append((arrow(s, x + 3.88, 3.4, "Next " + str(i), colour=WHITE), "wipe"))   # white on the dark slide
        steps.append(group)
    add_animations(s, steps)
    s.notes_slide.notes_text_frame.text = "Iterations 0-6 of the system are done; the data-science work fills November."


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    prs.core_properties.title = "Data Science in Smart Cabin"
    prs.core_properties.author = "Smart Cabin project"
    for make in (s_title, s_data, s_pipeline, s_overview, s_return_time, s_probabilistic, s_ablation, s_extras,
                 s_data_plan, s_metrics, s_timeline):
        make(prs)
    prs.save(OUT)
    print("saved", OUT, "-", len(prs.slides), "slides")


if __name__ == "__main__":
    main()
