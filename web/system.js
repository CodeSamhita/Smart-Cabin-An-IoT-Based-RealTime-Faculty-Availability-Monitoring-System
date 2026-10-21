// Smart Cabin - system page: health, sensors, demo controls and recent changes.

function showHealth() {
  var data = getData();
  var list = getPeople();
  var counts = { green: 0, yellow: 0, red: 0, grey: 0 };

  for (var i = 0; i < list.length; i++) {
    counts[getPersonStatus(list[i]).status]++;
  }

  document.getElementById("last-update").textContent = data.updated || "never (run code/main.py)";
  document.getElementById("people-count").textContent = list.length;
  document.getElementById("status-counts").textContent =
    "Available: " + counts.green + "   With visitors: " + counts.yellow +
    "   Away: " + counts.red + "   Unknown: " + counts.grey;
}

function showSensors() {
  var sensors = getData().sensors || [];
  var list = document.getElementById("sensor-list");
  list.innerHTML = "";

  for (var i = 0; i < sensors.length; i++) {
    var s = sensors[i];
    var li = document.createElement("li");
    if (s.state === "planned" || s.state === "optional") {
      li.className = "future";
    }
    li.innerHTML = "<span class='sensor-state'></span><b></b><br><span class='small'></span>";
    li.children[0].className = "sensor-state " + s.state;
    li.children[0].textContent = s.state === "planned" ? "planned (future)" : s.state;
    li.children[1].textContent = s.name;
    li.children[3].textContent = s.note;
    list.appendChild(li);
  }
}

function fillDemoPeople() {
  var select = document.getElementById("demo-person");
  var chosen = select.value;
  var list = getPeople();
  select.innerHTML = "";
  for (var i = 0; i < list.length; i++) {
    var option = document.createElement("option");
    option.value = list[i].id;
    option.textContent = list[i].name + " (" + groupLabel(list[i]) + ")";
    select.appendChild(option);
  }
  if (chosen) {
    select.value = chosen;
  }
}

function demoSet(state) {
  var person = findPerson(document.getElementById("demo-person").value);
  if (!person) {
    return;
  }
  save("sc_demo_" + person.id, state);
  addHistory(person.name, state, "demo", "Set from System page");
  document.getElementById("demo-info").textContent = person.name + " is now shown as " + STATUS_INFO[state].short + ".";
  showPage();
}

function demoClearAll() {
  var list = getPeople();
  for (var i = 0; i < list.length; i++) {
    removeSaved("sc_demo_" + list[i].id);
    removeSaved("sc_override_" + list[i].id);
  }
  document.getElementById("demo-info").textContent = "Cleared. Statuses now come from Python again.";
  showPage();
}

function showHistory() {
  var all = getHistory();
  var body = document.getElementById("history-body");
  body.innerHTML = "";

  for (var i = 0; i < all.length && i < 30; i++) {
    var tr = document.createElement("tr");
    tr.innerHTML = "<td></td><td></td><td></td><td></td>";
    tr.children[0].textContent = all[i].time;
    tr.children[1].textContent = all[i].person;
    tr.children[2].textContent = all[i].status;
    tr.children[3].textContent = all[i].source;
    body.appendChild(tr);
  }

  if (body.children.length === 0) {
    body.innerHTML = "<tr><td colspan='4'>No changes yet. Run code/main.py to create some.</td></tr>";
  }
}

function showPage() {
  showHealth();
  showSensors();
  fillDemoPeople();
  showHistory();
}

startAutoRefresh(showPage);
