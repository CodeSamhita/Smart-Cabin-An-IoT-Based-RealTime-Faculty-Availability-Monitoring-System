// Smart Cabin edge device - registration page logic (PiRegister.dc.html).
// 1 your name -> 2 your face (10 photos, live preview) -> 3 RFID card -> 4 saved with the server.
// The device runs each step; this page asks it every second how far it is. The registration's secret session key
// is kept in this browser tab only.

let token = '';
try { token = sessionStorage.getItem('registration') || ''; } catch (e) {}
let people = [];
let step = 1;
let viewing = null;
let picked = null;
let reg = null;            // the device's view of this registration (photos, card, time left)
let location_ = '';
let previewTimer = null;

const call = (method, url, body) => api(method, url, body, token ? { 'X-Session': token } : {});

function initials(name) {
  return (name || '').replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
}
const shortSchool = (s) => (s || '').replace(/^Presidency School of /, '');
const sortKey = (n) => n.replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').toLowerCase();

function setToken(value) {
  token = value || '';
  try { token ? sessionStorage.setItem('registration', token) : sessionStorage.removeItem('registration'); } catch (e) {}
}

function serverBadge(kind, text) {
  const look = { loading: ['#fbecc6', '#6b4a00', '#d39b0b'], ok: ['#dcf1e3', '#14532d', '#1e8a4c'], failed: ['#f8dcd5', '#8a2412', '#9e2a17'] }[kind];
  $('server-badge').style.background = look[0];
  $('server-badge').style.color = look[1];
  $('server-dot').style.background = look[2];
  $('server-text').textContent = text;
}

// ---------- the steps ----------
function drawSteps() {
  $('steps').innerHTML = ['Your name', 'Your face', 'RFID card', 'Send'].map((label, i) => {
    const n = i + 1, done = n < step, cur = n === step;
    return '<li style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.625rem; border-radius: 0.5rem; font-size: 0.8125rem; font-weight: 600; ' +
      (cur ? 'background: #1b2d4b; color: #ffffff' : done ? 'background: #e6ecf5; color: #1b2d4b' : 'background: #ffffff; color: #56625c; border: 1px solid #dde2ea') + '">' +
      '<span style="width: 1.5rem; height: 1.5rem; flex: none; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; ' +
      (cur ? 'background: #ffffff; color: #1b2d4b' : done ? 'background: #1b2d4b; color: #ffffff' : 'background: #eef1f4; color: #56625c') + '">' + (done ? '✓' : n) + '</span>' +
      '<span style="min-width: 0">' + label + '</span></li>';
  }).join('');
  $('step-name').hidden = step !== 1;
  $('step-face').hidden = step !== 2;
  $('step-card').hidden = step !== 3;
  $('step-save').hidden = step !== 4;
}

function goTo(n) {
  step = n;
  drawSteps();
  drawPicked();
}

function drawPicked() {
  document.querySelectorAll('.pick-initials').forEach((e) => { e.textContent = picked ? initials(picked.name) : ''; });
  document.querySelectorAll('.pick-name').forEach((e) => { e.textContent = picked ? picked.name : ''; });
  document.querySelectorAll('.location-text').forEach((e) => { e.textContent = 'Cabin ' + (location_ || '(not set yet)'); });
  const next = $('to-face');
  next.disabled = !picked;
  next.style.cssText = 'min-height: 2.75rem; padding: 0 1.125rem; border: 0; border-radius: 0.5rem; font: inherit; font-weight: 600; ' +
    (picked ? 'background: #1b2d4b; color: #ffffff; cursor: pointer' : 'background: #dde2ea; color: #56625c; cursor: not-allowed');
}

// ---------- step 1: your name ----------
function drawPeople() {
  const q = $('q').value;
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const typed = q.trim().length >= 2;
  const matches = typed ? people.filter((p) => words.every((w) => p.name.toLowerCase().includes(w))).slice(0, 40) : [];
  $('hint').hidden = typed && matches.length > 0;
  $('hint').textContent = !typed ? 'Type at least 2 letters of your name.' : 'Nobody found. Check the spelling.';
  $('people').innerHTML = matches.map((p) => {
    const on = picked && p.id === picked.id;
    return '<button type="button" data-id="' + esc(p.id) + '" aria-pressed="' + on + '" style="display: flex; align-items: center; gap: 0.75rem; padding: 0.625rem 0.75rem; text-align: left; font: inherit; color: inherit; cursor: pointer; border-radius: 0.5rem; ' +
      (on ? 'background: #e6ecf5; border: 2px solid #1b2d4b; margin: 0' : 'background: #ffffff; border: 1px solid #dde2ea; margin: 1px') + '">' +
      '<span style="width: 2.25rem; height: 2.25rem; flex: none; border-radius: 50%; background: #e6ecf5; color: #1b2d4b; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8125rem">' + esc(initials(p.name)) + '</span>' +
      '<span style="display: flex; flex-direction: column; min-width: 0; flex: 1"><span style="font-weight: 600; font-size: 0.9375rem">' + esc(p.name) + '</span><span style="font-size: 0.75rem; color: #56625c">' + esc(p.designation) + ' · ' + esc(shortSchool(p.school)) + '</span></span></button>';
  }).join('');
}

