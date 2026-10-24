// Smart Cabin - the timetable editor (BUILD_PLAN.md section 2b).
// slots: the day's times, e.g. [{kind: "hour", label: "Hour 1", start: "09:00", end: "09:50"}, {kind: "tea", ...}]
// cells: what each hour is, keyed "day-slot", e.g. "0-3" = Monday, 4th slot. Missing = Free.

let options = null;      // drop-down choices from the server
let sheets = [];         // all of this person's timetables
let sheetIndex = 0;      // the one being edited
let busy = [];           // busy hours from all timetables (as last saved), to grey out the other timetables' hours
let slots = [];
let cells = {};
let editing = null;      // the "day-slot" key being edited
let phoneDay = 0;        // the day shown on a phone
let changed = false;     // unsaved changes

const toMin = t => { const [h, m] = t.split(":"); return Number(h) * 60 + Number(m); };
const toHHMM = m => String(Math.floor(m / 60) % 24).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
const days = () => options.days.slice(0, $("saturday").checked ? 6 : 5);
// Numbered hours: the teaching hours and the lunch hour (lunch is an hour too: 8 hours a day). Tea is not.
const hourIndexes = () => slots.map((s, i) => s.kind !== "tea" ? i : -1).filter(i => i >= 0);
const cssName = activity => activity.split(" ")[0];

// ---------- Step 1: the day's times ----------
function workOutTimes() {
  // Keep what was filled in: remember cells by hour number (Hour 1, 2 ...), not by position
  const byHour = {};
  hourIndexes().forEach((slotIndex, n) => {
    for (let d = 0; d < 6; d++) if (cells[d + "-" + slotIndex]) byHour[d + "-h" + n] = cells[d + "-" + slotIndex];
  });

  const lengths = { hour: Number($("len-hour").value), tea: Number($("len-tea").value), lunch: Number($("len-lunch").value) };
  const order = options.templates[$("template").value].map(s => s.kind);
  let minute = toMin($("day-start").value || "09:00"), n = 0;
  slots = order.map(kind => {
    if (kind !== "tea") n++;
    const label = kind === "tea" ? "Tea break" : "Hour " + n + (kind === "lunch" ? " (lunch)" : "");
    const s = { kind: kind, label: label, start: toHHMM(minute), end: toHHMM(minute + lengths[kind]) };
    minute += lengths[kind];
    return s;
  });

  cells = {};
  hourIndexes().forEach((slotIndex, n) => {
    for (let d = 0; d < 6; d++) if (byHour[d + "-h" + n]) cells[d + "-" + slotIndex] = byHour[d + "-h" + n];
  });
  showSlots();
  showGrid();
}

function showSlots() {
  $("slots").innerHTML = slots.map((s, i) =>
    "<tr><td>" + esc(s.label) + "</td>" +
    "<td><input type='time' value='" + s.start + "' onchange='slots[" + i + "].start = this.value; changed = true; showGrid()'></td>" +
    "<td><input type='time' value='" + s.end + "' onchange='slots[" + i + "].end = this.value; changed = true; showGrid()'></td></tr>").join("");
}

// ---------- Step 2: the grid ----------
function busyElsewhere(key) {
  // Something from another timetable at this hour's time? e.g. "Class BCA201 (School of CS - BCA)"
  const [day, slot] = key.split("-").map(Number);
  const s = slots[slot], name = sheets[sheetIndex].name;
  const hit = busy.find(b => b.sheet !== name && b.day === day && toMin(b.start) < toMin(s.end) && toMin(s.start) < toMin(b.end));
  return hit ? hit.text + " (" + hit.sheet + ")" : "";
}

function isLunch(key) { return slots[Number(key.split("-")[1])].kind === "lunch"; }

function cellHtml(key) {
  const c = cells[key];
  const other = busyElsewhere(key);
  const empty = isLunch(key) ? "Lunch" : "Free";
  if (!c) return other ? "<span class='where'>" + empty + " &middot; busy: " + esc(other) + "</span>" : "<span>" + empty + "</span>";
  if (c.continues) return "<span class='what'>Lab</span><div class='where'>(2nd hour)</div>";
  return "<span class='what'>" + esc(c.activity + (c.title ? " " + c.title : "")) + "</span>" +
         "<div class='where'>" + esc(placeText(c)) + "</div>";
}

function placeText(c) {
  if (!c.building) return "";
  const floor = options.floors.find(f => f.value === Number(c.floor));
  return c.building + " block, " + (floor ? floor.label : "") + (c.number ? ", " + (c.activity === "Lab" ? "Lab " : "Room ") + c.number : "");
}

