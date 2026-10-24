// Smart Cabin - helpers used by every page: talking to the server, safe text, sliding sections,
// pop-up messages and the "notify me" bell.

// ---------- Talking to the server ----------
async function api(method, url, body) {
  // Calls the server and returns the JSON answer. Shows the server's message if it says no.
  const options = { method: method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  let data = {};
  try { data = await response.json(); } catch (e) {}
  if (!response.ok) {
    let message = data.detail || ("Error " + response.status);
    if (Array.isArray(message)) {                       // FastAPI's "this field is wrong" list
      message = message.map(m => (m.loc || []).slice(-1)[0] + ": " + m.msg).join(", ");
    }
    if (response.status === 401 && !url.startsWith("/api/login")) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname);
    }
    throw new Error(message);
  }
  return data;
}

function esc(text) {
  // Makes text safe to put inside HTML
  return String(text === null || text === undefined ? "" : text)
    .replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function $(id) { return document.getElementById(id); }

// ---------- Pop-up message ----------
let toastTimer = null;
function toast(text, kind) {
  let box = $("toast");
  if (!box) {
    box = document.createElement("div");
    box.id = "toast";
    document.body.appendChild(box);
  }
  box.className = "toast" + (kind ? " " + kind : "");
  box.textContent = text;
  box.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.add("hidden"), kind === "alert" ? 10000 : 3500);
}

// ---------- Sections: side by side on a laptop, slide on a phone ----------
function setupPanels() {
  // Builds the tab bar from each <section class="panel" data-title="...">
  const panels = document.querySelector(".panels");
  const tabs = document.querySelector(".tabs");
  if (!panels || !tabs) return;
  const sections = Array.from(panels.querySelectorAll(".panel:not(.hidden)"));
  tabs.innerHTML = "<button class='arrow' data-go='-1'>&#8249;</button><div class='tab-list'></div>" +
                   "<button class='arrow' data-go='1'>&#8250;</button>";
  const list = tabs.querySelector(".tab-list");
  sections.forEach((s, i) => {
    const b = document.createElement("button");
    b.className = "tab";
    b.textContent = s.dataset.title;
    b.onclick = () => show(i);
    list.appendChild(b);
  });

  // Where each section starts inside the sliding strip (includes the gap between sections)
  const startOf = s => s.offsetLeft - sections[0].offsetLeft;
  function current() {
    let best = 0;
    sections.forEach((s, i) => {
      if (Math.abs(startOf(s) - panels.scrollLeft) < Math.abs(startOf(sections[best]) - panels.scrollLeft)) best = i;
    });
    return best;
  }
  function show(i) {
    i = Math.max(0, Math.min(sections.length - 1, i));
    panels.scrollTo({ left: startOf(sections[i]), behavior: "smooth" });
    mark(i);
  }
  function mark(i) {
    list.querySelectorAll(".tab").forEach((t, j) => t.classList.toggle("active", i === j));
    const active = list.children[i];
    if (active) active.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  tabs.querySelectorAll(".arrow").forEach(a => a.onclick = () => show(current() + Number(a.dataset.go)));
  let wait = null;
  panels.onscroll = () => { clearTimeout(wait); wait = setTimeout(() => mark(current()), 80); };
  mark(0);
}

// ---------- Logging out ----------
async function logout() {
  await api("POST", "/api/logout");
  location.href = "/";
}

// ---------- "Notify me when available" bell ----------
let bellOpen = false;

function beep() {
  // A short two-note sound, made by the browser (no sound file needed)
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [660, 880].forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = f; o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.2, ctx.currentTime + i * 0.2);
      o.start(ctx.currentTime + i * 0.2); o.stop(ctx.currentTime + i * 0.2 + 0.18);
    });
  } catch (e) {}
}

function systemNotification(text) {
  // Works where the browser allows it (e.g. http://localhost, or https). Otherwise the banner is enough.
  try {
    if ("Notification" in window && Notification.permission === "granted") new Notification("Smart Cabin", { body: text });
  } catch (e) {}
}

function askNotificationPermission() {
  try {
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
  } catch (e) {}
}

async function checkWatches() {
  const bell = $("bell");
  if (!bell) return;
  let data;
  try { data = await api("GET", "/api/watches"); } catch (e) { return; }
  bell.querySelector(".count").textContent = data.watching.length || "";
  bell.querySelector(".count").classList.toggle("hidden", !data.watching.length);
  $("bell-list").innerHTML = data.watching.length
    ? data.watching.map(w => "<div class='row'><a href='/person/" + w.target_id + "'>" + esc(w.name) + "</a>" +
        "<button class='plain small-btn' onclick='stopWatch(" + w.target_id + ")'>Stop</button></div>").join("")
    : "<div class='small'>Open a person and press <b>Notify me when available</b>.</div>";
  if (data.alerts.length) {
    const names = data.alerts.map(a => a.name).join(", ");
    toast("✔ " + names + (data.alerts.length > 1 ? " are" : " is") + " available now", "alert");
    beep();
    systemNotification(names + " is available now");
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
    await api("POST", "/api/watches/shown");
  }
}

async function stopWatch(id) {
  await api("DELETE", "/api/watches/" + id);
  checkWatches();
  if (typeof onWatchChanged === "function") onWatchChanged();
}

function toggleBell() {
  bellOpen = !bellOpen;
  $("bell-menu").classList.toggle("hidden", !bellOpen);
}

document.addEventListener("DOMContentLoaded", () => {
  setupPanels();
  if ($("bell")) {
    checkWatches();
    setInterval(checkWatches, 15000);
  }
});
