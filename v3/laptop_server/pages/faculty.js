// Smart Cabin - My cabin, a faculty member's own page (Faculty.dc.html). Reads /api/faculty/home every 5 s.
//   status    : the big light, how they are in, and the colour key (PLAN.md section 2)
//   timetable : several named timetables, one "in use"; the university's periods across, days down, breaks full height;
//               edit: class or lunch, first / last period, course, room, section, batch (the server checks it all)
//   advanced  : account details + change password, registration (face sets / cards), the cabin device's details,
//               parts and maintenance (persondevice.js)

let home = null;
let view = 'simple';
let current = '';              // the timetable shown
let draft = null;              // {name, oldName, week} while editing
let askingDelete = false;

const COLOUR_KEY = [
  ['available', 'Available', 'In the cabin, alone', 'background: #1e8a4c'],
  ['meeting', 'In a meeting', 'In the cabin, with others', 'background: #d39b0b'],
  ['not_available', 'Not available', 'Not in the cabin (the timetable says where, if known)', 'background: #9e2a17'],
  ['unknown', 'Unknown', 'The device has sent nothing for 60 s (pages only)', 'border: 2px solid #6b7570; box-sizing: border-box'],
  ['registering', 'Blue', 'Registration or adding face / card at the device', 'background: #2a5bd7'],
  ['dark', 'Short white flash', 'The room is dark: once every 2 minutes a light for the camera, to check who is in, then back to the status colour', 'background: #ffffff; border: 1px solid #9aa5b4; box-sizing: border-box'],
];
const LIGHT = { available: ['#1e8a4c', 'green'], meeting: ['#d39b0b', 'yellow'], not_available: ['#9e2a17', 'red'] };
const SHORT_DAYS = { Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed', Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat' };

const initialsOf = (n) => (n || '').replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
const col = (n) => 1 + n + (n >= 3 ? 1 : 0) + (n >= 7 ? 1 : 0);     // grid column of a period (day names are column 1)
const copyWeek = (w) => { const c = {}; home.days.forEach((d) => { c[d] = (w[d] || []).map((e) => Object.assign({}, e)); }); return c; };
const emptyWeek = () => { const c = {}; home.days.forEach((d) => { c[d] = []; }); return c; };

function say(id, ok, text) {
  $(id).textContent = text;
  $(id).style.color = ok ? '#14532d' : '#8a2412';
  $(id).hidden = !text;
}

// ---------- status and cabin ----------
function drawTop() {
  const p = home, r = p.registration;
  $('initials').textContent = initialsOf(p.name);
  $('name').textContent = p.name;
  $('subtitle').textContent = [p.designation, (p.school || '').replace(/^Presidency School of /, ''), p.id].filter(Boolean).join(' · ');
  const s = STATUS_LOOK[p.status] || STATUS_LOOK.unknown;
  $('big-ring').style.background = s.bg;
  $('big-dot').style.background = s.dot;
  $('big-dot').style.boxShadow = '0 0 0 0.5rem ' + s.glow;
  $('big-label').textContent = s.label;
  $('big-label').style.color = s.fg;
  $('big-text').textContent = p.how || p.where || s.text;
  $('legend').innerHTML = COLOUR_KEY.map(([key, label, meaning, dot]) => '<li style="display: flex; align-items: center; gap: 0.625rem; padding: 0.375rem 0.5rem; border-radius: 0.375rem' +
    (key === p.status ? '; background: #f4f5f8; outline: 1px solid #b8c1cf' : '') + '"><span aria-hidden="true" style="width: 0.875rem; height: 0.875rem; flex: none; border-radius: 50%; ' + dot + '"></span>' +
    '<span style="font-size: 0.8125rem; font-weight: 600; min-width: 7.5rem">' + label + '</span><span style="font-size: 0.75rem; color: #56625c">' + meaning + '</span></li>').join('');
  const row = (label, value, mono) => '<div><dt style="font-size: 0.75rem; color: #56625c">' + label + '</dt><dd style="margin: 0.125rem 0 0; ' +
    (mono ? "font-family: 'IBM Plex Mono', monospace" : 'font-weight: 600') + '">' + value + '</dd></div>';
  if (!r) {
    $('cabin').innerHTML = row('Cabin', 'No cabin device') + row('Device', '–', true);
  } else {
    const light = LIGHT[p.status];
    $('cabin').innerHTML = row('Cabin', esc(r.location || '–')) + row('Device', esc(r.device), true) +
      row('Last report', esc(p.updated || '–'), true) + row('People counted', esc(r.headcount === '' ? '–' : r.headcount)) +
      row('ID card', r.card_in === 'yes' ? 'tapped in' : 'not tapped in') +
      row('Indication light', light ? '<span style="display: inline-flex; align-items: center; gap: 0.375rem"><span aria-hidden="true" style="width: 0.75rem; height: 0.75rem; border-radius: 50%; background: ' + light[0] + '; border: 1px solid #9aa5b4"></span>' + light[1] + '</span>' : '–');
  }
}

