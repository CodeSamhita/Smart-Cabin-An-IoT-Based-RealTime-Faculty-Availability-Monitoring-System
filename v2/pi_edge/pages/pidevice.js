// Smart Cabin edge device - the device page's logic (PiDevice.dc.html).
// Reads /api/state every second (with the device details every 10 s in the Advanced view) and fills the design.
// The Advanced view also shows the live picture stream (/live.mjpg, only while it is open) and live charts of the last 2 minutes.
// For now (prototype focus) adding / deleting extra face sets and cards, and the maintenance actions, only say that
// they come later; nothing is changed on the device.

const STATUS = {
  available: { label: 'Available', text: 'In the cabin, alone', bg: '#dcf1e3', fg: '#14532d', dot: '#1e8a4c', glow: 'rgba(30,138,76,0.18)' },
  meeting: { label: 'In a meeting', text: 'In the cabin, with others', bg: '#fbecc6', fg: '#6b4a00', dot: '#d39b0b', glow: 'rgba(211,155,11,0.2)' },
  not_available: { label: 'Not available', text: 'Not in the cabin', bg: '#f8dcd5', fg: '#8a2412', dot: '#9e2a17', glow: 'rgba(158,42,23,0.18)' }
};
const LED = { green: '#1e8a4c', yellow: '#d39b0b', red: '#9e2a17', blue: '#2a5bd7', white: '#ffffff', purple: '#8a2bbf', off: '#3c4842' };
const ACTIONS = {
  restart: { title: 'Restart program', text: 'Restarts only the Smart Cabin software. Quick; nothing is lost.', btn: 'Restart program', danger: false,
             detail: 'The Smart Cabin program on this device stops and starts again. Status updates pause for a few seconds.' },
  reboot: { title: 'Reboot device', text: 'Restarts the whole Raspberry Pi. Takes about a minute.', btn: 'Reboot device', danger: false,
            detail: 'The device restarts completely. The cabin shows "Unknown" on the server until it is back, about a minute.' },
  shutdown: { title: 'Shut down', text: 'Turns the Pi off safely before you unplug it.', btn: 'Shut down', danger: false,
              detail: 'The device turns off. It only comes back when the power is unplugged and plugged in again.' },
  reset: { title: 'Factory reset', text: 'Erases the registered person, face data, RFID cards and settings on this device.', btn: 'Factory reset', danger: true, typed: true,
           detail: 'This removes everything stored for this cabin on this device and on the server. The device goes back to "Not set up" and needs the admin to authorize setup again. This cannot be undone.' }
};
const LATER = 'Not available yet in this prototype. Nothing was changed.';

let view = 'simple';
let last = null;
let detailsAt = 0;
let confirmKey = '';
let livePicture = '';           // 'on' while the live picture stream is open

// Live charts: the last 2 minutes (120 readings, one a second)
const CHARTS = [
  { key: 'headcount', label: 'People counted', unit: '', colour: '#2a4a7a', min: 0, max: 3 },
  { key: 'confidence', label: 'Confidence', unit: ' %', colour: '#1e8a4c', min: 0, max: 100 },
  { key: 'temperature', label: 'CPU temperature', unit: ' °C', colour: '#d39b0b', min: 30, max: 85 },
  { key: 'cpu_percent', label: 'CPU use', unit: ' %', colour: '#9e2a17', min: 0, max: 100 },
];
const readings = {};
CHARTS.forEach((c) => { readings[c.key] = []; });

function buildCharts() {
  $('charts').innerHTML = CHARTS.map((c) =>
    '<div style="display: flex; flex-direction: column; gap: 0.375rem; padding: 0.75rem; border-radius: 0.5rem; background: #f4f5f8">' +
    '<div style="display: flex; align-items: baseline; gap: 0.5rem"><span style="font-size: 0.75rem; color: #56625c; flex: 1">' + c.label + '</span>' +
    '<span id="now-' + c.key + '" style="font-family: \'IBM Plex Mono\', monospace; font-size: 1rem; font-weight: 600">–</span></div>' +
    '<canvas id="chart-' + c.key + '" height="64" style="width: 100%; height: 4rem; display: block"></canvas>' +
    '<span style="font-size: 0.6875rem; color: #56625c">last 2 minutes</span></div>').join('');
}

