// Smart Cabin - Devices page logic (Devices.dc.html).
//   counts      : Devices / Online / Not reporting / Need a location; each is also a filter for the device list
//   device list : the newest device (latest first seen), or the devices of the picked count. A card in the design's two
//                 looks: with a location (details + Make setup PIN / Edit location) or without (the location box + Save)
//   faculty     : every faculty member by school, with search; a card opens their admin page (AdminPerson.dc.html?id=)
// Refreshes every second, but not while a location is being typed.

const PIN_MINUTES = 15;
const editing = {};      // device -> true while its location box is open
const typed = {};        // device -> location text typed so far
const pins = {};         // device -> {pin, expires}
const notes = {};        // device -> {ok, text}: the answer to the last button press on that card
let tile = '';           // '' = newest device, or 'all' / 'online' / 'offline' / 'nolocation'
let lastDevices = [];
let everyone = [];       // the faculty list with statuses (from /api/people-status)
let school = '';
let peopleAt = 0;

const PILL = {
  online: ['Online', '#dcf1e3', '#14532d', '#1e8a4c'],
  offline: ['Not reporting', '#f8dcd5', '#8a2412', '#9e2a17'],
  nolocation: ['No location', '#fbecc6', '#6b4a00', '#d39b0b'],
};
const STATUS = {
  available: ['Available', '#dcf1e3', '#14532d', 'background: #1e8a4c'],
  meeting: ['In a meeting', '#fbecc6', '#6b4a00', 'background: #d39b0b'],
  not_available: ['Not available', '#f8dcd5', '#8a2412', 'background: #9e2a17'],
  unknown: ['Unknown', '#e6eae8', '#3a4540', 'border: 2px solid #6b7570; box-sizing: border-box'],
  not_set_up: ['Not set up', '#ffffff', '#3a4540', 'border: 2px dashed #8a948f; box-sizing: border-box'],
};
const TILES = [['all', 'Devices', ''], ['online', 'Online', '#14532d'], ['offline', 'Not reporting', '#8a2412'], ['nolocation', 'Need a location', '#6b4a00']];
const LIST_TITLES = { '': 'Newest device', all: 'Devices', online: 'Online', offline: 'Not reporting', nolocation: 'Need a location' };

function ago(seconds) {
  if (seconds === null || seconds === undefined) return 'never';
  if (seconds < 60) return seconds + ' s ago';
  if (seconds < 3600) return Math.round(seconds / 60) + ' min ago';
  return Math.round(seconds / 3600) + ' h ago';
}

function partText(part) {
  if (!part) return '–';
  if (part.present === false) return 'not present';
  return part.ok ? 'ok' : 'problem';
}

function kindOf(d) { return !d.online ? 'offline' : (d.location ? 'online' : 'nolocation'); }

function pillHtml(kind) {
  const [label, bg, fg, dotColour] = PILL[kind];
  return '<span style="display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.25rem 0.625rem; border-radius: 999px; background: ' + bg + '; color: ' + fg + '; font-size: 0.8125rem; font-weight: 600"><span style="width: 0.5rem; height: 0.5rem; border-radius: 50%; background: ' + dotColour + '"></span>' + label + '</span>';
}

function field(label, value, mono) {
  return '<div><dt style="color: #4a5650; font-size: 0.8125rem">' + label + '</dt><dd style="margin: 0.125rem 0 0' + (mono ? "; font-family: 'IBM Plex Mono', monospace" : '') + '">' + esc(value) + '</dd></div>';
}