function cellClass(key) {
  const c = cells[key];
  return "cell " + (c ? cssName(c.activity) : "free");
}

function showGrid() {
  const ds = days();
  // Laptop: hours down, days across
  let html = "<tr><th></th>" + ds.map(d => "<th>" + d.slice(0, 3) + "</th>").join("") + "</tr>";
  slots.forEach((s, i) => {
    html += "<tr><td class='slot-time'>" + esc(s.label) + "<br>" + s.start + "-" + s.end + "</td>";
    if (s.kind === "tea") {
      html += "<td class='break' colspan='" + ds.length + "'>" + esc(s.label) + "</td>";
    } else {
      ds.forEach((d, day) => {
        const key = day + "-" + i;
        html += "<td class='" + cellClass(key) + "' onclick='openEditor(\"" + key + "\")'>" + cellHtml(key) + "</td>";
      });
    }
    html += "</tr>";
  });
  $("grid").innerHTML = html;

  // Phone: one day at a time
  phoneDay = Math.min(phoneDay, ds.length - 1);
  $("day-chips").innerHTML = ds.map((d, day) =>
    "<button class='chip" + (day === phoneDay ? " active" : "") + "' onclick='phoneDay = " + day + "; showGrid()'>" + d.slice(0, 3) + "</button>").join("");
  $("day-list").innerHTML = slots.map((s, i) => {
    const key = phoneDay + "-" + i;
    if (s.kind === "tea") return "<div class='day-row break'><span class='time'>" + s.start + "</span>" + esc(s.label) + "</div>";
    return "<div class='day-row " + cellClass(key) + "' onclick='openEditor(\"" + key + "\")'><span class='time'>" +
           esc(s.label) + "<br>" + s.start + "-" + s.end + "</span><div>" + cellHtml(key) + "</div></div>";
  }).join("");
}

// ---------- The box for one hour ----------
function nextHourKey(key) {
  const [day, slot] = key.split("-").map(Number);
  const later = hourIndexes().filter(i => i > slot);
  return later.length ? day + "-" + later[0] : null;
}

function previousHourKey(key) {
  const [day, slot] = key.split("-").map(Number);
  const earlier = hourIndexes().filter(i => i < slot);
  return earlier.length ? day + "-" + earlier[earlier.length - 1] : null;
}

function openEditor(key) {
  // The 2nd hour of a lab is edited through its first hour
  if (cells[key] && cells[key].continues) key = previousHourKey(key);
  editing = key;
  const [day, slot] = key.split("-").map(Number);
  const c = cells[key] || { activity: "", title: "", building: "", floor: 0, number: 0 };
  $("ed-title").textContent = options.days[day] + ", " + slots[slot].label + " (" + slots[slot].start + " - " + slots[slot].end + ")";
  $("ed-activity").options[0].text = isLunch(key) ? "Lunch break" : "Free (in my cabin)";
  $("ed-activity").value = c.activity;
  $("ed-name").value = c.title || "";
  $("ed-building").value = c.building || "";
  $("ed-floor").value = String(c.floor || 0);
  $("ed-number").value = String(c.number || 0);
  editorChanged();
  $("editor").classList.remove("hidden");
}

function editorChanged() {
  const activity = $("ed-activity").value;
  $("ed-details").classList.toggle("hidden", !activity || activity === "Office hours");
  $("ed-lab-note").classList.toggle("hidden", activity !== "Lab");
  $("ed-number").options[0].text = activity === "Lab" ? "Lab no." : "Room no.";
}

function saveEditor() {
  const activity = $("ed-activity").value;
  const next = nextHourKey(editing);
  // Clear the old 2nd lab hour, if this was a lab
  if (cells[editing] && cells[editing].activity === "Lab" && next && cells[next] && cells[next].continues) delete cells[next];
  if (!activity) {
    delete cells[editing];
  } else {
    cells[editing] = { activity: activity, title: $("ed-name").value.trim(), building: $("ed-building").value,
                       floor: Number($("ed-floor").value), number: Number($("ed-number").value), continues: false };
    if (activity === "Lab" && next) {
      if (cells[next] && !cells[next].continues && !confirm("The next hour already has " + cells[next].activity + ". Replace it with the lab?")) {
        return;
      }
      cells[next] = { activity: "Lab", continues: true, title: "", building: "", floor: 0, number: 0 };
    }
  }
  $("editor").classList.add("hidden");
  changed = true;
  showGrid();
}