// ---------- timetable ----------
function shownWeek() {
  if (draft) return draft.week;
  const t = home.timetables.tables.find((x) => x.name === current);
  return t ? t.week : emptyWeek();
}

function drawTabs() {
  const tables = home.timetables.tables;
  const names = tables.map((t) => t.name);
  if (draft && draft.isNew) names.push(draft.name || 'New timetable');
  $('tabs').innerHTML = names.map((n) => {
    const on = draft ? (draft.isNew ? n === (draft.name || 'New timetable') : n === draft.oldName) : n === current;
    return '<button type="button" role="tab" data-name="' + esc(n) + '" aria-selected="' + on + '" style="display: inline-flex; align-items: center; gap: 0.5rem; min-height: 2.25rem; padding: 0 0.875rem; border-radius: 999px; font: inherit; font-size: 0.8125rem; font-weight: 600; cursor: pointer; ' +
      (on ? 'background: #1b2d4b; color: #ffffff; border: 1px solid #1b2d4b' : 'background: #ffffff; color: #1a211e; border: 1px solid #b8c1cf') + '">' + esc(n) +
      (n === home.timetables.in_use ? '<span style="font-size: 0.6875rem; font-weight: 600; padding: 0.125rem 0.5rem; border-radius: 999px; background: #dcf1e3; color: #14532d">In use</span>' : '') + '</button>';
  }).join('') + (draft ? '' : '<button type="button" id="new-tt" style="display: inline-flex; align-items: center; gap: 0.25rem; min-height: 2.25rem; padding: 0 0.75rem; border: 1px dashed #b8c1cf; border-radius: 999px; background: transparent; color: #1b2d4b; font: inherit; font-size: 0.8125rem; font-weight: 600; cursor: pointer">+ New timetable</button>');
}

function drawGrid() {
  const week = shownWeek();
  const P = home.periods, today = home.day;
  const days = home.days.filter((d) => d !== 'Saturday' || (week[d] || []).length);
  const line = '; border-right: 1px solid #b8c1cf; border-bottom: 1px solid #b8c1cf; box-sizing: border-box';
  const head = (c, a, b) => '<div style="grid-row: 1; grid-column: ' + c + '; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.125rem; padding: 0.375rem; background: #e6ecf5' + line + '">' +
    '<span style="font-size: 1rem; font-weight: 700; color: #1b2d4b">' + a + '</span><span style="font-family: \'IBM Plex Mono\', monospace; font-size: 0.6875rem; color: #3c4842">' + b + '</span></div>';
  let html = head(1, '', '');
  for (let n = 1; n <= 8; n++) html += head(col(n), n, P[n][0] + '–' + P[n][1]);
  home.breaks.forEach((b, k) => {
    const c = k ? 9 : 4;
    html += head(c, '', '');
    html += '<div style="grid-row: 2 / span ' + days.length + '; grid-column: ' + c + '; display: flex; align-items: center; justify-content: center; background: #f4f5f8' + line + '"><span style="writing-mode: vertical-rl; transform: rotate(180deg); font-size: 0.9375rem; font-weight: 700; letter-spacing: 0.08em; color: #56625c">Break</span></div>';
  });
  days.forEach((d, i) => {
    const row = i + 2, isToday = d === today, bg = isToday ? '#f7f9fc' : '#ffffff';
    html += '<div style="grid-row: ' + row + '; grid-column: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.25rem; background: ' + (isToday ? '#e6ecf5' : '#f4f5f8') + line + '">' +
      '<span style="font-size: 1rem; font-weight: 700">' + SHORT_DAYS[d] + '</span>' +
      (isToday ? '<span style="font-size: 0.6875rem; font-weight: 600; padding: 0.125rem 0.5rem; border-radius: 999px; background: #1b2d4b; color: #ffffff">Today</span>' : '') + '</div>';
    const groups = [], used = {};
    (week[d] || []).forEach((e) => {
      const g = groups.find((x) => x.kind === 'class' && e.kind === 'class' && x.from === e.from && x.to === e.to);
      if (g) g.items.push(e); else groups.push({ kind: e.kind, from: e.from, to: e.to, items: [e] });
    });
    groups.forEach((g) => {
      for (let n = g.from; n <= g.to; n++) used[n] = true;
      const place = 'grid-row: ' + row + '; grid-column: ' + col(g.from) + ' / ' + (col(g.to) + 1) + '; ';
      if (g.kind === 'lunch') {
        html += '<div style="' + place + 'display: flex; align-items: center; justify-content: center; background: #fbecc6' + line + '"><span style="font-size: 0.875rem; font-weight: 700; color: #6b4a00">Lunch break</span></div>';
      } else {
        html += '<div style="' + place + 'display: flex; flex-direction: column; background: ' + bg + line + '">' + g.items.map((e, k) =>
          '<div style="flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 0.125rem; padding: 0.375rem 0.5rem; text-align: center' + (k ? '; border-top: 1px solid #b8c1cf' : '') + '">' +
          '<span style="font-size: 0.6875rem; color: #3c4842">' + esc(e.section) + '</span><span style="font-size: 0.875rem; font-weight: 700; color: #1b2d4b">' + esc(e.course) + '</span>' +
          '<span style="display: flex; justify-content: space-between; gap: 0.5rem; font-size: 0.6875rem; color: #3c4842"><span>' + esc(e.batch) + '</span><span style="font-family: \'IBM Plex Mono\', monospace">' + esc(e.room) + '</span></span></div>').join('') + '</div>';
      }
    });
    for (let n = 1; n <= 8; n++) if (!used[n]) html += '<div style="grid-row: ' + row + '; grid-column: ' + col(n) + '; background: ' + bg + line + '"></div>';
  });
  $('tt-view').innerHTML = '<div style="min-width: 60rem; display: grid; grid-template-columns: 5.5rem repeat(2, minmax(5.5rem, 1fr)) 2rem repeat(4, minmax(5.5rem, 1fr)) 2rem repeat(2, minmax(5.5rem, 1fr)); grid-auto-rows: minmax(4.5rem, auto); border-top: 1px solid #b8c1cf; border-left: 1px solid #b8c1cf">' + html + '</div>';
}