function drawChart(c) {
  const canvas = $('chart-' + c.key);
  if (!canvas || canvas.offsetWidth === 0) return;
  const w = canvas.width = canvas.offsetWidth * devicePixelRatio;
  const h = canvas.height = canvas.offsetHeight * devicePixelRatio;
  const g = canvas.getContext('2d');
  const values = readings[c.key];
  const top = Math.max(c.max, ...values.filter((v) => v !== null));
  const y = (v) => h - 4 - (Math.min(top, Math.max(c.min, v)) - c.min) / (top - c.min) * (h - 8);
  const x = (i) => (i / 119) * w;
  g.clearRect(0, 0, w, h);
  g.strokeStyle = '#dde2ea';
  g.lineWidth = 1;
  for (let k = 1; k < 4; k++) { g.beginPath(); g.moveTo(0, (h * k) / 4); g.lineTo(w, (h * k) / 4); g.stroke(); }
  const start = 120 - values.length;
  const points = values.map((v, i) => (v === null ? null : [x(start + i), y(v)])).filter(Boolean);
  if (!points.length) return;
  g.beginPath();
  points.forEach(([px, py], i) => (i ? g.lineTo(px, py) : g.moveTo(px, py)));
  g.lineTo(points[points.length - 1][0], h);
  g.lineTo(points[0][0], h);
  g.closePath();
  g.fillStyle = c.colour + '22';
  g.fill();
  g.beginPath();
  points.forEach(([px, py], i) => (i ? g.lineTo(px, py) : g.moveTo(px, py)));
  g.strokeStyle = c.colour;
  g.lineWidth = 2 * devicePixelRatio;
  g.stroke();
  const [ex, ey] = points[points.length - 1];
  g.beginPath();
  g.arc(ex, ey, 3.5 * devicePixelRatio, 0, Math.PI * 2);
  g.fillStyle = c.colour;
  g.fill();
}

function updateLive(s) {
  CHARTS.forEach((c) => {
    const v = s[c.key];
    readings[c.key].push(v === null || v === undefined ? null : Number(v));
    if (readings[c.key].length > 120) readings[c.key].shift();
    $('now-' + c.key).textContent = v === null || v === undefined ? '–' : v + c.unit;
  });
  if (view !== 'advanced') {
    if (livePicture) { $('live-img').removeAttribute('src'); livePicture = ''; }   // stop the stream: saves the Pi's CPU
    return;
  }
  CHARTS.forEach(drawChart);
  if (!livePicture) {                                        // start the continuous picture stream once
    livePicture = 'on';
    $('live-img').src = '/live.mjpg?n=' + Date.now();
  }
  $('live-caption').textContent = 'live · last count ' + s.last_picture + ' · ' + s.headcount + (s.headcount === 1 ? ' person' : ' people');
}

function initials(name) {
  return (name || '').replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
}

function drawViews() {
  $('views').innerHTML = [['simple', 'Simple'], ['advanced', 'Advanced']].map(([value, label]) => {
    const on = view === value;
    return '<button type="button" data-view="' + value + '" aria-pressed="' + on + '" style="min-height: 2.25rem; padding: 0 1rem; border: 0; border-radius: 999px; font: inherit; font-size: 0.875rem; font-weight: 600; cursor: pointer; ' +
      (on ? 'background: #1b2d4b; color: #ffffff' : 'background: transparent; color: #1b2d4b') + '">' + label + '</button>';
  }).join('');
}

