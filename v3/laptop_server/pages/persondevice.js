// Smart Cabin - shared by AdminPerson.dc.html and Faculty.dc.html: draws one person's cabin device the way the device's
// own Advanced view does (status, charts, face sets / cards, device details, parts, maintenance).
// The details come from the server (the Pi sends them with each hello, every minute).
//   statusPill(), drawStatusBox(), drawCharts(), drawRegistration(), drawDetails(), drawParts(), setUpMaintenance()

const STATUS_LOOK = {
  available: { label: 'Available', text: 'In the cabin, alone', bg: '#dcf1e3', fg: '#14532d', dot: '#1e8a4c', glow: 'rgba(30,138,76,0.18)' },
  meeting: { label: 'In a meeting', text: 'In the cabin, with others', bg: '#fbecc6', fg: '#6b4a00', dot: '#d39b0b', glow: 'rgba(211,155,11,0.2)' },
  not_available: { label: 'Not available', text: 'Not in the cabin', bg: '#f8dcd5', fg: '#8a2412', dot: '#9e2a17', glow: 'rgba(158,42,23,0.18)' },
  unknown: { label: 'Unknown', text: 'The cabin device is not reporting', bg: '#e6eae8', fg: '#3a4540', dot: '#6b7570', glow: 'rgba(107,117,112,0.18)' },
  not_set_up: { label: 'Not set up', text: 'No cabin device', bg: '#ffffff', fg: '#3a4540', dot: '#8a948f', glow: 'rgba(138,148,143,0.18)' },
};
const PART_NAMES = { camera: 'Camera', rfid: 'Card reader', led: 'Indication light', buzzer: 'Buzzer', vision: 'Vision', 'people model': 'People model',
                     'face model': 'Face model', server: 'Server link', page: 'This page', registration: 'Registration' };
const MAINTENANCE = [
  { title: 'Restart program', text: 'Restarts only the Smart Cabin software. Quick; nothing is lost.',
    detail: 'The Smart Cabin program on this device stops and starts again. Status updates pause for a few seconds.' },
  { title: 'Reboot device', text: 'Restarts the whole Raspberry Pi. Takes about a minute.',
    detail: 'The device restarts completely. The cabin shows "Unknown" on the server until it is back, about a minute.' },
  { title: 'Shut down', text: 'Turns the Pi off safely before you unplug it.',
    detail: 'The device turns off. It only comes back when the power is unplugged and plugged in again.' },
  { title: 'Factory reset', text: 'Erases the registered person, face data, RFID cards and settings on this device.', typed: true, danger: true,
    detail: 'This removes everything stored for this cabin on this device and on the server. The device goes back to "Not set up" and needs the admin to authorize setup again. This cannot be undone.' },
];

function statusPill(status) {
  const s = STATUS_LOOK[status] || STATUS_LOOK.unknown;
  return '<span style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.375rem 0.875rem; border-radius: 999px; background: ' + s.bg +
    '; color: ' + s.fg + '; font-size: 0.9375rem; font-weight: 700' + (status === 'not_set_up' ? '; border: 1px solid #c6d0ca' : '') +
    '"><span style="width: 0.625rem; height: 0.625rem; border-radius: 50%; background: ' + s.dot + '"></span>' + s.label + '</span>';
}

function yesNo(v) { return v === 'yes' ? 'yes' : v === 'no' ? 'no' : '–'; }