function periodOptions(value) {
  let html = '';
  for (let n = 1; n <= 8; n++) html += '<option value="' + n + '"' + (Number(value) === n ? ' selected' : '') + '>' + n + '</option>';
  return html;
}

function drawEdit() {
  const P = home.periods, input = 'min-height: 2.25rem; padding: 0 0.5rem; border: 1px solid #b8c1cf; border-radius: 0.375rem; font: inherit; font-size: 0.8125rem';
  const select = 'min-height: 2.25rem; border: 1px solid #b8c1cf; border-radius: 0.375rem; background: #ffffff; font: inherit; font-size: 0.8125rem';
  $('tt-edit').innerHTML = home.days.map((d) => {
    const isToday = d === home.day;
    return '<div style="display: flex; flex-wrap: wrap; align-items: flex-start; gap: 0.5rem; padding: 0.625rem; border-radius: 0.625rem; ' + (isToday ? 'background: #e6ecf5; border: 2px solid #1b2d4b' : 'background: #f4f5f8; border: 2px solid transparent') + '">' +
      '<span style="width: 7rem; flex: none; font-size: 0.875rem; font-weight: 700; padding-top: 0.5rem">' + d + '</span>' +
      '<div style="flex: 1; min-width: 0; display: flex; flex-wrap: wrap; gap: 0.5rem">' +
      draft.week[d].map((e, i) => '<div data-day="' + d + '" data-i="' + i + '" style="width: 17rem; display: flex; flex-direction: column; gap: 0.375rem; padding: 0.5rem; border-radius: 0.5rem; background: #ffffff; border: 1px solid #b8c1cf">' +
        '<div style="display: flex; align-items: center; gap: 0.25rem">' +
        '<select data-field="kind" aria-label="Class or lunch" style="flex: 1; ' + select + '"><option value="class"' + (e.kind === 'class' ? ' selected' : '') + '>Class</option><option value="lunch"' + (e.kind === 'lunch' ? ' selected' : '') + '>Lunch break</option></select>' +
        '<select data-field="from" aria-label="From period" style="width: 3.5rem; ' + select + '">' + periodOptions(e.from) + '</select><span aria-hidden="true">–</span>' +
        '<select data-field="to" aria-label="To period" style="width: 3.5rem; ' + select + '">' + periodOptions(e.to) + '</select>' +
        '<button type="button" data-remove="1" aria-label="Delete this entry" title="Delete" style="width: 2.25rem; height: 2.25rem; flex: none; border: 0; border-radius: 0.375rem; background: transparent; color: #8a2412; cursor: pointer; font: inherit; font-weight: 700">✕</button></div>' +
        '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 0.6875rem; color: #56625c">' + ((P[e.from] || ['', ''])[0]) + '–' + ((P[e.to] || ['', ''])[1]) + '</span>' +
        (e.kind === 'class' ? '<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.25rem">' +
          '<input type="text" data-field="course" aria-label="Course" value="' + esc(e.course) + '" placeholder="Course" style="' + input + '">' +
          '<input type="text" data-field="room" aria-label="Room" value="' + esc(e.room) + '" placeholder="Room" style="' + input + '">' +
          '<input type="text" data-field="section" aria-label="Section" value="' + esc(e.section) + '" placeholder="Section" style="' + input + '">' +
          '<input type="text" data-field="batch" aria-label="Batch" value="' + esc(e.batch) + '" placeholder="Batch" style="' + input + '"></div>' : '') +
        '</div>').join('') +
      '<button type="button" data-add="' + d + '" style="min-height: 2.25rem; padding: 0 0.875rem; border: 1px dashed #b8c1cf; border-radius: 0.5rem; background: transparent; color: #1b2d4b; font: inherit; font-size: 0.8125rem; font-weight: 600; cursor: pointer">+ Add</button>' +
      '</div></div>';
  }).join('');
}