function draw(s) {
  const st = STATUS[s.status] || STATUS.not_available;
  const registered = !!s.person;
  const simple = view === 'simple', advanced = !simple;
  $('dev-code').textContent = s.device;
  $('dev-location').textContent = s.location || 'Location not set yet';
  $('live-time').textContent = clock();
  $('live-dot').style.background = s.server_ok ? '#5fd38d' : '#e07a5f';

  // Simple view
  $('simple').hidden = !simple;
  $('big-ring').style.background = st.bg;
  $('big-dot').style.background = st.dot;
  $('big-dot').style.boxShadow = '0 0 0 0.5rem ' + st.glow;
  $('big-label').textContent = st.label;
  $('big-label').style.color = st.fg;
  const how = !s.in_cabin ? '' : s.face_recent && s.card_in ? 'Seen and tapped in' : s.face_recent ? 'Seen, not tapped in'
    : s.card_in ? 'Tapped in, not seen yet' : 'Someone counted in the cabin';
  $('big-text').textContent = registered ? st.text + (how ? ' · ' + how : '') : 'Nobody registered';
  $('simple-reg').hidden = !registered;
  $('simple-noreg').hidden = registered;
  $('simple-name').textContent = s.person;
  $('simple-designation').textContent = s.designation;
  $('simple-location').textContent = s.location || 'Location not set yet';

  // Advanced view: status
  $('adv-status').hidden = !advanced;
  $('adv-pill').style.background = st.bg;
  $('adv-pill').style.color = st.fg;
  $('adv-pill-dot').style.background = st.dot;
  $('adv-pill-text').textContent = st.label;
  $('door-dot').style.background = LED[s.led] || LED.off;
  $('door-text').textContent = 'Door light: ' + (s.led === 'yellow' ? 'yellow' : s.led);
  $('adv-reg').hidden = !registered;
  $('adv-noreg').hidden = registered;
  $('adv-initials').textContent = initials(s.person);
  $('adv-name').textContent = s.person;
  $('f-in').textContent = s.in_cabin ? 'yes' : 'no';
  $('f-confidence').textContent = s.confidence + ' %';
  $('f-count').textContent = s.headcount + (s.dark ? ' (room is dark)' : '');
  $('f-card').textContent = s.card_in ? 'tapped in' : 'not tapped in';
  $('f-picture').textContent = s.last_picture + ' · ' + s.picture_ms + ' ms';
  $('f-temp').textContent = s.temperature === null ? '–' : s.temperature + ' °C';
  $('server-state').style.color = s.server_ok ? '#14532d' : '#8a2412';
  $('server-dot').style.background = s.server_ok ? '#1e8a4c' : '#9e2a17';
  $('server-text').textContent = s.server_ok ? 'Server connected' : 'Server not connected: ' + s.server_message;
  $('server-address').textContent = s.server_url;

  // Advanced view: live view
  $('live-box').hidden = !advanced;

  // Advanced view: registration details
  $('reg-details').hidden = !(advanced && registered);
  if (registered) {
    $('rd-initials').textContent = initials(s.person);
    $('rd-name').textContent = s.person;
    $('rd-designation').textContent = s.designation;
    $('rd-school').textContent = s.school || '–';
    $('rd-department').textContent = s.department || '–';
    $('rd-cabin').textContent = s.location || '–';
    $('rd-id').textContent = s.person_id;
    $('rd-when').textContent = s.registered_at || '–';
    const hasFace = s.face_photos > 0, hasCard = !!s.card_tail;
    $('face-check').style.background = hasFace ? '#1e8a4c' : '#9aa5b4';
    $('face-check').textContent = hasFace ? '✓' : '–';
    $('face-title').textContent = hasFace ? 'Face registered' : 'No face registered';
    $('face-summary').textContent = hasFace ? s.face_photos + ' photos · 1 set' : 'Not registered on this device';
    $('face-list').innerHTML = hasFace ? '<li style="display: flex; align-items: center; gap: 0.5rem; min-height: 2.25rem; padding: 0.25rem 0.25rem 0.25rem 0.5rem; border-radius: 0.375rem; background: #ffffff; font-size: 0.8125rem"><span style="flex: 1; min-width: 0">Face set 1 · ' + s.face_photos + ' photos <span style="color: #56625c">· at setup</span></span></li>' : '';
    $('card-check').style.background = hasCard ? '#1e8a4c' : '#9aa5b4';
    $('card-check').textContent = hasCard ? '✓' : '–';
    $('card-title').textContent = hasCard ? 'RFID cards linked' : 'No RFID card linked';
    $('card-summary').textContent = hasCard ? '1 card' : 'Not registered on this device';
    $('card-list').innerHTML = hasCard ? '<li style="display: flex; align-items: center; gap: 0.5rem; min-height: 2.25rem; padding: 0.25rem 0.25rem 0.25rem 0.5rem; border-radius: 0.375rem; background: #ffffff; font-size: 0.8125rem"><span style="font-family: \'IBM Plex Mono\', monospace">•••• ' + esc(s.card_tail) + '</span><span style="flex: 1; min-width: 0; font-size: 0.75rem; color: #56625c">at setup</span></li>' : '';
  }

  // Setup state (only when nobody is registered)
  $('setup-ok').hidden = registered || !s.setup_allowed;
  $('setup-wait').hidden = registered || s.setup_allowed;
  $('wait-code').textContent = s.device;
  $('wait-reason').textContent = s.server_ok ? s.setup_message : 'The device cannot reach the server: ' + s.server_message;

  // Advanced view: details, parts, maintenance
  $('dev-details').hidden = !advanced;
  $('parts-box').hidden = !advanced;
  $('maintenance').hidden = !advanced;
  const NAMES = { camera: 'Camera', rfid: 'Card reader', led: 'Door light', vision: 'Vision', 'people model': 'People model',
                  'face model': 'Face model', server: 'Server link', page: 'This page', registration: 'Registration' };
  $('parts').innerHTML = Object.keys(s.parts).sort().map((n) => {
    const p = s.parts[n];
    const absent = p.present === false;
    const colour = absent ? '#9aa5b4' : p.ok ? '#1e8a4c' : '#9e2a17';
    return '<div style="display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem 0; border-bottom: 1px solid #eef1f4; font-size: 0.875rem">' +
      '<span style="width: 0.5rem; height: 0.5rem; flex: none; border-radius: 50%; background: ' + colour + '"></span>' +
      '<span style="font-weight: 600; min-width: 6rem">' + esc(NAMES[n] || n) + '</span>' +
      '<span style="font-size: 0.75rem; font-weight: 600; color: ' + (absent ? '#56625c' : p.ok ? '#14532d' : '#8a2412') + '">' + (absent ? 'Not present' : p.ok ? 'OK' : 'Problem') + '</span>' +
      '<span style="margin-left: auto; font-size: 0.75rem; color: #56625c; text-align: right">' + esc(p.message) + '</span></div>';
  }).join('');
  if (s.last_error && advanced && s.last_error !== shownError) {      // show each new error once
    shownError = s.last_error;
    showBar('Last device error: ' + s.last_error);
  }
}
let shownError = '';

