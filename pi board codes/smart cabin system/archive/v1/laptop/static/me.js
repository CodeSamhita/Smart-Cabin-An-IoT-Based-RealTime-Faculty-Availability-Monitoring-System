// Smart Cabin - a faculty member's own page: status and buttons, today's timetable, devices, password.

const ICONS = { green: "✔", yellow: "●●", red: "✖", grey: "?" };
const BUTTON_STATUS = { available: "green", meeting: "yellow", away: "red" };

function showStatus(s) {
  $("icon").className = "big-icon " + s.status;
  $("icon").textContent = ICONS[s.status];
  $("label").textContent = s.label;
  $("reason").textContent = s.reason;
  $("until").textContent = s.until;
  $("manual").classList.toggle("hidden", !s.manual);
  // Outline the button that is active
  document.querySelectorAll(".status-buttons button").forEach(b => {
    const mode = b.dataset.mode;
    b.classList.toggle("chosen", mode === "auto" ? !s.button : BUTTON_STATUS[mode] === s.button);
  });
}

async function loadStatus() { showStatus(await api("GET", "/api/my/status")); }

async function press(mode) {
  try {
    const s = await api("POST", "/api/my/status", { mode: mode, reason: $("reason-select").value, minutes: Number($("minutes").value) });
    showStatus(s);
    toast(mode === "auto" ? "Back to automatic (sensors and timetable)." : "Status set: " + s.label);
  } catch (e) { toast(e.message); }
}

async function loadToday() {
  const p = await api("GET", "/api/people/" + MY_ID);
  $("today").innerHTML = p.today && p.today.length
    ? "<b>Today (" + esc(p.today_name) + ")</b><table>" + p.today.map(e =>
        "<tr><td>" + e.start + " - " + e.end + "</td><td>" + esc(e.text) + "</td></tr>").join("") + "</table>"
    : "<p>Nothing in your timetable for today yet.</p>";
}

async function loadDevices() {
  const d = await api("GET", "/api/my/devices");
  $("cabin").textContent = d.cabin ? "Cabin: " + d.cabin + " · device " + (d.device_online ? "online" : "offline")
                                   : "No cabin yet. The admin sets one up for you.";
  $("cards").innerHTML = d.cards.length ? d.cards.map(c => "<div class='list-row'><span class='mono'>" + esc(c.uid) +
      "</span><span>added " + esc(c.added) + " <button class='danger small-btn' onclick='removeCard(\"" + esc(c.uid) +
      "\")'>Remove</button></span></div>").join("") : "No card linked yet.";
  $("phones").innerHTML = d.phones.length ? d.phones.map(p => "<div class='list-row'><span>" + esc(p.name) +
      "<br><span class='mono'>" + esc(p.address) + "</span></span><button class='danger small-btn' onclick='removePhone(\"" +
      esc(p.address) + "\")'>Remove</button></div>").join("") + "<p>" + d.phones.length + " of " + d.max_phones + "</p>"
    : "No phone paired yet (0 of " + d.max_phones + ").";
  $("face").textContent = d.face_photos ? "Registered (" + d.face_photos + " photos, kept only on the cabin device)." : "Not registered yet.";
}

async function removeCard(uid) {
  if (confirm("Remove card " + uid + "?")) { await api("DELETE", "/api/my/cards/" + uid); loadDevices(); }
}
async function removePhone(address) {
  if (confirm("Remove this device?")) { await api("DELETE", "/api/my/phones/" + address); loadDevices(); }
}

async function changePassword() {
  $("pw-msg").className = "small";
  if ($("new1").value !== $("new2").value) {
    $("pw-msg").className = "error"; $("pw-msg").textContent = "The two new passwords are different."; return;
  }
  try {
    await api("POST", "/api/me/password", { old_password: $("old").value, new_password: $("new1").value });
    $("pw-msg").className = "ok-text"; $("pw-msg").textContent = "Password changed.";
    ["old", "new1", "new2"].forEach(id => $(id).value = "");
  } catch (e) { $("pw-msg").className = "error"; $("pw-msg").textContent = e.message; }
}

document.querySelectorAll(".status-buttons button").forEach(b => b.onclick = () => press(b.dataset.mode));
$("change").onclick = changePassword;
loadStatus(); loadToday(); loadDevices();
setInterval(loadStatus, 10000);
setInterval(loadDevices, 30000);