function drawTimetable() {
  const tables = home.timetables.tables;
  if (!draft && !tables.some((t) => t.name === current)) current = home.timetables.in_use || (tables[0] ? tables[0].name : '');
  drawTabs();
  $('edit-tt').hidden = !!draft || !current;
  $('cancel-tt').hidden = !draft;
  $('save-tt').hidden = !draft;
  $('name-box').hidden = !draft;
  $('table-actions').hidden = !!draft || !current || current === home.timetables.in_use;
  $('delete-tt').textContent = askingDelete ? 'Yes, delete "' + current + '"' : 'Delete timetable';
  $('tt-head').innerHTML = draft || !current ? '' : '<h3 style="margin: 0; font-size: 1.25rem; font-weight: 700">' + esc(current) + '</h3>' +
    (current === home.timetables.in_use ? '<span style="font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.625rem; border-radius: 999px; background: #dcf1e3; color: #14532d">In use</span>' : '');
  $('tt-view').hidden = !!draft;
  $('tt-edit').hidden = !draft;
  if (draft) drawEdit(); else if (current) drawGrid(); else $('tt-view').innerHTML = '<p style="margin: 0; padding: 1.25rem; text-align: center; border: 1px dashed #b8c1cf; border-radius: 0.75rem; color: #4a5650">No timetable yet. Press "+ New timetable".</p>';
}

$('tabs').addEventListener('click', (e) => {
  if (e.target.closest('#new-tt')) {
    draft = { isNew: true, oldName: '', name: '', week: emptyWeek() };
    $('tt-name').value = '';
    say('tt-note', true, '');
    return drawTimetable();
  }
  const b = e.target.closest('[data-name]');
  if (b && !draft) { current = b.dataset.name; askingDelete = false; say('tt-note', true, ''); drawTimetable(); }
});
$('edit-tt').addEventListener('click', () => {
  const t = home.timetables.tables.find((x) => x.name === current);
  draft = { isNew: false, oldName: current, name: current, week: copyWeek(t.week) };
  $('tt-name').value = current;
  say('tt-note', true, '');
  drawTimetable();
});
$('cancel-tt').addEventListener('click', () => { draft = null; say('tt-note', true, ''); drawTimetable(); });
$('tt-name').addEventListener('input', () => { draft.name = $('tt-name').value; drawTabs(); });
$('tt-edit').addEventListener('change', (e) => {
  const box = e.target.closest('[data-day]');
  if (!box || !e.target.dataset.field) return;
  const entry = draft.week[box.dataset.day][Number(box.dataset.i)];
  const field = e.target.dataset.field;
  entry[field] = field === 'from' || field === 'to' ? Number(e.target.value) : e.target.value;
  if (field === 'from' && entry.to < entry.from) entry.to = entry.from;
  if (field === 'kind' || field === 'from' || field === 'to') drawEdit();
});
$('tt-edit').addEventListener('click', (e) => {
  const add = e.target.closest('[data-add]');
  if (add) { draft.week[add.dataset.add].push({ kind: 'class', from: 1, to: 1, course: '', room: '', section: '', batch: '' }); return drawEdit(); }
  const remove = e.target.closest('[data-remove]');
  if (remove) {
    const box = remove.closest('[data-day]');
    draft.week[box.dataset.day].splice(Number(box.dataset.i), 1);
    drawEdit();
  }
});
$('save-tt').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await api('POST', '/api/faculty/timetable/save', { old_name: draft.oldName, name: $('tt-name').value, week: draft.week });
  say('tt-note', r.ok, r.message);
  if (!r.ok) return;
  home.timetables = r.timetables;
  current = $('tt-name').value.trim().replace(/\s+/g, ' ');
  draft = null;
  drawTimetable();
}));
$('use-tt').addEventListener('click', (e) => press(e.currentTarget, async () => {
  const r = await api('POST', '/api/faculty/timetable/use', { name: current });
  say('tt-note', r.ok, r.message);
  if (r.ok) { home.timetables = r.timetables; drawTimetable(); }
}));
$('delete-tt').addEventListener('click', (e) => {
  if (!askingDelete) { askingDelete = true; return drawTimetable(); }
  press(e.currentTarget, async () => {
    const r = await api('POST', '/api/faculty/timetable/delete', { name: current });
    say('tt-note', r.ok, r.message);
    askingDelete = false;
    if (r.ok) { home.timetables = r.timetables; current = r.timetables.in_use; }
    drawTimetable();
  });
});