function drawDetails(d) {
  $('uptime').textContent = d.uptime;
  $('meters').innerHTML = d.meters.map((m) => {
    const colour = m.pct >= 85 ? '#9e2a17' : m.pct >= 65 ? '#d39b0b' : '#1e8a4c';
    return '<div style="display: flex; flex-direction: column; gap: 0.375rem; padding: 0.75rem; border-radius: 0.5rem; background: #f4f5f8">' +
      '<div style="display: flex; align-items: baseline; gap: 0.5rem"><span style="font-size: 0.75rem; color: #56625c; flex: 1">' + esc(m.label) + '</span><span style="font-family: \'IBM Plex Mono\', monospace; font-size: 1rem; font-weight: 600">' + esc(m.value) + '</span></div>' +
      '<div role="meter" aria-label="' + esc(m.label) + '" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + m.pct + '" style="height: 0.375rem; border-radius: 999px; background: #dde2ea; overflow: hidden"><span style="display: block; height: 100%; width: ' + m.pct + '%; border-radius: 999px; background: ' + colour + '"></span></div>' +
      '<span style="font-size: 0.6875rem; color: #56625c">' + esc(m.note) + '</span></div>';
  }).join('');
  $('spec-groups').innerHTML = d.groups.map((g) =>
    '<div style="display: flex; flex-direction: column; gap: 0.375rem"><h3 style="margin: 0; font-size: 0.8125rem; font-weight: 700; color: #1b2d4b">' + esc(g.title) + '</h3>' +
    '<dl style="margin: 0; display: grid; grid-template-columns: minmax(7rem, auto) 1fr; gap: 0.375rem 1rem; font-size: 0.8125rem; padding: 0.625rem 0.75rem; border-radius: 0.5rem; border: 1px solid #eef1f4">' +
    g.rows.map((r) => '<dt style="color: #56625c">' + esc(r[0]) + '</dt><dd style="' + (r[2] ? "margin: 0; font-family: 'IBM Plex Mono', monospace; word-break: break-all" : 'margin: 0') + '">' + esc(r[1] || '–') + '</dd>').join('') +
    '</dl></div>').join('');
}