function cardHtml(d) {
  const kind = kindOf(d);
  const showBox = !d.location || editing[d.device];
  const button = 'min-height: 2.75rem; padding: 0 1rem; border-radius: 0.5rem; font: inherit; font-weight: 600; cursor: pointer; ';
  const dark = button + 'border: 0; background: #1b2d4b; color: #ffffff';
  const light = button + 'border: 1px solid #b8c1cf; background: #ffffff; color: #1a211e';
  let html = '<article data-device="' + esc(d.device) + '" style="background: #ffffff; border: 1px solid #dde2ea; border-radius: 0.75rem; padding: 1.375rem; display: flex; flex-direction: column; gap: 1rem">' +
    '<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem">' +
    '<span style="font-family: \'IBM Plex Mono\', monospace; font-weight: 500; font-size: 0.9375rem; padding: 0.25rem 0.625rem; border-radius: 0.375rem; background: #1b2d4b; color: #ffffff">' + esc(d.device) + '</span>' +
    '<span style="font-weight: 600; flex: 1; min-width: 0">' + esc(d.model || 'Unknown board') + '</span>' + pillHtml(kind) + '</div>';
  if (d.location && !editing[d.device]) {
    html += '<dl style="margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem 1rem; font-size: 0.875rem">' +
      field('Location', d.location) + field('Person', d.person || 'Nobody registered') +
      field('Last seen', ago(d.seconds_since_seen), true) + field('CPU temp', d.temperature === '' ? '–' : d.temperature + ' °C', true) +
      field('IP', d.ip || '–', true) + field('Camera · card reader', partText(d.parts.camera) + ' · ' + partText(d.parts.rfid)) + '</dl>' +
      '<div style="display: flex; flex-wrap: wrap; gap: 0.5rem; border-top: 1px solid #e6ebe8; padding-top: 1rem">' +
      '<button type="button" data-do="pin" style="' + dark + '">Make setup PIN</button>' +
      '<button type="button" data-do="edit" style="' + light + '">Edit location</button>' +
      (d.person_id ? '<a href="AdminPerson.dc.html?id=' + encodeURIComponent(d.person_id) + '" style="' + light + '; display: inline-flex; align-items: center; text-decoration: none">Open ' + esc(d.person) + '</a>' : '') +
      '</div>';
  }
  if (showBox) {
    html += '<label style="display: flex; flex-direction: column; gap: 0.375rem; font-size: 0.875rem; font-weight: 600; color: #3c4842">Location' +
      '<span style="display: flex; gap: 0.5rem">' +
      '<input type="text" class="loc" value="' + esc(typed[d.device] ?? d.location) + '" placeholder="e.g. Block [x], cabin [no.]" style="flex: 1; min-width: 0; min-height: 2.75rem; padding: 0 0.75rem; border: 1px solid #b8c1cf; border-radius: 0.5rem; font: inherit; font-weight: 400; font-size: 0.9375rem">' +
      '<button type="button" data-do="save" style="' + dark + '">Save</button></span></label>';
  }
  const pin = pins[d.device];
  if (pin && pin.expires > Date.now()) {
    html += '<div style="display: flex; flex-direction: column; gap: 0.375rem; padding: 0.875rem 1rem; border-radius: 0.625rem; background: #f4f5f8; border: 1px dashed #b8c1cf">' +
      '<span style="font-size: 0.8125rem; color: #4a5650">Setup PIN · give this to the person at the cabin</span>' +
      '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 1.75rem; font-weight: 500; letter-spacing: 0.2em">' + esc(pin.pin) + '</span>' +
      '<span style="font-size: 0.8125rem; color: #4a5650">Expires ' + new Date(pin.expires).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}) + '</span></div>';
  }
  const note = notes[d.device];
  if (note) {
    html += '<span style="font-size: 0.8125rem; color: ' + (note.ok ? '#14532d' : '#8a2412') + '">' + esc(note.text) + '</span>';
  }
  return html + '</article>';
}

const EVENT_NAMES = { 'status': 'Status changed', 'new device': 'First seen', 'registered': 'Person registered',
                      'unregistered': 'Person removed', 'moved': 'Person moved', 'location': 'Location set',
                      'credentials': 'Face / cards changed', 'faculty': 'Faculty login', 'timetable': 'Timetable',
                      'setup pin': 'Setup PIN made', 'device key': 'Device key', 'refused': 'Refused', 'admin': 'Admin' };

function drawTiles(list) {
  const count = { all: list.length, online: list.filter((d) => kindOf(d) === 'online').length,
                  offline: list.filter((d) => !d.online).length, nolocation: list.filter((d) => !d.location).length };
  $('tiles').innerHTML = TILES.map(([key, label, colour]) => {
    const on = tile === key;
    return '<button type="button" data-tile="' + key + '" aria-pressed="' + on + '" style="display: block; text-align: left; font: inherit; color: inherit; cursor: pointer; border-radius: 0.75rem; padding: 1rem 1.125rem; ' +
      (on ? 'background: #e6ecf5; border: 2px solid #1b2d4b; margin: 0' : 'background: #ffffff; border: 1px solid #dde2ea; margin: 1px') + '">' +
      '<span style="display: block; font-size: 0.8125rem; color: #4a5650">' + label + '</span>' +
      '<span style="display: block; font-size: 1.625rem; font-weight: 700' + (colour ? '; color: ' + colour : '') + '">' + count[key] + '</span></button>';
  }).join('');
}

