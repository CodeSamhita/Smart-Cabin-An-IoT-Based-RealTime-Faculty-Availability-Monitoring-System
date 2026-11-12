// Smart Cabin - the admin's page for one faculty member (AdminPerson.dc.html?id=<server id>).
// Reads /api/admin/person every 5 s (and the device list, for "Assign a cabin"), and runs the admin's buttons:
// edit location, setup PIN, remove registration, save username / ID card number, reset to a default password.

const personId = new URLSearchParams(location.search).get('id') || '';
let person = null;
let devicesList = [];
let editingLocation = false;
const LOGIN_LOOK = { none: ['No login yet', '#eef1f4', '#3c4842'], change: ['Must change password', '#fbecc6', '#6b4a00'], active: ['Active', '#dcf1e3', '#14532d'] };

const initialsOf = (n) => (n || '').replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');

function note(ok, text) {
  $('note').textContent = text;
  $('note').style.color = ok ? '#14532d' : '#8a2412';
  $('note').hidden = !text;
}

function showPin(pin) {
  $('pin').textContent = pin;
  $('pin-expires').textContent = 'Expires ' + new Date(Date.now() + 15 * 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  $('pin-box').hidden = false;
}

function draw() {
  const p = person, r = p.registration;
  document.title = 'Smart Cabin – ' + p.name;
  $('initials').textContent = initialsOf(p.name);
  $('name').textContent = p.name;
  $('subtitle').textContent = [p.designation, (p.school || '').replace(/^Presidency School of /, ''), p.id].filter(Boolean).join(' · ');
  $('pill').innerHTML = statusPill(p.status);
  $('setup-registered').hidden = !r;
  $('setup-free').hidden = !!r;
  $('status-box').hidden = !r;
  $('device-sections').hidden = !r;
  if (r) {
    $('cs-device').textContent = r.device + (r.model ? ' · ' + r.model : '');
    $('cs-location').textContent = r.location || '–';
    $('cs-from').textContent = r.from_time;
    $('asking-text').textContent = 'Remove ' + p.name + ' from ' + r.device + '?';
    $('status-body').innerHTML = drawStatusBox(p);
    $('charts').innerHTML = drawCharts(r.recent);
    $('registration').innerHTML = drawRegistration(p);
    $('details').innerHTML = drawDetails(r.details);
    $('uptime').textContent = r.details && r.details.uptime ? 'Up ' + r.details.uptime : '';
    $('parts').innerHTML = drawParts(r.parts);
    markStale(['charts', 'details', 'parts'], !r.online);
  } else {
    const free = devicesList.filter((d) => !d.person && d.location);
    const keep = $('free-device').value;
    $('free-device').innerHTML = free.length ? free.map((d) => '<option value="' + esc(d.device) + '">' + esc(d.device + ' · ' + d.location + ' · free') + '</option>').join('')
      : '<option value="">No free device with a location</option>';
    if (free.some((d) => d.device === keep)) $('free-device').value = keep;
  }
  const look = LOGIN_LOOK[p.account.state] || LOGIN_LOOK.none;
  $('login-state').innerHTML = '<span style="font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.625rem; border-radius: 999px; background: ' + look[1] + '; color: ' + look[2] + '">' + look[0] + '</span>';
  if (document.activeElement !== $('uname') && document.activeElement !== $('card-no')) {
    $('uname').value = p.account.username;
    $('card-no').value = p.account.id_card_number;
  }
}

async function refresh() {
  const [data, list] = await Promise.all([api('GET', '/api/admin/person?id=' + encodeURIComponent(personId)), api('GET', '/api/admin/devices')]);
  if (!data.ok) return showBar(data.message);
  if (list.ok) devicesList = list.devices;
  person = data.person;
  $('live-time').textContent = clock();
  draw();
}

$('edit-loc').addEventListener('click', () => {
  editingLocation = !editingLocation;
  $('loc-box').hidden = !editingLocation;
  if (editingLocation) { $('loc').value = person.registration.location; $('loc').focus(); }
});
$('save-loc').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await api('POST', '/api/admin/location', { device: person.registration.device, location: $('loc').value });
  note(r.ok, r.message);
  if (r.ok) { editingLocation = false; $('loc-box').hidden = true; refresh(); }
}));
$('make-pin').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await api('POST', '/api/admin/pin', { device: person.registration.device });
  note(r.ok, r.ok ? 'PIN made. It works once.' : r.message);
  if (r.ok) showPin(r.pin);
}));
$('make-free-pin').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const device = $('free-device').value;
  if (!device) return note(false, 'There is no free device with a location. Set one up on the Devices page first.');
  const r = await api('POST', '/api/admin/pin', { device });
  note(r.ok, r.ok ? 'PIN made for ' + device + '. ' + person.name + ' registers at that device with it.' : r.message);
  if (r.ok) showPin(r.pin);
}));
$('ask-remove').addEventListener('click', () => { $('asking').hidden = false; });
$('cancel-remove').addEventListener('click', () => { $('asking').hidden = true; });
$('remove').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await api('POST', '/api/admin/unregister', { device: person.registration.device });
  note(r.ok, r.message);
  $('asking').hidden = true;
  refresh();
}));
$('save-ids').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await api('POST', '/api/admin/person/ids', { person_id: personId, username: $('uname').value, id_card_number: $('card-no').value });
  note(r.ok, r.message);
  refresh();
}));
$('reset').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await api('POST', '/api/admin/person/reset-password', { person_id: personId, password: $('reset-pw').value, days: 7 });
  note(r.ok, r.message);
  if (r.ok) $('reset-pw').value = '';
  refresh();
}));
$('logout').addEventListener('click', async (e) => {
  e.preventDefault();
  await api('POST', '/api/logout');
  location.href = 'Login.dc.html';
});

setUpMaintenance(() => (person && person.registration ? person.registration.device : ''));

api('GET', '/api/admin/me').then((me) => {
  if (!me.ok) return showBar(me.message);
  if (!me.logged_in) return location.href = 'Login.dc.html';
  if (!personId) return showBar('No person picked. Open a person from the Devices page.');
  $('admin-name').textContent = me.username;
  refresh();
  setInterval(() => everySecond(refresh), 5000);
});
