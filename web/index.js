// Smart Cabin - home page: a grid of cards, one per person, with keyword search.

// What is chosen with the quick select buttons ("" means all)
var selectedSchool = "";
var selectedRole = "";

var ROLES = [["", "Everyone"], ["Dean", "Deans"], ["HOD", "HODs"], ["Faculty", "Faculty"]];

function showButtons() {
  // Role buttons
  makeButtons("role-buttons", ROLES, selectedRole, function (value) {
    selectedRole = value;
    showButtons();
    showCards();
  });

  // School buttons: "All schools" plus each school once
  var schools = [["", "All schools"]];
  var seen = [];
  var list = getPeople();
  for (var i = 0; i < list.length; i++) {
    if (seen.indexOf(list[i].school) === -1) {
      seen.push(list[i].school);
      schools.push([list[i].school, schoolLabel(list[i].school)]);
    }
  }
  makeButtons("school-buttons", schools, selectedSchool, function (value) {
    selectedSchool = value;
    showButtons();
    showCards();
  });
}

function matchesSearch(person, status, words) {
  // Every typed word must appear somewhere in the person's details
  var text = [person.name, person.designation, person.role, person.school, person.department,
              person.cabin, STATUS_INFO[status.status].short, STATUS_INFO[status.status].long,
              status.reason].join(" ").toLowerCase();
  for (var i = 0; i < words.length; i++) {
    if (text.indexOf(words[i]) === -1) {
      return false;
    }
  }
  return true;
}

function makeCard(person, status) {
  var card = document.createElement("a");
  card.className = "person-card " + status.status;
  card.href = "person.html?id=" + encodeURIComponent(person.id);

  card.innerHTML =
    "<div class='name'></div>" +
    "<div class='small'></div>" +
    "<div class='status-line'><span class='dot'></span><span></span></div>" +
    "<div class='small'></div>";

  card.children[0].textContent = person.name;
  card.children[1].textContent = person.designation + (person.cabin ? " - " + person.cabin : "");
  card.children[2].children[0].className = "dot " + status.status;
  card.children[2].children[0].textContent = STATUS_INFO[status.status].icon;
  card.children[2].children[1].textContent = STATUS_INFO[status.status].short + (status.manual ? " (set manually)" : "");

  var extra = status.reason || "";
  if (status.expected_back) {
    extra += (extra ? ", back " : "Back ") + status.expected_back;
  }
  card.children[3].textContent = extra;
  return card;
}

function showCards() {
  var words = document.getElementById("search").value.toLowerCase().split(" ").filter(Boolean);
  var school = selectedSchool;
  var role = selectedRole;
  var box = document.getElementById("cards");
  box.innerHTML = "";

  // Group the matching people by department
  var groups = {};
  var order = [];
  var count = 0;
  var list = getPeople();

  for (var i = 0; i < list.length; i++) {
    var person = list[i];
    var status = getPersonStatus(person);
    if (school && person.school !== school) {
      continue;
    }
    if (role && person.role !== role) {
      continue;
    }
    if (!matchesSearch(person, status, words)) {
      continue;
    }
    // Heading, e.g. "Department of Physics - School of Engineering" or "School of Law"
    var heading = groupLabel(person);
    if (!groups[heading]) {
      groups[heading] = [];
      order.push(heading);
    }
    groups[heading].push(makeCard(person, status));
    count++;
  }

  for (var j = 0; j < order.length; j++) {
    var h2 = document.createElement("h2");
    h2.textContent = order[j] + " (" + groups[order[j]].length + ")";
    box.appendChild(h2);

    var grid = document.createElement("div");
    grid.className = "grid";
    for (var k = 0; k < groups[order[j]].length; k++) {
      grid.appendChild(groups[order[j]][k]);
    }
    box.appendChild(grid);
  }

  document.getElementById("result-count").textContent =
    count === 0 ? "No one matches your search." : "Showing " + count + " of " + list.length + " people";
}

function showPage() {
  showButtons();
  showCards();
}

startAutoRefresh(showPage);
