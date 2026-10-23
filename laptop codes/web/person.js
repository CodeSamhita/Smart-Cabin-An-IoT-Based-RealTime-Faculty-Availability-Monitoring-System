// Smart Cabin - one person's page. The person is chosen by ?id=... in the address.

var personId = new URLSearchParams(location.search).get("id");

function showStatus(person) {
  var s = getPersonStatus(person);

  document.getElementById("person-name").textContent = person.name;
  var details = [person.designation, groupLabel(person)];
  if (person.cabin) {
    details.push(person.cabin);
  }
  document.getElementById("person-details").textContent = details.join("  |  ");

  document.getElementById("status-icon").className = "big-icon " + s.status;
  document.getElementById("status-icon").textContent = STATUS_INFO[s.status].icon;
  document.getElementById("status-text").textContent = STATUS_INFO[s.status].long;
  document.getElementById("status-reason").textContent = s.reason ? "Reason: " + s.reason : "";
  document.getElementById("status-back").textContent = s.expected_back ? "Expected back: " + s.expected_back : "";
  document.getElementById("status-time").textContent = s.last_checked || "-";

  if (s.manual) {
    document.getElementById("status-manual").classList.remove("hidden");
  } else {
    document.getElementById("status-manual").classList.add("hidden");
  }

  var list = document.getElementById("evidence-list");
  list.innerHTML = "";
  for (var i = 0; i < s.evidence.length; i++) {
    var li = document.createElement("li");
    li.textContent = s.evidence[i];
    list.appendChild(li);
  }
}

function showTimetable(person) {
  var today = todayName();
  var now = nowHHMM();
  var rows = getTimetable(person);
  var body = document.getElementById("timetable-body");

  document.getElementById("today-name").textContent = today;
  body.innerHTML = "";

  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    if (r.day !== today) {
      continue;
    }
    var tr = document.createElement("tr");
    if (now >= r.start && now < r.end) {
      tr.className = "now";      // happening right now
    }
    tr.innerHTML = "<td></td><td></td>";
    tr.children[0].textContent = r.start + " - " + r.end;
    tr.children[1].textContent = r.activity;
    body.appendChild(tr);
  }

  if (body.children.length === 0) {
    body.innerHTML = "<tr><td>No classes today</td></tr>";
  }
}

function showPage() {
  var person = findPerson(personId);
  if (!person) {
    document.getElementById("not-found").classList.remove("hidden");
    document.getElementById("person-page").classList.add("hidden");
    return;
  }
  document.title = "Smart Cabin - " + person.name;
  showStatus(person);
  showTimetable(person);
}

startAutoRefresh(showPage);