function drawDevices(list) {
  let shown;
  if (!tile) {
    const newest = list.slice().sort((a, b) => String(b.first_seen).localeCompare(String(a.first_seen)))[0];
    shown = newest ? [newest] : [];
    $('nd-added').textContent = newest ? 'added ' + newest.first_seen : '';
  } else {
    shown = list.filter((d) => tile === 'all' || (tile === 'online' && kindOf(d) === 'online') || (tile === 'offline' && !d.online) || (tile === 'nolocation' && !d.location));
    $('nd-added').textContent = '';
  }
  $('nd').textContent = LIST_TITLES[tile];
  $('device-list').innerHTML = shown.length ? shown.map(cardHtml).join('')
    : '<p style="margin: 0; padding: 1.25rem; text-align: center; background: #ffffff; border: 1px dashed #b8c1cf; border-radius: 0.75rem; color: #4a5650">' +
      (list.length ? 'No device here.' : 'No device yet. Start the edge app on a Pi and it appears here by itself.') + '</p>';
}

// ---------- faculty ----------
const shortSchool = (s) => (s || '').replace(/^Presidency School of /, '');
const initials = (n) => n.replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');

function drawPeople() {
  const q = $('q').value.trim().toLowerCase();
  const deviceOf = {};
  lastDevices.forEach((d) => { if (d.person_id) deviceOf[d.person_id] = d.device; });
  const schools = Array.from(new Set(everyone.map((p) => p.school).filter(Boolean))).sort((a, b) => shortSchool(a).localeCompare(shortSchool(b)));
  const showSchools = !school && !q;
  $('fac').textContent = school || 'Faculty';
  $('q').placeholder = school ? 'Search a name in this school' : 'Search a name in all schools';
  $('school-grid').hidden = !showSchools;
  $('results').hidden = showSchools;
  if (showSchools) {
    $('school-grid').innerHTML = schools.map((s) => {
      const n = everyone.filter((p) => p.school === s).length;
      return '<button type="button" data-school="' + esc(s) + '" style="display: flex; flex-direction: column; align-items: flex-start; gap: 0.375rem; min-height: 8rem; padding: 1.25rem; text-align: left; font: inherit; color: #1b2d4b; border: 1px solid #cfd9e8; border-radius: 0.75rem; cursor: pointer; box-shadow: 0 0.125rem 0.5rem rgba(27,45,75,0.08); background: #e6ecf5">' +
        '<span style="font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; color: #3d5275; font-weight: 600">Presidency School of</span>' +
        '<span style="flex: 1; font-size: 1.125rem; font-weight: 700; line-height: 1.3">' + esc(shortSchool(s)) + '</span>' +
        '<span style="font-size: 0.875rem; font-weight: 600; color: #2a4a7a">' + n + (n === 1 ? ' faculty member' : ' faculty') + ' →</span></button>';
    }).join('');
    return;
  }
  const matched = everyone.filter((p) => (!q || p.name.toLowerCase().includes(q)) && (!school || p.school === school));
  $('count-text').textContent = matched.length + ' of ' + everyone.length + ' faculty' + (matched.length > 120 ? ' (first 120; type more of the name)' : '');
  $('empty').hidden = matched.length !== 0;
  $('people-grid').innerHTML = matched.slice(0, 120).map((p) => {
    const s = STATUS[p.status] ? p.status : 'unknown';
    const look = STATUS[s];
    const device = deviceOf[p.id];
    return '<a href="AdminPerson.dc.html?id=' + encodeURIComponent(p.id) + '" style="display: flex; flex-direction: column; gap: 0.75rem; color: inherit; text-decoration: none; padding: 1rem; border-radius: 0.75rem; background: #ffffff; box-shadow: 0 0.125rem 0.5rem rgba(27,45,75,0.08); border: 1px solid #dde2ea">' +
      '<span style="display: flex; align-items: center; gap: 0.75rem">' +
      '<span style="width: 2.5rem; height: 2.5rem; flex: none; border-radius: 50%; background: #e6ecf5; color: #1b2d4b; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.875rem">' + esc(initials(p.name)) + '</span>' +
      '<span style="display: flex; flex-direction: column; min-width: 0"><span style="font-weight: 600; font-size: 0.9375rem">' + esc(p.name) + '</span>' +
      '<span style="font-size: 0.8125rem; color: #56625c">' + esc(p.designation) + '</span><span style="font-size: 0.75rem; color: #56625c">' + esc(shortSchool(p.school)) + '</span></span></span>' +
      '<span style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem">' +
      '<span style="display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.25rem 0.625rem; border-radius: 999px; font-size: 0.8125rem; font-weight: 600; background: ' + look[1] + '; color: ' + look[2] + (s === 'not_set_up' ? '; border: 1px solid #c6d0ca' : '') + '"><span style="width: 0.5625rem; height: 0.5625rem; border-radius: 50%; ' + look[3] + '"></span>' + look[0] + '</span>' +
      (device ? '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 0.75rem; padding: 0.125rem 0.5rem; border-radius: 0.375rem; background: #1b2d4b; color: #ffffff">' + esc(device) + '</span>' : '') +
      '</span></a>';
  }).join('');
}

