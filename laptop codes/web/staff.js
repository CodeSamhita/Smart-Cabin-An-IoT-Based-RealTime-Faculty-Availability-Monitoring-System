// Smart Cabin - staff panel. Any HOD or faculty member can log in and manage their own status.

var DEMO_PASSWORD = "staff123";   // demo only - a real login must be checked on a server
var me = null;                     // the person who is logged in


// ---------- Login ----------

function fillLoginList() {
  var select = document.getElementById("login-person");
  var list = getPeople();
  select.innerHTML = "<option value=''>Choose your name</option>";
  for (var i = 0; i < list.length; i++) {
    var option = document.createElement("option");
    option.value = list[i].id;
    option.textContent = list[i].name + " (" + groupLabel(list[i]) + ")";
    select.appendChild(option);
  }
}

function login() {
  var id = document.getElementById("login-person").value;
  var pw = document.getElementById("password").value;
  if (!id) {
    document.getElementById("login-error").textContent = "Please choose your name.";
  } else if (pw !== DEMO_PASSWORD) {
    document.getElementById("login-error").textContent = "Wrong password.";
  } else {
    sessionStorage.setItem("sc_staff", id);
    showPanel();
  }
}

function logout() {
  sessionStorage.removeItem("sc_staff");
  location.reload();
}

function showPanel() {
  me = findPerson(sessionStorage.getItem("sc_staff"));
  if (!me) {
    return;
  }
  document.getElementById("logged-in-as").textContent = "Logged in as " + me.name + " - " + groupLabel(me);
  document.getElementById("login-box").classList.add("hidden");
  document.getElementById("panel").classList.remove("hidden");
  showOverrideInfo();
  showTimetableEditor(getTimetable(me));
  showHistory();
}


// ---------- Set my status ----------

function setOverride(status, reason) {
  var hours = parseFloat(document.getElementById("expire-hours").value);
  var backTime = document.getElementById("back-time").value;

  save("sc_override_" + me.id, {
    status: status,
    reason: reason,
    expected_back: backTime ? "at " + backTime : "",
    until: Date.now() + hours * 60 * 60 * 1000
  });
  addHistory(me.name, status, "set manually", reason || "Available");
  showOverrideInfo();
  showHistory();
}

function clearOverride() {
  removeSaved("sc_override_" + me.id);
  addHistory(me.name, "-", "set manually", "Cleared");
  showOverrideInfo();
  showHistory();
}

function showOverrideInfo() {
  var o = getOverride(me.id);
  var info = document.getElementById("override-info");
  if (o) {
    info.textContent = "Now showing: " + STATUS_INFO[o.status].short + (o.reason ? " (" + o.reason + ")" : "") +
      " until " + new Date(o.until).toLocaleTimeString();
  } else {
    info.textContent = "Nothing set. Your status comes from the camera and timetable.";
  }
}


// ---------- My timetable ----------

function showTimetableEditor(rows) {
  document.getElementById("tt-body").innerHTML = "";
  for (var i = 0; i < rows.length; i++) {
    addRow(rows[i]);
  }
}

function addRow(row) {
  row = row || { day: "Monday", start: "09:00", end: "10:00", activity: "" };
  var tr = document.createElement("tr");
  tr.innerHTML =
    "<td><input class='tt-day'></td>" +
    "<td><input class='tt-start' type='time'></td>" +
    "<td><input class='tt-end' type='time'></td>" +
    "<td><input class='tt-activity'></td>" +
    "<td><button onclick='this.parentNode.parentNode.remove()'>X</button></td>";
  tr.querySelector(".tt-day").value = row.day;
  tr.querySelector(".tt-start").value = row.start;
  tr.querySelector(".tt-end").value = row.end;
  tr.querySelector(".tt-activity").value = row.activity;
  document.getElementById("tt-body").appendChild(tr);
}

function saveTimetable() {
  var rows = [];
  var trs = document.getElementById("tt-body").children;
  for (var i = 0; i < trs.length; i++) {
    rows.push({
      day: trs[i].querySelector(".tt-day").value.trim(),
      start: trs[i].querySelector(".tt-start").value,
      end: trs[i].querySelector(".tt-end").value,
      activity: trs[i].querySelector(".tt-activity").value.trim()
    });
  }
  save("sc_timetable_" + me.id, rows);
  document.getElementById("tt-info").textContent = "Saved. Your page now uses this timetable.";
}

function resetTimetable() {
  removeSaved("sc_timetable_" + me.id);
  showTimetableEditor(getTimetable(me));
  document.getElementById("tt-info").textContent = "Back to the timetable from data/timetable.csv.";
}

function loadCsv() {
  var file = document.getElementById("csv-file").files[0];
  if (!file) {
    return;
  }
  var reader = new FileReader();
  reader.onload = function () {
    var lines = reader.result.split(/\r?\n/);
    var rows = [];
    for (var i = 0; i < lines.length; i++) {
      var parts = lines[i].split(",");
      // Skip empty lines and the header line
      if (parts.length < 4 || parts[0].trim().toLowerCase() === "day") {
        continue;
      }
      rows.push({ day: parts[0].trim(), start: parts[1].trim(), end: parts[2].trim(),
                  activity: parts.slice(3).join(",").trim() });
    }
    showTimetableEditor(rows);
    document.getElementById("tt-info").textContent =
      "Loaded " + rows.length + " rows from " + file.name + ". Click Save to use them.";
  };
  reader.readAsText(file);
}


// ---------- My history ----------

function showHistory() {
  var all = getHistory();
  var body = document.getElementById("history-body");
  body.innerHTML = "";

  for (var i = 0; i < all.length; i++) {
    if (all[i].person !== me.name) {
      continue;
    }
    var tr = document.createElement("tr");
    tr.innerHTML = "<td></td><td></td><td></td><td></td>";
    tr.children[0].textContent = all[i].time;
    tr.children[1].textContent = all[i].status;
    tr.children[2].textContent = all[i].source;
    tr.children[3].textContent = all[i].note;
    body.appendChild(tr);
  }

  if (body.children.length === 0) {
    body.innerHTML = "<tr><td colspan='4'>No changes yet.</td></tr>";
  }
}


// ---------- Start ----------

fillLoginList();
if (sessionStorage.getItem("sc_staff")) {
  showPanel();      // stay logged in while this tab is open
}