function drawStatusBox(p) {
  // The Status box: status, in the cabin, confidence, people counted, ID card, last report, temperature
  const r = p.registration;
  const row = (label, value, mono) => '<div><dt style="font-size: 0.75rem; color: #56625c">' + label + '</dt><dd style="margin: 0.125rem 0 0; ' +
    (mono ? "font-family: 'IBM Plex Mono', monospace" : 'font-weight: 600') + '">' + esc(value) + '</dd></div>';
  return '<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem">' + statusPill(p.status) +
    (p.how ? '<span style="font-size: 0.8125rem; color: #4a5650">' + esc(p.how) + '</span>' : '') + '</div>' +
    '<dl style="margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem 1rem; font-size: 0.875rem">' +
    row('In the cabin', yesNo(r.in_cabin)) + row('Confidence', r.confidence === '' ? '–' : r.confidence + ' %') +
    row('People counted', r.headcount === '' ? '–' : r.headcount) + row('ID card', r.card_in === 'yes' ? 'tapped in' : 'not tapped in') +
    row('Last report', p.updated || '–', true) + row('Temperature', r.temperature === '' ? '–' : r.temperature + ' °C', true) + '</dl>' +
    '<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.375rem 0.75rem; border-top: 1px solid #eef1f4; padding-top: 0.75rem; font-size: 0.8125rem">' +
    '<span style="display: inline-flex; align-items: center; gap: 0.375rem; font-weight: 600; color: ' + (r.online ? '#14532d' : '#8a2412') + '"><span style="width: 0.5rem; height: 0.5rem; border-radius: 50%; background: ' + (r.online ? '#1e8a4c' : '#9e2a17') + '"></span>' +
    (r.online ? 'Device reporting' : 'Device not reporting') + '</span>' +
    (r.page_url ? '<a href="' + esc(r.page_url) + '" target="_blank" rel="noopener" style="font-weight: 600">Open the device page (live view)</a>' : '') + '</div>';
}

function chart(values, colour, min, max) {
  // A small line chart as SVG (the last readings from presence_log.csv)
  const nums = values.map(Number).filter((v) => !Number.isNaN(v));
  if (!nums.length) return '<svg viewBox="0 0 120 32" style="width: 100%; height: 4rem; display: block" aria-hidden="true"><path d="M0 8H120M0 16H120M0 24H120" stroke="#dde2ea" stroke-width="0.5"></path></svg>';
  const top = Math.max(max, ...nums);
  const pts = nums.map((v, i) => ((i + 60 - nums.length) * 120 / 59).toFixed(1) + ',' + (30 - (Math.min(top, Math.max(min, v)) - min) / (top - min) * 28).toFixed(1)).join(' ');
  return '<svg viewBox="0 0 120 32" preserveAspectRatio="none" style="width: 100%; height: 4rem; display: block" aria-hidden="true"><path d="M0 8H120M0 16H120M0 24H120" stroke="#dde2ea" stroke-width="0.5"></path>' +
    '<polyline points="' + pts + '" fill="none" stroke="' + colour + '" stroke-width="1.5" vector-effect="non-scaling-stroke"></polyline></svg>';
}

function drawCharts(recent) {
  const list = recent || [];
  const last = list[list.length - 1] || {};
  const one = (label, key, unit, colour, min, max) => '<div style="display: flex; flex-direction: column; gap: 0.375rem; padding: 0.75rem; border-radius: 0.5rem; background: #f4f5f8">' +
    '<div style="display: flex; align-items: baseline; gap: 0.5rem"><span style="font-size: 0.75rem; color: #56625c; flex: 1">' + label + '</span>' +
    '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 1rem; font-weight: 600">' + (last[key] !== undefined && last[key] !== '' ? esc(last[key]) + unit : '–') + '</span></div>' +
    chart(list.map((r) => r[key]), colour, min, max) + '<span style="font-size: 0.6875rem; color: #56625c">last ' + list.length + ' reports</span></div>';
  return one('People counted', 'headcount', '', '#2a4a7a', 0, 3) + one('Confidence', 'confidence', ' %', '#1e8a4c', 0, 100) +
    one('CPU temperature', 'temperature', ' °C', '#d39b0b', 30, 85);
}

