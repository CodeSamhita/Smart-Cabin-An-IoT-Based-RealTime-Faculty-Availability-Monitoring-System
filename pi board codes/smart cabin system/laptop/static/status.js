// Smart Cabin - the public status page: everyone's status, with search and quick filters.
// Refreshes every 10 s. The filters stay as they are while it refreshes.

let people = [];
let chosenStatus = "";
let chosenPosition = "";

const STATUSES = [["", "Everyone"], ["green", "Available"], ["yellow", "In a meeting"], ["red", "Not available"]];
const POSITIONS = [["", "All"], ["Dean", "Deans"], ["HOD", "HODs"], ["Faculty", "Faculty"]];

// Extra words that find a status, so "free" finds Available and "busy" finds In a meeting
const STATUS_WORDS = {
  green: "available free in cabin",
  yellow: "meeting busy visitors in cabin",
  red: "unavailable away out class lab break leave",
  grey: "unknown offline"
};
// (The status label itself is not searched: "Not available" contains "available", which would match everyone.)

function chips(boxId, options, chosen, pick) {
  $(boxId).innerHTML = "";
  options.forEach(([value, label]) => {
    const b = document.createElement("button");
    b.className = "chip" + (value === chosen ? " active" : "");
    b.textContent = label;
    b.onclick = () => pick(value);
    $(boxId).appendChild(b);
  });
}

function fillSelect(id, label, values, keep) {
  const select = $(id);
  select.innerHTML = "<option value=''>" + label + "</option>" +
    values.map(v => "<option" + (v === keep ? " selected" : "") + ">" + esc(v) + "</option>").join("");
}

function unique(list) { return [...new Set(list.filter(Boolean))].sort(); }

function searchText(p) {
  return [p.name, p.position, p.designation, p.school, p.department, p.cabin, p.reason,
          STATUS_WORDS[p.status]].join(" ").toLowerCase();
}

function matches(p, words) {
  if (chosenStatus && p.status !== chosenStatus) return false;
  if (chosenPosition && p.position !== chosenPosition) return false;
  if ($("school").value && p.school !== $("school").value) return false;
  if ($("department").value && p.department !== $("department").value) return false;
  const text = searchText(p);
  return words.every(w => text.includes(w));         // every typed word must appear somewhere
}

function card(p) {
  return "<a class='person-card " + p.status + "' href='/person/" + p.id + "'>" +
    "<div class='name'>" + esc(p.name) + "</div>" +
    "<div class='small'>" + esc([p.position !== "Faculty" ? p.position : "", p.designation].filter(Boolean).join(", ")) + "</div>" +
    "<div class='small'>" + esc(p.department || p.school) + (p.cabin ? " &middot; " + esc(p.cabin) : "") + "</div>" +
    "<div class='status-line'><span class='dot " + p.status + "'></span>" + esc(p.label) +
    (p.manual ? " <span class='tag'>set by them</span>" : "") + "</div>" +
    "<div class='small'>" + esc(p.reason) + (p.until ? ", " + esc(p.until) : "") + "</div></a>";
}

function show() {
  const words = $("search").value.toLowerCase().replace(/not available|not free/g, "unavailable")
    .split(/\s+/).filter(Boolean);
  // Department list follows the chosen school
  const school = $("school").value;
  fillSelect("department", "All departments",
             unique(people.filter(p => !school || p.school === school).map(p => p.department)), $("department").value);

  const shown = people.filter(p => matches(p, words));
  // Available people first, then in a meeting, then the rest; by name inside each
  const order = { green: 0, yellow: 1, red: 2, grey: 3 };
  shown.sort((a, b) => order[a.status] - order[b.status] || a.name.localeCompare(b.name));
  $("cards").innerHTML = shown.map(card).join("");

  const free = people.filter(p => p.status === "green").length;
  $("summary").textContent = people.length
    ? free + " of " + people.length + " available now" + (shown.length !== people.length ? " · showing " + shown.length : "")
    : "";
  $("empty").classList.toggle("hidden", shown.length > 0);
  $("empty").textContent = people.length ? "Nobody matches. Try fewer words." : "Nobody is registered yet.";

  chips("status-chips", STATUSES, chosenStatus, v => { chosenStatus = v; show(); });
  chips("position-chips", POSITIONS, chosenPosition, v => { chosenPosition = v; show(); });
}

async function load() {
  try {
    const data = await api("GET", "/api/people");
    people = data.people;
    fillSelect("school", "All schools", unique(people.map(p => p.school)), $("school").value);
    show();
  } catch (e) {
    $("summary").textContent = "Can't reach the server: " + e.message;
  }
}

$("search").addEventListener("input", show);
$("school").addEventListener("change", () => { $("department").value = ""; show(); });
$("department").addEventListener("change", show);
load();
setInterval(load, 10000);