function openView(p) {
  viewing = p;
  $('pv-initials').textContent = initials(p.name);
  $('pv-name').textContent = p.name;
  $('pv-designation').textContent = p.designation;
  $('pv-school').textContent = p.school || '—';
  $('pv-department').textContent = p.department || '—';
  $('pv-role').textContent = p.role || '—';
  $('pv-id').textContent = p.id;
  $('view').hidden = false;
}

// ---------- the device's progress ----------
async function poll() {
  const s = await call('GET', '/api/state');
  if (!s.ok) return;
  $('dev-code').textContent = s.device;
  $('dev-location').textContent = s.location || 'Location not set yet';
  location_ = s.location;
  reg = s.registration;
  if (!reg) {
    if (token && step < 4) {                               // the device ended it (timed out)
      setToken('');
      showBar('The registration ended on the device (it stops after 5 minutes). Go back and start again.');
    }
    $('time-left').textContent = step === 4 ? 'done' : 'not started';
    return;
  }
  $('time-left').textContent = Math.floor(reg.seconds_left / 60) + ':' + String(reg.seconds_left % 60).padStart(2, '0') + ' left';
  drawFace();
  drawCard();
}

function drawFace() {
  if (!reg) return;
  const n = reg.face_photos || 0;
  $('photo-dots').innerHTML = Array.from({ length: 10 }, (_, i) => '<span style="height: 0.5rem; border-radius: 999px; background: ' + (i < n ? '#1e8a4c' : '#dde2ea') + '"></span>').join('');
  $('photo-dots').setAttribute('aria-valuenow', n);
  $('photo-count').textContent = n + ' / 10';
  const done = n >= 10 && !reg.face_busy;
  $('face-text').textContent = reg.face_message || (done ? 'All 10 photos taken.' : 'Press Start camera when you are ready.');
  $('to-card').hidden = !done;
  $('start-face').hidden = done;
  $('start-face').disabled = reg.face_busy;
  $('start-face').textContent = reg.face_busy ? 'Taking photos…' : (n ? 'Try again' : 'Start camera');
  if (reg.face_busy && !previewTimer) {
    previewTimer = setInterval(() => { $('preview').src = '/preview.jpg?t=' + encodeURIComponent(token) + '&n=' + Date.now(); }, 1000);
    $('preview').hidden = false;
    $('preview-text').hidden = true;
  }
  if (!reg.face_busy && previewTimer) {
    clearInterval(previewTimer);
    previewTimer = null;
    $('preview').hidden = true;
    $('preview-text').hidden = false;
  }
}

function drawCard() {
  if (!reg) return;
  const state = reg.card_id ? 'done' : reg.card_waiting ? 'waiting' : 'idle';
  const look = {
    idle: ['#f4f5f8', '#3d5275', '2px dashed #b8c1cf', 'Ready for your card', reg.card_message && !reg.card_waiting ? reg.card_message : 'Press "I am ready", then hold your ID card flat on the reader.'],
    waiting: ['#e6ecf5', '#1b2d4b', '2px solid #2a4a7a', 'Waiting for your card…', 'Hold your card on the reader until it beeps.'],
    done: ['#dcf1e3', '#14532d', '2px solid #1e8a4c', 'Card linked', 'Card id ' + reg.card_id],
  }[state];
  $('card-box').style.background = look[0];
  $('card-box').style.color = look[1];
  $('card-box').style.border = look[2];
  $('card-title').textContent = look[3];
  $('card-text').textContent = look[4];
  $('save').hidden = state !== 'done';
  $('start-card').hidden = state === 'done';
  $('start-card').disabled = state === 'waiting';
  $('start-card').textContent = state === 'waiting' ? 'Waiting…' : 'I am ready';
}

// ---------- step 4: save ----------
const SAVE_STEPS = [
  ['Name sent', 'Server checks the name against its staff list'],
  ['Face data saved', '10 photos turned into face data on this device; only the data is sent'],
  ['RFID card linked', 'Server makes sure no one else uses this card'],
  ['Server confirmed', 'This cabin is now linked to this faculty member'],
];

function drawSaveSteps(stage) {
  $('save-steps').innerHTML = SAVE_STEPS.map(([label, note], i) => {
    const done = i < stage, cur = i === stage;
    return '<li style="display: flex; align-items: center; gap: 0.75rem; padding: 0.625rem 0; border-bottom: 1px solid #eef1f4">' +
      '<span style="width: 1.75rem; height: 1.75rem; flex: none; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8125rem; font-weight: 700; ' +
      (done ? 'background: #1e8a4c; color: #ffffff' : cur ? 'background: #e6ecf5; color: #1b2d4b; border: 2px solid #2a4a7a; box-sizing: border-box' : 'background: #eef1f4; color: #56625c') + '">' + (done ? '✓' : cur ? '…' : i + 1) + '</span>' +
      '<span style="flex: 1; min-width: 0; display: flex; flex-direction: column"><span style="font-size: 0.9375rem; font-weight: 600; color: ' + (done || cur ? '#1a211e' : '#56625c') + '">' + label + '</span><span style="font-size: 0.75rem; color: #56625c">' + note + '</span></span></li>';
  }).join('');
}

