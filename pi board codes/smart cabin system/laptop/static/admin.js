// Smart Cabin - admin: cabins, their devices, and the activity log.

let faculty = [];

function ownerOptions(selected, cabinId, cabins) {
  // Faculty without a cabin, plus the current owner
  const taken = cabins.filter(c => c.id !== cabinId && c.owner_id).map(c => c.owner_id);
  return "<option value=''>- nobody yet -</option>" + faculty.filter(p => p.active && !taken.includes(p.id))
    .map(p => "<option value='" + p.id + "'" + (p.id === selected ? " selected" : "") + ">" + esc(p.name) + "</option>").join("");
}

function sensorText(sensors) {
  const names = Object.keys(sensors);
  if (!names.length) return "";
  return names.map(n => (String(sensors[n]).startsWith("ok") ? "✔ " : "✖ ") + n +
    (String(sensors[n]).startsWith("ok") ? "" : ": " + sensors[n])).join(" · ");
}

function cabinRow(c, cabins) {
  const state = !c.connected ? "<span class='tag' style='background:#8a8a8a'>no device yet</span>"
    : c.online ? "<span class='tag' style='background:#2e9e44'>online</span>"
    : "<span class='tag' style='background:#d43c3c'>offline</span>";
  const seen = c.last_report ? "last report " + new Date(c.last_report * 1000).toLocaleString() : "";
  const now = c.online ? " · " + (c.faculty_in ? "faculty in" : "faculty not in") + ", " + c.headcount + " in the cabin" : "";
  return "<div class='box' style='margin: 8px 0;'><div class='list-row'><b>" + esc(c.name) + "</b>" + state + "</div>" +
    "<label>Faculty member</label><select onchange='changeOwner(" + c.id + ", this.value)'>" +
      ownerOptions(c.owner_id, c.id, cabins) + "</select>" +
    "<label>Linked device (it connects by itself when switched on here)</label>" +
    "<div class='form-row'><input id='dev-" + c.id + "' value='" + esc(c.device_id || "") + "' placeholder='Pi serial from the box label, or use Add a new device'>" +
    "<button class='plain small-btn' style='flex:none' onclick='linkDevice(" + c.id + ")'>Save</button></div>" +
    (c.device_name ? "<p class='small'>Device: " + esc(c.device_name) + "</p>" : "") +
    "<p class='small'>" + esc(seen + now) + "</p>" +
    (sensorText(c.sensors || {}) ? "<p class='small'>" + esc(sensorText(c.sensors)) + "</p>" : "") +
    (c.setup_code ? "<p>Device code: <span class='code'>" + c.setup_code + "</span><br><span class='small'>Type it on the Pi's page within 15 minutes.</span></p>" : "") +
    "<button class='plain small-btn' onclick='newCode(" + c.id + ")'>New code</button> " +
    "<button class='danger small-btn' onclick='removeCabin(" + c.id + ", \"" + esc(c.name).replace(/"/g, "") + "\")'>Delete</button></div>";
}

async function load() {
  faculty = (await api("GET", "/api/admin/faculty")).faculty;
  const cabins = (await api("GET", "/api/admin/cabins")).cabins;
  $("count").textContent = cabins.length;
  $("c-owner").innerHTML = ownerOptions(null, null, cabins);
  $("cabins").innerHTML = cabins.length ? cabins.map(c => cabinRow(c, cabins)).join("")
    : "<p class='small'>No cabins yet. Register faculty first (Register page), then add their cabin here.</p>";
  const events = (await api("GET", "/api/admin/events")).events;
  $("events").innerHTML = events.length ? events.map(e => "<div class='list-row'><span><b>" + esc(e.kind) + "</b> " +
    esc(e.name || "") + " " + esc(e.detail) + "</span><span class='mono' style='flex:none'>" + esc(e.time) + "</span></div>").join("")
    : "Nothing yet.";
}

async function addCabin() {
  $("c-error").textContent = "";
  try {
    const owner = $("c-owner").value;
    const r = await api("POST", "/api/admin/cabins", { name: $("c-name").value, owner_id: owner ? Number(owner) : null });
    $("c-name").value = "";
    toast("Cabin added. Device code: " + r.code);
    load();
  } catch (e) { $("c-error").textContent = e.message; }
}

async function changeOwner(id, owner) {
  const cabin = (await api("GET", "/api/admin/cabins")).cabins.find(c => c.id === id);
  try {
    await api("PUT", "/api/admin/cabins/" + id, { name: cabin.name, owner_id: owner ? Number(owner) : null });
    toast("Saved.");
  } catch (e) { toast(e.message); }
  load();
}

async function linkDevice(id) {
  // Link a device ID typed from the box label (empty = unlink). The Pi then connects by itself in this cabin.
  const cabin = (await api("GET", "/api/admin/cabins")).cabins.find(c => c.id === id);
  try {
    await api("PUT", "/api/admin/cabins/" + id, { name: cabin.name, owner_id: cabin.owner_id, device_id: $("dev-" + id).value.trim() });
    toast($("dev-" + id).value.trim() ? "Device linked. Switch it on in this cabin." : "Device unlinked.");
  } catch (e) { toast(e.message); }
  load();
}

async function newCode(id) { await api("POST", "/api/admin/cabins/" + id + "/code"); load(); }

async function removeCabin(id, name) {
  if (!confirm("Delete the cabin " + name + "? Its device will stop working.")) return;
  await api("DELETE", "/api/admin/cabins/" + id);
  load();
}

// ---------- Add a new device: Pis waiting to be connected ----------
let cabinList = [];
let lookingForDevices = false;

async function showWaitingDevices() {
  if (!lookingForDevices) return;
  const devices = (await api("GET", "/api/admin/device-requests")).devices;
  cabinList = (await api("GET", "/api/admin/cabins")).cabins;
  const box = $("device-list");
  if (!devices.length) {
    box.innerHTML = "<p class='small'>Looking for Pis... (switch the Pi on and start main.py; it takes a few seconds)</p>";
    return;
  }
  // Keep what the admin already chose / typed in each row while the list refreshes
  const kept = {};
  box.querySelectorAll("[data-keep]").forEach(el => kept[el.dataset.keep] = el.value);
  const cabinOptions = "<option value=''>Which cabin is this?</option><option value='new'>+ New cabin...</option>" +
    cabinList.map(c => "<option value='" + c.id + "'>" + esc(c.name) + (c.device_id ? " (has a device)" : "") + "</option>").join("");
  const facultyOptions = "<option value=''>Who sits there? (registered faculty)</option>" +
    faculty.filter(p => p.active).map(p => "<option value='" + p.id + "'>" + esc(p.name) +
      (p.cabin ? " - now in " + esc(p.cabin) : "") + "</option>").join("");
  box.innerHTML = devices.map(d => {
    const id = esc(d.device_id);
    return "<div class='box' style='margin: 6px 0;'><div class='list-row'><b>" + esc(d.name || "Raspberry Pi") + "</b>" +
      "<span>PIN <span class='code' style='font-size:20px'>" + esc(d.pin) + "</span></span></div>" +
      "<div class='small'>" + esc(d.model) + " &middot; " + esc(d.ip) + " &middot; ID " + id + " &middot; seen " + d.seen_ago + " s ago</div>" +
      ("<select data-keep='cabin-" + id + "' onchange='showNewCabin(\"" + id + "\")'>" + cabinOptions + "</select>" +
        "<input data-keep='newname-" + id + "' class='hidden' placeholder='New cabin, e.g. J block, 4th floor, Cabin 12'>" +
        "<select data-keep='owner-" + id + "' style='margin-top:6px'>" + facultyOptions + "</select>" +
        "<button onclick='connectDevice(\"" + id + "\")'>Connect</button> " +
        "<button class='plain' onclick='ignoreDevice(\"" + id + "\")'>Not this one</button>") +
      "</div>";
  }).join("");
  box.querySelectorAll("[data-keep]").forEach(el => { if (kept[el.dataset.keep] !== undefined) el.value = kept[el.dataset.keep]; });
  devices.forEach(d => showNewCabin(d.device_id));
}

function field(name, deviceId) { return document.querySelector("[data-keep='" + name + "-" + deviceId + "']"); }

function showNewCabin(deviceId) {
  if (field("cabin", deviceId)) field("newname", deviceId).classList.toggle("hidden", field("cabin", deviceId).value !== "new");
}

async function connectDevice(deviceId) {
  // The admin only says which cabin this is and who sits there
  const cabinValue = field("cabin", deviceId).value;
  const ownerValue = field("owner", deviceId).value;
  if (!cabinValue) { toast("Pick the cabin (or + New cabin)."); return; }
  const body = { owner_id: ownerValue ? Number(ownerValue) : null };
  if (cabinValue === "new") {
    body.new_cabin = field("newname", deviceId).value.trim();
    if (!body.new_cabin) { toast("Type the new cabin's name."); return; }
  } else {
    body.cabin_id = Number(cabinValue);
    const cabin = cabinList.find(c => String(c.id) === cabinValue);
    if (cabin.device_id && !confirm(cabin.name + " already has a device. Replace it with this one?")) return;
  }
  try {
    const r = await api("POST", "/api/admin/device-requests/" + encodeURIComponent(deviceId) + "/approve", body);
    toast("Linked to " + r.cabin + ". The Pi connects within a few seconds, and by itself from now on.");
  } catch (e) { toast(e.message); }
  showWaitingDevices(); load();
}

async function ignoreDevice(deviceId) {
  await api("DELETE", "/api/admin/device-requests/" + encodeURIComponent(deviceId));
  showWaitingDevices();
}

$("find-devices").onclick = () => {
  lookingForDevices = !lookingForDevices;
  $("device-list").classList.toggle("hidden", !lookingForDevices);
  $("find-devices").textContent = lookingForDevices ? "Stop looking" : "Add a new device";
  showWaitingDevices();
};

$("add").onclick = addCabin;
load();
setInterval(load, 15000);
setInterval(showWaitingDevices, 3000);
