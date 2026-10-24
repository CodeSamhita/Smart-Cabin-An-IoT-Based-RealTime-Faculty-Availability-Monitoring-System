// Smart Cabin - one person's page. Everyone sees the status. Logged-in staff also see the timetable,
// when the person is expected back, and can ask to be notified when the person is available.

const ICONS = { green: "✔", yellow: "●●", red: "✖", grey: "?" };
let panelsReady = false;

function nowMinutes() { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); }
function minutes(hhmm) { const [h, m] = hhmm.split(":"); return Number(h) * 60 + Number(m); }

function timetableRows(entries, highlightNow) {
  if (!entries.length) return "<tr><td class='small'>Nothing in the timetable.</td></tr>";
  const now = nowMinutes();
  return entries.map(e => {
    const isNow = highlightNow && minutes(e.start) <= now && now < minutes(e.end);
    return "<tr class='" + (isNow ? "now" : "") + "'><td>" + e.start + " - " + e.end + "</td><td>" + esc(e.text) + "</td></tr>";
  }).join("");
}

function showWatch(p) {
  const box = $("watch-box");
  if (!p.logged_in || p.is_me) { box.innerHTML = ""; return; }
  if (p.status === "green") {
    box.innerHTML = "<p class='ok-text'>Available now.</p>";
  } else if (p.watching) {
    box.innerHTML = "<p class='small'>&#128276; You'll be notified when they are available (while this site is open).</p>" +
                    "<button class='plain' onclick='unwatch()'>Stop notifying me</button>";
  } else {
    box.innerHTML = "<button onclick='watch()'>&#128276; Notify me when available</button>";
  }
}

async function load() {
  let p;
  try {
    p = await api("GET", "/api/people/" + PERSON_ID);
  } catch (e) {
    $("not-found").classList.remove("hidden");
    return;
  }
  $("page").classList.remove("hidden");
  document.title = p.name + " - Smart Cabin";
  $("name").textContent = p.name;
  $("details").textContent = [p.position !== "Faculty" ? p.position : "", p.designation, p.department, p.school,
                              p.cabin ? "Cabin: " + p.cabin : ""].filter(Boolean).join(" · ");
  $("icon").className = "big-icon " + p.status;
  $("icon").textContent = ICONS[p.status];
  $("label").textContent = p.label;
  $("reason").textContent = p.reason;
  $("until").textContent = p.until;
  $("manual").classList.toggle("hidden", !p.manual);
  showWatch(p);

  $("login-hint").classList.toggle("hidden", p.logged_in);
  $("today-panel").classList.toggle("hidden", !p.logged_in);
  $("week-panel").classList.toggle("hidden", !p.logged_in);
  if (p.logged_in) {
    $("today-name").textContent = p.today_name;
    const lines = [];
    if (p.now) lines.push("Now: " + p.now);
    if (p.back_at && p.status === "red") lines.push("Expected back around " + p.back_at);
    if (p.next) lines.push("Next: " + p.next);
    $("now-next").textContent = lines.join(" · ");
    $("today").innerHTML = timetableRows(p.today, true);
    const days = [...new Set(p.week.map(e => e.day_name))];
    $("week").innerHTML = days.length ? days.map(d => "<h3>" + d + "</h3><table>" +
      timetableRows(p.week.filter(e => e.day_name === d), false) + "</table>").join("")
      : "<p class='small'>No timetable yet.</p>";
    if (!panelsReady) { setupPanels(); panelsReady = true; }   // rebuild the tabs once the hidden sections show
  }
}

async function watch() {
  askNotificationPermission();
  try { await api("POST", "/api/watches/" + PERSON_ID); toast("You'll be notified when they are available."); }
  catch (e) { toast(e.message); }
  load(); checkWatches();
}

async function unwatch() { await api("DELETE", "/api/watches/" + PERSON_ID); load(); checkWatches(); }
function onWatchChanged() { load(); }

load();
setInterval(load, 10000);
