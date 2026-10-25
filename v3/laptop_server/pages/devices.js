// Smart Cabin - Devices page logic (Devices.dc.html). Draws one card per device in the design's two looks:
//   with a location   : details (location, person, last seen, CPU temp, IP, camera · card reader) + Make setup PIN / Edit location
//   without a location (or editing it): the location box + Save
// A setup PIN, once made, shows in the card's PIN box. Refreshes every 10 s, but not while a location is being typed.

const PIN_MINUTES = 15;
const editing = {};      // device -> true while its location box is open
const typed = {};        // device -> location text typed so far
const pins = {};         // device -> {pin, expires}
const notes = {};        // device -> {ok, text}: the answer to the last button press on that card

const PILL = {
  online: ['Online', '#dcf1e3', '#14532d', '#1e8a4c'],
  offline: ['Not reporting', '#f8dcd5', '#8a2412', '#9e2a17'],
  nolocation: ['No location', '#fbecc6', '#6b4a00', '#d39b0b'],
};

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

function pillHtml(kind) {
  const [label, bg, fg, dotColour] = PILL[kind];
  return '<span style="display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.25rem 0.625rem; border-radius: 999px; background: ' + bg + '; color: ' + fg + '; font-size: 0.8125rem; font-weight: 600"><span style="width: 0.5rem; height: 0.5rem; border-radius: 50%; background: ' + dotColour + '"></span>' + label + '</span>';
}

function field(label, value, mono) {
  return '<div><dt style="color: #4a5650; font-size: 0.8125rem">' + label + '</dt><dd style="margin: 0.125rem 0 0' + (mono ? "; font-family: 'IBM Plex Mono', monospace" : '') + '">' + esc(value) + '</dd></div>';
}

function cardHtml(d) {
  const kind = !d.online ? 'offline' : (d.location ? 'online' : 'nolocation');
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
      '<button type="button" data-do="edit" style="' + light + '">Edit location</button></div>';
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
                      'credentials': 'Face / cards changed',
                      'setup pin': 'Setup PIN made', 'device key': 'Device key', 'refused': 'Refused', 'admin': 'Admin' };

async function refresh(force) {
  if (!force && document.activeElement && document.activeElement.classList.contains('loc')) return;
  const data = await api('GET', '/api/admin/devices');
  if (!data.ok) return showBar(data.message);
  const list = data.devices;
  $('n-devices').textContent = list.length;
  $('n-online').textContent = list.filter((d) => d.online).length;
  $('n-offline').textContent = list.filter((d) => !d.online).length;
  $('n-nolocation').textContent = list.filter((d) => !d.location).length;
  $('device-list').innerHTML = list.length ? list.map(cardHtml).join('')
    : '<p style="margin: 0; color: #4a5650">No device yet. Start the edge app on a Pi and it appears here by itself.</p>';
  $('updated').textContent = clock();
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

$('refresh').addEventListener('click', (e) => press(e.currentTarget, () => refresh(true)));

$('logout').addEventListener('click', async (e) => {
  e.preventDefault();
  await api('POST', '/api/admin/logout');
  location.href = 'Login.dc.html';
});

api('GET', '/api/admin/me').then((me) => {
  if (!me.ok) return showBar(me.message);
  if (!me.logged_in) return location.href = 'Login.dc.html';
  $('admin-name').textContent = me.username;
  refresh(true);
  setInterval(() => everySecond(() => refresh(false)), 1000);
});