function drawRegistration(p) {
  const r = p.registration, data = r.person_data || {};
  const sets = data.face_sets || [], cards = data.cards || [];
  const item = 'display: flex; align-items: center; gap: 0.5rem; min-height: 2.25rem; padding: 0.25rem 0.5rem; border-radius: 0.375rem; background: #ffffff; font-size: 0.8125rem';
  const check = (ok) => '<span style="width: 1.75rem; height: 1.75rem; flex: none; border-radius: 50%; background: ' + (ok ? '#1e8a4c' : '#9aa5b4') + '; color: #ffffff; display: flex; align-items: center; justify-content: center; font-size: 0.8125rem; font-weight: 700">' + (ok ? '✓' : '–') + '</span>';
  const photos = Number(r.face_photos || 0);
  return '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(14rem, 100%), 1fr)); gap: 0.5rem">' +
    '<div style="display: flex; flex-direction: column; gap: 0.75rem; padding: 0.875rem; border-radius: 0.5rem; background: #f4f5f8">' +
    '<div style="display: flex; align-items: center; gap: 0.625rem">' + check(photos > 0) + '<div><div style="font-size: 0.875rem; font-weight: 600">' + (photos ? 'Face registered' : 'No face registered') + '</div>' +
    '<div style="font-size: 0.75rem; color: #56625c">' + photos + ' photos' + (sets.length ? ' · ' + sets.length + (sets.length === 1 ? ' set' : ' sets') : '') + '</div></div></div>' +
    (sets.length ? '<ul style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 0.25rem">' + sets.map((s, i) => '<li style="' + item + '">Face set ' + (i + 1) + ' · ' + esc(s.photos) + ' photos <span style="color: #56625c">· ' + esc(s.added) + '</span></li>').join('') + '</ul>' : '') +
    '</div>' +
    '<div style="display: flex; flex-direction: column; gap: 0.75rem; padding: 0.875rem; border-radius: 0.5rem; background: #f4f5f8">' +
    '<div style="display: flex; align-items: center; gap: 0.625rem">' + check(r.cards > 0) + '<div><div style="font-size: 0.875rem; font-weight: 600">' + (r.cards ? 'RFID cards linked' : 'No RFID card linked') + '</div>' +
    '<div style="font-size: 0.75rem; color: #56625c">' + r.cards + (r.cards === 1 ? ' card' : ' cards') + '</div></div></div>' +
    (cards.length ? '<ul style="margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 0.25rem">' + cards.map((c, i) => '<li style="' + item + '">Card ' + (i + 1) + ' <span style="font-size: 0.75rem; color: #56625c">· ' + esc(c.added) + '</span></li>').join('') + '</ul>' : '') +
    '</div></div>';
}

function drawDetails(details) {
  const d = details || {};
  const meters = (d.meters || []).map((m) => {
    const colour = m.pct >= 85 ? '#9e2a17' : m.pct >= 65 ? '#d39b0b' : '#1e8a4c';
    return '<div style="display: flex; flex-direction: column; gap: 0.375rem; padding: 0.75rem; border-radius: 0.5rem; background: #f4f5f8">' +
      '<div style="display: flex; align-items: baseline; gap: 0.5rem"><span style="font-size: 0.75rem; color: #56625c; flex: 1">' + esc(m.label) + '</span><span style="font-family: \'IBM Plex Mono\', monospace; font-size: 1rem; font-weight: 600">' + esc(m.value) + '</span></div>' +
      '<div role="meter" aria-label="' + esc(m.label) + '" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Number(m.pct) + '" style="height: 0.375rem; border-radius: 999px; background: #dde2ea; overflow: hidden"><span style="display: block; height: 100%; width: ' + Number(m.pct) + '%; border-radius: 999px; background: ' + colour + '"></span></div>' +
      '<span style="font-size: 0.6875rem; color: #56625c">' + esc(m.note) + '</span></div>';
  }).join('');
  const groups = (d.groups || []).map((g) => '<div style="display: flex; flex-direction: column; gap: 0.375rem"><h3 style="margin: 0; font-size: 0.8125rem; font-weight: 700; color: #1b2d4b">' + esc(g.title) + '</h3>' +
    '<dl style="margin: 0; display: grid; grid-template-columns: minmax(7rem, auto) 1fr; gap: 0.375rem 1rem; font-size: 0.8125rem; padding: 0.625rem 0.75rem; border-radius: 0.5rem; border: 1px solid #eef1f4">' +
    g.rows.map((r) => '<dt style="color: #56625c">' + esc(r[0]) + '</dt><dd style="' + (r[2] ? "margin: 0; font-family: 'IBM Plex Mono', monospace; word-break: break-all" : 'margin: 0') + '">' + esc(r[1] || '–') + '</dd>').join('') + '</dl></div>').join('');
  if (!meters && !groups) return '<p style="margin: 0; font-size: 0.875rem; color: #4a5650">No details yet. The device sends them about once a minute.</p>';
  return '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(11rem, 100%), 1fr)); gap: 0.5rem">' + meters + '</div>' +
    '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(20rem, 100%), 1fr)); gap: 1rem">' + groups + '</div>';
}

