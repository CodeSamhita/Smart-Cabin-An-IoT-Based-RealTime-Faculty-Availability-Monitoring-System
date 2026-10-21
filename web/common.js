// Smart Cabin - helpers used by every page.
// The data comes from data.js (written by Python) in a variable called SMART_CABIN.
// Demo choices and staff overrides are saved in the browser (localStorage) and win over data.js.

var REFRESH_SECONDS = 10;

var STATUS_INFO = {
  green:  { icon: "✔",       short: "Available",     long: "In cabin - available" },
  yellow: { icon: "●●", short: "With visitors", long: "In cabin - with visitors" },
  red:    { icon: "✖",       short: "Away",          long: "Not in cabin" },
  grey:   { icon: "?",            short: "Unknown",       long: "Unknown" }
};

// Sample statuses used by the demo buttons on the System page
var DEMO_STATES = {
  green:  { reason: "", expected_back: "", people_count: 1,
            evidence: ["Camera: person seen, nobody else in the cabin"] },
  yellow: { reason: "", expected_back: "", people_count: 3,
            evidence: ["Camera: person seen with 2 visitors"] },
  red:    { reason: "In class - Room 204", expected_back: "around 10:05", people_count: 0,
            evidence: ["Timetable: in class", "Camera: cabin empty"] },
  grey:   { reason: "Camera could not confirm", expected_back: "", people_count: 0,
            evidence: ["Camera: no usable snapshot"] }
};

var DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];


// ---------- Saving in the browser ----------

function readSaved(key) {
  try {
    var text = localStorage.getItem(key);
    return text ? JSON.parse(text) : null;
  } catch (e) {
    return null;
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    // Some browsers block storage for local files; the page still works without it
  }
}

function removeSaved(key) {
  try {
    localStorage.removeItem(key);
  } catch (e) {}
}


// ---------- Time ----------

function nowHHMM() {
  var d = new Date();
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

function todayName() {
  return DAYS[new Date().getDay()];
}


// ---------- Data from Python ----------

function getData() {
  if (typeof SMART_CABIN !== "undefined") {
    return SMART_CABIN;
  }
  return { title: "Smart Cabin", subtitle: "No data yet - run code/main.py",
           people: [], sensors: [], history: [] };
}

function getPeople() {
  return getData().people || [];
}

function findPerson(id) {
  var list = getPeople();
  for (var i = 0; i < list.length; i++) {
    if (list[i].id === id) {
      return list[i];
    }
  }
  return null;
}

function schoolLabel(school) {
  // "Presidency School of Law" -> "School of Law" (shorter for buttons and headings)
  return (school || "").replace(/^Presidency /, "");
}

function groupLabel(person) {
  // "Department of Physics - School of Engineering", or just "School of Law"
  if (person.department === person.school) {
    return schoolLabel(person.school);
  }
  return person.department + " - " + schoolLabel(person.school);
}

function getTimetable(person) {
  // A timetable saved from the staff page wins over the one from Python
  return readSaved("sc_timetable_" + person.id) || person.timetable || [];
}

function getOverride(id) {
  // Staff override, only if it has not expired
  var o = readSaved("sc_override_" + id);
  if (o && o.until && Date.now() > o.until) {
    removeSaved("sc_override_" + id);
    return null;
  }
  return o;
}

function getPersonStatus(person) {
  // Final status for one person: override > demo > data from Python
  var s = {
    status: person.status,
    reason: person.reason,
    expected_back: person.expected_back,
    people_count: person.people_count,
    evidence: person.evidence || [],
    last_checked: person.last_checked,
    manual: false
  };

  var demo = readSaved("sc_demo_" + person.id);
  if (demo && DEMO_STATES[demo]) {
    s.status = demo;
    s.reason = DEMO_STATES[demo].reason;
    s.expected_back = DEMO_STATES[demo].expected_back;
    s.people_count = DEMO_STATES[demo].people_count;
    s.evidence = DEMO_STATES[demo].evidence.concat(["(Demo mode)"]);
  }

  var o = getOverride(person.id);
  if (o) {
    s.status = o.status;
    s.reason = o.reason;
    s.expected_back = o.expected_back;
    s.people_count = null;
    s.evidence = ["Set manually by " + person.name,
                  "Expires at " + new Date(o.until).toLocaleTimeString()];
    s.manual = true;
  }

  if (!STATUS_INFO[s.status]) {
    s.status = "grey";
  }
  return s;
}

function addHistory(personName, status, source, note) {
  var list = readSaved("sc_history") || [];
  list.unshift({ time: new Date().toLocaleTimeString(), person: personName,
                 status: status, source: source, note: note });
  save("sc_history", list.slice(0, 50));
}

function getHistory() {
  // Changes saved in this browser first, then the log from Python
  return (readSaved("sc_history") || []).concat(getData().history || []);
}


// ---------- Quick select buttons ----------

function makeButtons(boxId, options, selected, onPick) {
  // One button per option. options is a list of [value, label]
  var box = document.getElementById(boxId);
  box.innerHTML = "";
  for (var i = 0; i < options.length; i++) {
    var b = document.createElement("button");
    b.className = options[i][0] === selected ? "chip active" : "chip";
    b.textContent = options[i][1];
    b.onclick = onPick.bind(null, options[i][0]);
    box.appendChild(b);
  }
}


// ---------- Page header ----------

function showHeader() {
  // Fill in the title and subtitle from Python (config.py) in the header of every page
  var data = getData();
  var title = document.getElementById("site-title");
  var subtitle = document.getElementById("site-subtitle");
  if (title) {
    title.textContent = data.title || "Smart Cabin";
  }
  if (subtitle) {
    subtitle.textContent = data.subtitle || "";
  }
}


// ---------- Live update without a server ----------

function reloadData(callback) {
  // Load data.js again so new values written by Python appear
  var old = document.getElementById("data-script");
  var s = document.createElement("script");
  s.id = "data-script";
  s.src = "data.js?t=" + Date.now();
  s.onload = callback;
  s.onerror = callback;
  if (old) {
    old.remove();
  }
  document.body.appendChild(s);
}

function startAutoRefresh(callback) {
  callback();
  setInterval(function () { reloadData(callback); }, REFRESH_SECONDS * 1000);
}


// Every page has the same header, so fill it in straight away
showHeader();
