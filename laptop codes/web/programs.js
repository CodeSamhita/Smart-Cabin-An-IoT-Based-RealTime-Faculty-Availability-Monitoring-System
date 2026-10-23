// Smart Cabin - programmes page: every programme, grouped by degree (B.Tech, M.Tech, MBA, ...),
// with quick select buttons for level and degree, and a search box.

var selectedLevel = "";
var selectedDegree = "";

var LEVELS = [["", "All levels"], ["Bachelor's", "Bachelor's"], ["Master's", "Master's"],
              ["Doctoral", "Ph.D"], ["Diploma", "Diploma"]];

function getPrograms() {
  return getData().programs || [];
}

function degreeOrder(onlyLevel) {
  // All degrees, Bachelor's first, then Master's, Ph.D, Diploma (optionally only one level)
  var degrees = [];
  var list = getPrograms();
  for (var l = 1; l < LEVELS.length; l++) {
    var level = LEVELS[l][0];
    if (onlyLevel && level !== onlyLevel) {
      continue;
    }
    for (var i = 0; i < list.length; i++) {
      if (list[i].level === level && degrees.indexOf(list[i].degree) === -1) {
        degrees.push(list[i].degree);
      }
    }
  }
  return degrees;
}

function showButtons() {
  // Level buttons
  makeButtons("level-buttons", LEVELS, selectedLevel, function (value) {
    selectedLevel = value;
    selectedDegree = "";        // start again with all degrees of this level
    showButtons();
    showPrograms();
  });

  // Degree buttons: only the degrees in the chosen level
  var degrees = [["", "All degrees"]];
  var names = degreeOrder(selectedLevel);
  for (var i = 0; i < names.length; i++) {
    degrees.push([names[i], names[i]]);
  }
  makeButtons("degree-buttons", degrees, selectedDegree, function (value) {
    selectedDegree = value;
    showButtons();
    showPrograms();
  });
}

function showPrograms() {
  var words = document.getElementById("search").value.toLowerCase().split(" ").filter(Boolean);
  var list = getPrograms();
  var box = document.getElementById("programs");
  box.innerHTML = "";

  // Group the matching programmes by degree
  var groups = {};
  var order = [];
  var count = 0;

  for (var i = 0; i < list.length; i++) {
    var p = list[i];
    if (selectedLevel && p.level !== selectedLevel) {
      continue;
    }
    if (selectedDegree && p.degree !== selectedDegree) {
      continue;
    }
    var text = (p.program + " " + p.school + " " + p.degree).toLowerCase();
    var ok = true;
    for (var w = 0; w < words.length; w++) {
      if (text.indexOf(words[w]) === -1) {
        ok = false;
      }
    }
    if (!ok) {
      continue;
    }
    if (!groups[p.degree]) {
      groups[p.degree] = [];
      order.push(p.degree);
    }
    groups[p.degree].push(p);
    count++;
  }

  // Show the degree sections in level order (B.Tech ... M.Tech ... Ph.D ...)
  var all = degreeOrder("");
  order.sort(function (a, b) { return all.indexOf(a) - all.indexOf(b); });

  for (var j = 0; j < order.length; j++) {
    var section = document.createElement("div");
    section.className = "box";
    section.innerHTML = "<h3></h3><table><tbody></tbody></table>";
    section.querySelector("h3").textContent = order[j] + " (" + groups[order[j]].length + ")";

    var body = section.querySelector("tbody");
    for (var k = 0; k < groups[order[j]].length; k++) {
      var p2 = groups[order[j]][k];
      var tr = document.createElement("tr");
      tr.innerHTML = "<td></td><td class='small'></td><td class='small'></td>";
      tr.children[0].textContent = p2.program;
      tr.children[1].textContent = schoolLabel(p2.school);
      tr.children[2].textContent = p2.duration;
      body.appendChild(tr);
    }
    box.appendChild(section);
  }

  document.getElementById("result-count").textContent =
    count === 0 ? "No programme matches your search." : "Showing " + count + " of " + list.length + " programmes";
}

showButtons();
showPrograms();
