// Smart Cabin - helpers shared by the pages (the design itself is in the .dc.html files).
//   api(method, url, body) : one request to the server with a 10 s time limit. Never throws: always {ok, message, ...}
//   showBar(text)          : a red bar at the top with an error in words (only appears when something goes wrong)
//   press(button, work)    : a button shows "Working…" while it waits, then its own label again
//   any JavaScript error on the page also shows in the red bar
//   a page opened as a plain file (double-clicked) shows the design, with a note that live data needs the server

const TIME_LIMIT_MS = 10000;
const OPENED_AS_FILE = location.protocol === "file:";

function $(id) { return document.getElementById(id); }

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}

function showBar(text, kind) {
  let bar = $("error-bar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "error-bar";
    bar.title = "Click to close";
    bar.addEventListener("click", () => bar.remove());
    document.body.prepend(bar);
  }
  const note = kind === "note";
  bar.style.cssText = "position: sticky; top: 0; z-index: 100; padding: 0.625rem 1.5rem; cursor: pointer; font-family: " +
    "'IBM Plex Sans', system-ui, sans-serif; font-size: 0.875rem; " +
    (note ? "background: #fbecc6; color: #6b4a00" : "background: #8a2412; color: #ffffff");
  bar.textContent = text + "  (click to close)";
}

window.addEventListener("error", e => showBar("Page error: " + e.message + " at " + String(e.filename || "").split("/").pop() + ":" + e.lineno));
window.addEventListener("unhandledrejection", e => showBar("Page error: " + (e.reason && e.reason.message ? e.reason.message : e.reason)));
if (OPENED_AS_FILE) {
  document.addEventListener("DOMContentLoaded", () => showBar("Opened as a file, so there is no live data. Start the server " +
    "(python main.py) and use the page it opens.", "note"));
}

async function api(method, url, body) {
  if (OPENED_AS_FILE) return {ok: false, message: "No live data (opened as a file)."};
  const control = new AbortController();
  const timer = setTimeout(() => control.abort(), TIME_LIMIT_MS);
  try {
    const answer = await fetch(url, {
      method, credentials: "same-origin", signal: control.signal,
      headers: body ? {"Content-Type": "application/json"} : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    let data;
    try { data = await answer.json(); }
    catch (e) { data = {ok: false, message: "The server answered with something that is not JSON (HTTP " + answer.status + ")."}; }
    if (data.ok === undefined) data.ok = answer.ok;
    if (data.login && !location.pathname.includes("Login")) location.href = "Login.dc.html";
    return data;
  } catch (e) {
    return {ok: false, message: e.name === "AbortError"
      ? "No answer from the server in 10 s. Is it running, and is this device on the same network?"
      : "Could not reach the server (" + e.message + "). Is it running?"};
  } finally {
    clearTimeout(timer);
  }
}

async function press(button, work) {
  const label = button.innerHTML;
  button.disabled = true;
  button.textContent = "Working…";
  try {
    return await work();
  } catch (e) {
    showBar("Page error: " + e.message);
  } finally {
    button.disabled = false;
    button.innerHTML = label;
  }
}

// Runs work() unless the previous run is still waiting for the server, so slow answers never pile up
let running = false;
async function everySecond(work) {
  if (running) return;
  running = true;
  try { await work(); } finally { running = false; }
}

function clock() {
  return new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
}