function drawActions() {
  $('actions').innerHTML = Object.keys(ACTIONS).map((k) => {
    const a = ACTIONS[k];
    return '<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 0.75rem; padding: 0.75rem 0; border-top: 1px solid #eef1f4">' +
      '<div style="flex: 1 1 14rem; min-width: 0"><div style="font-size: 0.9375rem; font-weight: 600">' + a.title + '</div><div style="font-size: 0.8125rem; color: #56625c">' + a.text + '</div></div>' +
      '<button type="button" data-action="' + k + '" style="min-height: 2.5rem; padding: 0 1rem; border-radius: 0.5rem; font: inherit; font-size: 0.875rem; font-weight: 600; cursor: pointer; ' +
      (a.danger ? 'background: #ffffff; color: #8a2412; border: 1px solid #e2b4aa' : 'background: #ffffff; color: #1b2d4b; border: 1px solid #b8c1cf') + '">' + a.btn + '</button></div>';
  }).join('');
}

function openConfirm(key) {
  confirmKey = key;
  const a = ACTIONS[key];
  $('cf-t').textContent = a.title + '?';
  $('cf-detail').textContent = a.detail;
  $('cf-typed').hidden = !a.typed;
  $('cf-code').textContent = last ? last.device : 'the device code';
  $('cf-input').value = '';
  $('cf-run').textContent = a.btn;
  updateConfirmButton();
  $('confirm').hidden = false;
}

function updateConfirmButton() {
  const a = ACTIONS[confirmKey];
  const blocked = !!(a && a.typed && $('cf-input').value.trim().toUpperCase() !== (last ? last.device.toUpperCase() : ''));
  $('cf-run').disabled = blocked;
  $('cf-run').style.background = blocked ? '#dde2ea' : (a && a.danger ? '#9e2a17' : '#1b2d4b');
  $('cf-run').style.color = blocked ? '#56625c' : '#ffffff';
  $('cf-run').style.cursor = blocked ? 'not-allowed' : 'pointer';
}

async function refresh() {
  const wantDetails = view === 'advanced' && Date.now() - detailsAt > 10000;
  const s = await api('GET', '/api/state' + (wantDetails ? '?details=1' : ''));
  if (!s.ok) {
    $('live-dot').style.background = '#e07a5f';
    $('live-time').textContent = 'no answer';
    return showBar('The device page does not answer: ' + s.message);
  }
  last = s;
  draw(s);
  updateLive(s);
  if (s.details) { detailsAt = Date.now(); drawDetails(s.details); }
}

$('live-img').addEventListener('load', () => { $('live-img').hidden = false; $('live-wait').hidden = true; });
$('live-img').addEventListener('error', () => { $('live-wait').textContent = 'No picture yet (is the camera working? see Parts).'; });

$('views').addEventListener('click', (e) => {
  const b = e.target.closest('[data-view]');
  if (!b) return;
  view = b.dataset.view;
  detailsAt = 0;
  drawViews();
  if (last) draw(last);
  refresh();
});
$('add-face').addEventListener('click', () => { $('adding-text').textContent = 'Adding more face data: ' + LATER; $('adding').hidden = false; });
$('add-card').addEventListener('click', () => { $('adding-text').textContent = 'Adding another RFID card: ' + LATER; $('adding').hidden = false; });
$('stop-adding').addEventListener('click', () => { $('adding').hidden = true; });
$('actions').addEventListener('click', (e) => { const b = e.target.closest('[data-action]'); if (b) openConfirm(b.dataset.action); });
$('cf-input').addEventListener('input', updateConfirmButton);
$('cf-cancel').addEventListener('click', () => { $('confirm').hidden = true; });
$('confirm-backdrop').addEventListener('click', () => { $('confirm').hidden = true; });
$('cf-run').addEventListener('click', () => {
  $('confirm').hidden = true;
  $('working').textContent = ACTIONS[confirmKey].title + ': ' + LATER;
  $('working').hidden = false;
  setTimeout(() => { $('working').hidden = true; }, 5000);
});

drawViews();
drawActions();
buildCharts();
refresh();
setInterval(() => everySecond(refresh), 1000);