// ---------- advanced ----------
function drawViews() {
  $('views').innerHTML = [['simple', 'Simple'], ['advanced', 'Advanced']].map(([value, label]) => '<button type="button" data-view="' + value + '" aria-pressed="' + (view === value) + '" style="min-height: 2.25rem; padding: 0 1rem; border: 0; border-radius: 999px; font: inherit; font-size: 0.875rem; font-weight: 600; cursor: pointer; ' +
    (view === value ? 'background: #1b2d4b; color: #ffffff' : 'background: transparent; color: #1b2d4b') + '">' + label + '</button>').join('');
  $('advanced').hidden = view !== 'advanced';
}

function drawAdvanced() {
  const p = home, r = p.registration;
  $('ac-username').textContent = p.account.username || '–';
  $('ac-id').textContent = p.id;
  $('ac-card').textContent = p.account.id_card_number || '–';
  $('device-sections').hidden = !r;
  if (!r) return;
  $('rd-when').textContent = 'registered ' + r.from_time;
  $('registration').innerHTML = drawRegistration(p);
  $('device-link').href = r.page_url || '#';
  $('dv-code').textContent = r.device;
  $('details').innerHTML = drawDetails(r.details);
  $('uptime').textContent = r.details && r.details.uptime ? 'Up ' + r.details.uptime : '';
  $('parts').innerHTML = drawParts(r.parts);
}

$('views').addEventListener('click', (e) => {
  const b = e.target.closest('[data-view]');
  if (b) { view = b.dataset.view; drawViews(); }
});

$('pw-form').addEventListener('submit', (e) => {
  e.preventDefault();
  press($('pw-btn'), async () => {
    const r = await api('POST', '/api/faculty/change-password', { current: $('pw-current').value, new: $('pw-new').value, again: $('pw-again').value });
    say('pw-note', r.ok, r.message);
    if (r.ok) { $('pw-current').value = ''; $('pw-new').value = ''; $('pw-again').value = ''; }
  });
});

$('logout').addEventListener('click', async (e) => {
  e.preventDefault();
  await api('POST', '/api/logout');
  location.href = 'Login.dc.html';
});

setUpMaintenance(() => (home && home.registration ? home.registration.device : ''));

$('deactivate').addEventListener('click', (e) => {
  const device = home && home.registration ? home.registration.device : '';
  if (!device || !confirm('Deactivate ' + device + '? It stops reporting your status until you register at a new device.')) return;
  press(e.currentTarget, async () => {
    const r = await api('POST', '/api/faculty/deactivate');
    showBar(r.message, r.ok ? 'note' : undefined);
    refresh();
  });
});

async function refresh() {
  const data = await api('GET', '/api/faculty/home');
  if (!data.ok) return showBar(data.message);
  const first = !home;
  const keepTimetables = home && draft ? home.timetables : null;
  home = data.person;
  if (keepTimetables) home.timetables = keepTimetables;        // don't disturb a timetable being edited
  $('live-time').textContent = clock();
  $('signed-in').textContent = home.account.username || home.id;
  drawTop();
  drawAdvanced();
  if (first || !draft) drawTimetable();
}

api('GET', '/api/me').then((me) => {
  if (!me.ok) return showBar(me.message);
  if (me.role !== 'faculty' || me.must_change) return location.href = 'Login.dc.html';
  drawViews();
  refresh();
  setInterval(() => everySecond(refresh), 5000);
});