// The badge and the closing message for each answer: registered at once, waiting for the admin, or kept on the device
const BADGES = { draft: ['Not sent', '#eef1f4', '#3a4540'], sending: ['Sending…', '#fbecc6', '#6b4a00'],
                 failed: ['Not sent', '#f8dcd5', '#8a2412'], registered: ['Registered', '#dcf1e3', '#14532d'],
                 pending: ['Waiting for approval', '#fbecc6', '#6b4a00'], waiting: ['Saved on this device', '#e6ecf5', '#1b2d4b'] };
const DONE = { registered: ['Registration complete', 'The server has saved it. This cabin now shows your status live.'],
               pending: ['Request sent', 'The admin approves it. This cabin shows your status from then on.'],
               waiting: ['Saved on this device', 'It is sent as soon as the server can be reached; the admin approves it then.'] };

function badge(kind) {
  const [text, bg, fg] = BADGES[kind];
  $('save-badge').textContent = text;
  $('save-badge').style.cssText = 'font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.625rem; border-radius: 999px; background: ' + bg + '; color: ' + fg;
}

function save() {
  // From the card step: the confirm form (faculty login, cabin); nothing is sent yet
  goTo(4);
  $('save-summary').textContent = (reg ? reg.face_photos : 0) + ' face photos · Card ' + (reg && reg.card_id ? reg.card_id : '–');
  $('save-error').hidden = true;
  $('saved').hidden = true;
  $('save-steps').hidden = true;
  $('confirm').hidden = false;
  if (!$('cabin').value) $('cabin').value = location_ || '';
  $('cabin').readOnly = !!location_;
  badge('draft');
}

async function send() {
  $('save-error').hidden = true;
  badge('sending');
  const r = await call('POST', '/api/register/save', { login: $('login').value, password: $('password').value, cabin: $('cabin').value });
  $('password').value = '';
  if (!r.ok) {
    badge('failed');
    $('save-error').textContent = r.message;
    $('save-error').hidden = false;
    return;
  }
  setToken('');
  $('confirm').hidden = true;
  if (r.state === 'registered') {                          // the server has confirmed: show each part as done
    $('save-steps').hidden = false;
    for (let stage = 1; stage <= 4; stage++) {
      drawSaveSteps(stage);
      await new Promise((done) => setTimeout(done, 350));
    }
  }
  badge(r.state);
  $('saved-title').textContent = DONE[r.state][0];
  $('saved-text').textContent = r.state === 'pending' ? r.message : DONE[r.state][1];
  $('saved').hidden = false;
}

// ---------- start ----------
async function start() {
  drawSteps();
  drawPicked();
  let list = token ? await call('GET', '/api/register/people') : { ok: false };
  if (!list.ok) {                                          // no registration yet, or an old one that ended
    setToken('');
    const r = await api('POST', '/api/register/start');
    if (!r.ok) { serverBadge('failed', 'Not allowed'); return showBar(r.message); }
    setToken(r.token);
    list = await call('GET', '/api/register/people');
  }
  if (!list.ok) { serverBadge('failed', 'Server not reachable'); return showBar(list.message); }
  people = list.people.sort((a, b) => sortKey(a.name).localeCompare(sortKey(b.name)));
  serverBadge('ok', people.length + ' names from server');
  drawPeople();
  poll();
  setInterval(() => everySecond(poll), 1000);
}

$('q').addEventListener('input', drawPeople);
$('people').addEventListener('click', (e) => {
  const b = e.target.closest('[data-id]');
  if (b) openView(people.find((p) => p.id === b.dataset.id));
});
$('view-close').addEventListener('click', () => { $('view').hidden = true; });
$('view-backdrop').addEventListener('click', () => { $('view').hidden = true; });
$('not-me').addEventListener('click', () => { $('view').hidden = true; });
$('yes-me').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await call('POST', '/api/register/pick', { person_id: viewing.id });
  if (!r.ok) return showBar(r.message);
  picked = viewing;
  $('view').hidden = true;
  drawPeople();
  goTo(2);
}));
$('to-face').addEventListener('click', () => { if (picked) goTo(2); });
$('to-name').addEventListener('click', () => goTo(1));
$('to-card').addEventListener('click', () => goTo(3));
$('back-face').addEventListener('click', () => goTo(2));
$('start-face').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await call('POST', '/api/register/face');
  if (!r.ok) showBar(r.message);
  poll();
}));
$('start-card').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await call('POST', '/api/register/card');
  if (!r.ok) showBar(r.message);
  poll();
}));
$('save').addEventListener('click', save);
$('back-card').addEventListener('click', () => goTo(3));
$('confirm').addEventListener('submit', (e) => { e.preventDefault(); press($('send'), send); });
$('cancel').addEventListener('click', async (e) => {
  e.preventDefault();
  if (token) await call('POST', '/api/register/cancel');
  setToken('');
  location.href = 'PiDevice.dc.html';
});

start();