async function loadPeople() {
  const data = await api('GET', '/api/people-status');
  if (!data.ok) return showBar('Could not load the faculty list: ' + data.message);
  everyone = data.people;
  peopleAt = Date.now();
  if (document.activeElement !== $('q')) drawPeople();
}

async function refresh(force) {
  if (!force && document.activeElement && document.activeElement.classList.contains('loc')) return;
  const data = await api('GET', '/api/admin/devices');
  if (!data.ok) return showBar(data.message);
  lastDevices = data.devices;
  drawTiles(lastDevices);
  drawDevices(lastDevices);
  $('updated').textContent = clock();
  if (Date.now() - peopleAt > 10000) loadPeople();
  const log = await api('GET', '/api/admin/log');
  if (!log.ok) return showBar(log.message);
  const cell = 'padding: 0.625rem 0.75rem; border-bottom: 1px solid #eef1f4';
  const mono = cell + "; font-family: 'IBM Plex Mono', monospace";
  $('events').innerHTML = log.events.slice().reverse().map((e) =>
    '<tr><td style="' + mono + '">' + esc(e.time) + '</td><td style="' + mono + '">' + esc(e.device || '–') + '</td><td style="' + cell + '">' +
    esc(EVENT_NAMES[e.kind] || e.kind) + '</td><td style="' + cell + '; color: #4a5650">' + esc(e.message) + '</td></tr>').join('');
  $('server-log').textContent = log.lines.join('') || 'The log is empty.';
  $('server-log').scrollTop = $('server-log').scrollHeight;
}

$('tiles').addEventListener('click', (e) => {
  const b = e.target.closest('[data-tile]');
  if (!b) return;
  tile = tile === b.dataset.tile ? '' : b.dataset.tile;
  drawTiles(lastDevices);
  drawDevices(lastDevices);
});

$('device-list').addEventListener('input', (e) => {
  if (e.target.classList.contains('loc')) typed[e.target.closest('article').dataset.device] = e.target.value;
});

$('device-list').addEventListener('click', (e) => {
  const button = e.target.closest('button[data-do]');
  if (!button) return;
  const card = button.closest('article');
  const device = card.dataset.device;
  const action = button.dataset.do;
  if (action === 'edit') {
    editing[device] = true;
    delete notes[device];
    return refresh(true);
  }
  press(button, async () => {
    let r;
    if (action === 'save') {
      r = await api('POST', '/api/admin/location', { device, location: card.querySelector('.loc').value });
      if (r.ok) { delete editing[device]; delete typed[device]; }
    } else if (action === 'pin') {
      r = await api('POST', '/api/admin/pin', { device });
      if (r.ok) pins[device] = { pin: r.pin, expires: Date.now() + PIN_MINUTES * 60000 };
    }
    notes[device] = { ok: r.ok, text: r.ok && action === 'pin' ? 'PIN made. It works once.' : r.message };
    await refresh(true);
  });
});

$('school-grid').addEventListener('click', (e) => {
  const b = e.target.closest('[data-school]');
  if (b) { school = b.dataset.school; $('q').value = ''; drawPeople(); }
});
$('back').addEventListener('click', () => { school = ''; $('q').value = ''; drawPeople(); });
$('q').addEventListener('input', drawPeople);

$('refresh').addEventListener('click', (e) => press(e.currentTarget, () => refresh(true)));

$('logout').addEventListener('click', async (e) => {
  e.preventDefault();
  await api('POST', '/api/logout');
  location.href = 'Login.dc.html';
});

api('GET', '/api/admin/me').then((me) => {
  if (!me.ok) return showBar(me.message);
  if (!me.logged_in) return location.href = 'Login.dc.html';
  $('admin-name').textContent = me.username;
  refresh(true);
  setInterval(() => everySecond(() => refresh(false)), 1000);
});