function drawParts(parts) {
  return Object.keys(parts || {}).sort().map((n) => {
    const p = parts[n], absent = p.present === false;
    const colour = absent ? '#9aa5b4' : p.ok ? '#1e8a4c' : '#9e2a17';
    return '<div style="display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem 0; border-bottom: 1px solid #eef1f4; font-size: 0.875rem">' +
      '<span style="width: 0.5rem; height: 0.5rem; flex: none; border-radius: 50%; background: ' + colour + '"></span>' +
      '<span style="font-weight: 600; min-width: 6rem">' + esc(PART_NAMES[n] || n) + '</span>' +
      '<span style="font-size: 0.75rem; font-weight: 600; color: ' + (absent ? '#56625c' : p.ok ? '#14532d' : '#8a2412') + '">' + (absent ? 'Not present' : p.ok ? 'OK' : 'Problem') + '</span>' +
      '<span style="margin-left: auto; font-size: 0.75rem; color: #56625c; text-align: right">' + esc(p.message) + '</span></div>';
  }).join('') || '<p style="margin: 0; font-size: 0.875rem; color: #4a5650">No report from the device yet.</p>';
}

function setUpMaintenance(getDevice) {
  // The Maintenance list and its confirm dialog (ids: actions, working, confirm, cf-*). As on the device's page,
  // the actions only say they come later; nothing is changed.
  let key = -1;
  $('actions').innerHTML = MAINTENANCE.map((a, i) => '<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 0.75rem; padding: 0.75rem 0; border-top: 1px solid #eef1f4">' +
    '<div style="flex: 1 1 14rem; min-width: 0"><div style="font-size: 0.9375rem; font-weight: 600">' + a.title + '</div><div style="font-size: 0.8125rem; color: #56625c">' + a.text + '</div></div>' +
    '<button type="button" data-action="' + i + '" style="min-height: 2.5rem; padding: 0 1rem; border-radius: 0.5rem; font: inherit; font-size: 0.875rem; font-weight: 600; cursor: pointer; ' +
    (a.danger ? 'background: #ffffff; color: #8a2412; border: 1px solid #e2b4aa' : 'background: #ffffff; color: #1b2d4b; border: 1px solid #b8c1cf') + '">' + a.title + '</button></div>').join('');
  const update = () => {
    const a = MAINTENANCE[key];
    const blocked = !!(a && a.typed && $('cf-input').value.trim().toUpperCase() !== String(getDevice()).toUpperCase());
    $('cf-run').disabled = blocked;
    $('cf-run').style.background = blocked ? '#dde2ea' : (a && a.danger ? '#9e2a17' : '#1b2d4b');
    $('cf-run').style.color = blocked ? '#56625c' : '#ffffff';
  };
  $('actions').addEventListener('click', (e) => {
    const b = e.target.closest('[data-action]');
    if (!b) return;
    key = Number(b.dataset.action);
    const a = MAINTENANCE[key];
    $('cf-t').textContent = a.title + '?';
    $('cf-detail').textContent = a.detail;
    $('cf-typed').hidden = !a.typed;
    $('cf-code').textContent = getDevice();
    $('cf-input').value = '';
    $('cf-run').textContent = a.title;
    update();
    $('confirm').hidden = false;
  });
  $('cf-input').addEventListener('input', update);
  $('cf-cancel').addEventListener('click', () => { $('confirm').hidden = true; });
  $('confirm-backdrop').addEventListener('click', () => { $('confirm').hidden = true; });
  $('cf-run').addEventListener('click', () => {
    $('confirm').hidden = true;
    $('working').textContent = MAINTENANCE[key].title + ': Not available yet in this prototype. Nothing was changed.';
    $('working').hidden = false;
    setTimeout(() => { $('working').hidden = true; }, 5000);
  });
}