// ---------- Step 3: save ----------
async function save() {
  $("save-msg").className = "small";
  const used = {};
  const workingDays = days().length;
  Object.keys(cells).forEach(k => { if (Number(k.split("-")[0]) < workingDays) used[k] = cells[k]; });
  const sheet = sheets[sheetIndex];
  try {
    const r = await api("PUT", "/api/timetable/" + PERSON_ID + "/sheets/" + sheet.id,
                        { name: sheet.name, template: $("template").value, saturday: $("saturday").checked, slots: slots, cells: used });
    changed = false;
    $("save-msg").className = "ok-text";
    $("save-msg").textContent = "Saved. All your timetables together: " + r.entries + " entries, breaks included.";
    showClashes(r.clashes);
    toast("Timetable saved.");
    await load(sheet.id);
  } catch (e) {
    $("save-msg").className = "error";
    $("save-msg").textContent = e.message;
  }
}

function showClashes(list) {
  $("clashes").classList.toggle("hidden", !list.length);
  $("clashes").innerHTML = list.length ? "<b>&#9888; Clashes between your timetables:</b><br>" + list.map(esc).join("<br>") : "";
}

// ---------- Several timetables ----------
function showSheets() {
  $("sheet-chips").innerHTML = sheets.map((s, i) =>
    "<button class='chip" + (i === sheetIndex ? " active" : "") + "' onclick='pickSheet(" + i + ")'>" + esc(s.name) + "</button>").join("");
}

function pickSheet(i) {
  if (changed && i !== sheetIndex && !confirm("You have unsaved changes in " + sheets[sheetIndex].name + ". Leave them?")) return;
  sheetIndex = i;
  const s = sheets[i];
  $("template").value = s.template;
  $("saturday").checked = s.saturday;
  slots = s.slots;
  cells = s.cells;
  if (slots.length) $("day-start").value = slots[0].start;
  changed = false;
  showSheets();
  showSlots();
  showGrid();
}

async function addSheet() {
  const name = prompt("Name of the new timetable, e.g. School of CS - BCA");
  if (!name || !name.trim()) return;
  if (changed && !confirm("You have unsaved changes. Leave them?")) return;
  const r = await api("POST", "/api/timetable/" + PERSON_ID + "/sheets", { name: name.trim() });
  changed = false;
  await load(r.id);
}

function renameSheet() {
  const name = prompt("New name for this timetable", sheets[sheetIndex].name);
  if (!name || !name.trim()) return;
  sheets[sheetIndex].name = name.trim();
  changed = true;
  showSheets();
  toast("Renamed. Press Save to keep it.");
}

async function deleteSheet() {
  if (!confirm("Delete the timetable " + sheets[sheetIndex].name + "?")) return;
  await api("DELETE", "/api/timetable/" + PERSON_ID + "/sheets/" + sheets[sheetIndex].id);
  changed = false;
  await load();
}

async function load(selectId) {
  const data = await api("GET", "/api/timetable/" + PERSON_ID);
  const firstTime = options === null;
  options = data;
  sheets = data.sheets;
  busy = data.busy;
  $("person-name").textContent = data.person.name;
  if (firstTime) {
    $("len-hour").value = data.lengths.hour;
    $("len-tea").value = data.lengths.tea;
    $("len-lunch").value = data.lengths.lunch;
    fillEditorChoices(data);
  }
  const i = sheets.findIndex(s => s.id === selectId);
  changed = false;
  pickSheet(i >= 0 ? i : 0);
}

function fillEditorChoices(data) {
  $("ed-activity").innerHTML = "<option value=''>Free (in my cabin)</option>" +
    data.activities.map(a => "<option>" + a + "</option>").join("");
  $("ed-building").innerHTML = "<option value=''>Block</option>" + data.buildings.map(b => "<option>" + b + "</option>").join("");
  $("ed-floor").innerHTML = data.floors.map(f => "<option value='" + f.value + "'>" + f.label + "</option>").join("");
  $("ed-number").innerHTML = "<option value='0'>Room no.</option>" + data.numbers.map(n => "<option>" + n + "</option>").join("");
}

$("work-out").onclick = () => { workOutTimes(); changed = true; };
$("template").onchange = () => { workOutTimes(); changed = true; };
$("saturday").onchange = () => { showGrid(); changed = true; };
$("sheet-add").onclick = addSheet;
$("sheet-rename").onclick = renameSheet;
$("sheet-delete").onclick = deleteSheet;
window.addEventListener("beforeunload", e => { if (changed) { e.preventDefault(); e.returnValue = ""; } });
$("ed-activity").onchange = editorChanged;
$("ed-ok").onclick = saveEditor;
$("ed-cancel").onclick = () => $("editor").classList.add("hidden");
$("save").onclick = save;
load();
