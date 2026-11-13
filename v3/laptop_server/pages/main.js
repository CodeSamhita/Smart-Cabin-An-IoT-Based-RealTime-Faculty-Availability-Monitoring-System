// Smart Cabin - the home page's logic (Main.dc.html). The same behaviour as the design: choose a school, search a name,
// filter by role and status, open a person. The data comes from the server (/api/people-status every 10 s), and a
// person's timetable and last report from /api/person.

const STATUS = {
  available: { label: 'Available', bg: '#dcf1e3', fg: '#14532d', dot: 'background: #1e8a4c' },
  meeting: { label: 'In a meeting', bg: '#fbecc6', fg: '#6b4a00', dot: 'background: #d39b0b' },
  not_available: { label: 'Not available', bg: '#f8dcd5', fg: '#8a2412', dot: 'background: #9e2a17' },
  unknown: { label: 'Unknown', bg: '#e6eae8', fg: '#3a4540', dot: 'border: 2px solid #6b7570; box-sizing: border-box' },
  not_set_up: { label: 'Not set up', bg: '#ffffff', fg: '#3a4540', dot: 'border: 2px dashed #8a948f; box-sizing: border-box' }
};
const SCHOOL_COLORS = ['#e6ecf5'];

const state = { all: [], loaded: false, failed: false, q: '', status: 'all', role: 'all', school: '', picked: '', open: false, filtersOpen: false,
                person: null };

// ---------- the design's helpers ----------
function shortSchool(s) { return s.replace(/^Presidency School of /, ''); }

function initials(name) {
  return name.replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
}

// Lower number = more senior. Leadership roles first, then Professor, Associate, Assistant (by grade), then others.
function designationRank(d) {
  const s = (d || '').toLowerCase();
  const base = s.split(/\s*(?:&|\band\b)\s*/)[0];
  if (!s) return 99;
  if (/provost/.test(s)) return 0;
  if (/\bdean\b/.test(s) && !/(associate|assistant) dean/.test(s)) return 1;
  if (/(associate|assistant) dean|director/.test(s)) return 2;
  if (/\bhod\b/.test(s) && !/assistant hod/.test(s)) return 3;
  if (/^professor/.test(base)) return /practice/.test(base) ? 5 : 4;
  if (/^associate professor/.test(base)) return /selection/.test(base) ? 6 : 6.5;
  if (/^assistant professor/.test(base)) {
    if (/adjunct|research/.test(base)) return 7.8;
    if (/selection/.test(base)) return 7;
    if (/senior/.test(base)) return 7.2;
    if (/grade\s*-?\s*1/.test(base)) return 7.4;
    return 7.6;
  }
  if (/adjunct|visiting/.test(s)) return 8;
  if (/trainer|soft skill|l&d/.test(s)) return 9;
  if (/teaching assistant|lab instructor/.test(s)) return 10;
  return 11;
}

// Main title of a designation, e.g. "Assistant Professor - Senior Scale & Coordinator" -> "Assistant Professor".
function baseTitle(d) {
  const s = (d || '').split(/\s*(?:&|\band\b|\s-\s|\(|,)\s*/i)[0];
  return s.replace(/\s+(grade|senior|selection)\b.*$/i, '').trim();
}

// A person's role filter keys: the "role" column (except plain Faculty) and their main title.
function roleKeys(p) {
  const keys = [];
  if (p.role && p.role !== 'Faculty') keys.push('role:' + p.role);
  const t = baseTitle(p.designation);
  if (t && t !== p.role) keys.push('title:' + t);
  return keys;
}

function chipStyle(on) {
  return 'min-height: 2.25rem; padding: 0 0.75rem; border-radius: 999px; font: inherit; font-size: 0.75rem; font-weight: 600; cursor: pointer; ' + (on ? 'background: #1b2d4b; color: #ffffff; border: 1px solid #1b2d4b' : 'background: #ffffff; color: #1a211e; border: 1px solid #b8c1cf');
}

function sortKey(name) { return name.replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.|Justice)\s*/i, '').toLowerCase(); }

const pill = (s) => 'display: inline-flex; align-self: flex-start; align-items: center; gap: 0.375rem; padding: 0.25rem 0.625rem; border-radius: 999px; font-size: 0.8125rem; font-weight: 600; background: ' + STATUS[s].bg + '; color: ' + STATUS[s].fg + (s === 'not_set_up' ? '; border: 1px solid #c6d0ca' : '');
const dot = (s) => 'width: 0.5625rem; height: 0.5625rem; border-radius: 50%; ' + STATUS[s].dot;

function decorate(p) {
  const s = STATUS[p.status] ? p.status : 'unknown';
  return { ...p, status: s, initials: initials(p.name), schoolShort: shortSchool(p.school), cabinText: p.location || 'No cabin set',
           statusLabel: STATUS[s].label, pillStyle: pill(s), dotStyle: dot(s) };
}

// ---------- data ----------
async function load() {
  const data = await api('GET', '/api/people-status');
  if (!data.ok) {
    state.failed = !state.loaded;
    $('live-dot').style.background = '#e07a5f';
    $('live-time').textContent = 'not updated';
    showBar('Could not load the faculty list: ' + data.message);
    return render();
  }
  state.all = data.people
    .map((r, i) => ({ ...r, order: i }))
    .sort((a, b) => (designationRank(a.designation) - designationRank(b.designation)) || sortKey(a.name).localeCompare(sortKey(b.name)));
  state.loaded = true;
  state.failed = false;
  $('live-dot').style.background = '#5fd38d';
  $('live-time').textContent = clock();
  $('live').title = 'Live · updated ' + clock();
  render();
  if (state.open) fillDetails();
}

// ---------- drawing ----------
function render() {
  const st = state, all = st.all;
  const q = st.q.trim().toLowerCase();
  const searching = !!q || st.role !== 'all' || st.status !== 'all';

  $('failed').hidden = !st.failed;
  $('tools').hidden = !st.loaded;
  $('q').placeholder = st.school ? 'Search a name in this school' : 'Search a name in all schools';
  $('schools').hidden = !(st.loaded && !st.school && !searching);
  $('results').hidden = !(st.loaded && (!!st.school || searching));

  // school buttons
  const schools = Array.from(new Set(all.map((p) => p.school).filter(Boolean))).sort((a, b) => shortSchool(a).localeCompare(shortSchool(b)));
  $('school-grid').innerHTML = schools.map((s, i) => {
    const n = all.filter((p) => p.school === s).length;
    const style = 'display: flex; flex-direction: column; align-items: flex-start; gap: 0.375rem; min-height: 8rem; padding: 1.25rem; text-align: left; font: inherit; color: #1b2d4b; border: 1px solid #cfd9e8; border-radius: 0.75rem; cursor: pointer; box-shadow: 0 0.125rem 0.5rem rgba(27,45,75,0.08); background: ' + SCHOOL_COLORS[i % SCHOOL_COLORS.length];
    return '<button type="button" data-school="' + esc(s) + '" style="' + style + '">' +
      '<span style="font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; color: #3d5275; font-weight: 600">Presidency School of</span>' +
      '<span style="flex: 1; font-size: 1.125rem; font-weight: 700; line-height: 1.3">' + esc(shortSchool(s)) + '</span>' +
      '<span style="display: inline-flex; align-items: center; gap: 0.375rem; font-size: 0.875rem; font-weight: 600; color: #2a4a7a">' + n + (n === 1 ? ' faculty member' : ' faculty') +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width: 1rem; height: 1rem"><path d="M5 12h14M13 6l6 6-6 6"></path></svg></span>' +
      '</button>';
  }).join('');

  // people
  const matched = all
    .filter((p) => (!q || p.name.toLowerCase().includes(q)) && (!st.school || p.school === st.school) && (st.role === 'all' || roleKeys(p).includes(st.role)))
    .map(decorate)
    .filter((p) => st.status === 'all' || p.status === st.status);
  $('results-title').textContent = st.school || 'Results in all schools';
  $('count-text').textContent = st.loaded ? matched.length + ' of ' + all.length + ' faculty' : 'Loading people.csv…';
  $('empty').hidden = !(st.loaded && matched.length === 0);
  $('people-grid').innerHTML = matched.map((p) => {
    const card = 'display: flex; flex-direction: column; gap: 0.75rem; text-align: left; font: inherit; color: inherit; cursor: pointer; padding: 1rem; border-radius: 0.75rem; background: #ffffff; box-shadow: 0 0.125rem 0.5rem rgba(27,45,75,0.08); border: ' + (p.id === st.picked ? '2px solid #1b2d4b' : '1px solid #dde2ea') + '; margin: ' + (p.id === st.picked ? '0' : '1px');
    return '<button type="button" data-id="' + esc(p.id) + '" style="' + card + '">' +
      '<span style="display: flex; align-items: center; gap: 0.75rem">' +
      '<span style="width: 2.5rem; height: 2.5rem; flex: none; border-radius: 50%; background: #e6ecf5; color: #1b2d4b; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.875rem">' + esc(p.initials) + '</span>' +
      '<span style="display: flex; flex-direction: column; min-width: 0">' +
      '<span style="font-weight: 600; font-size: 0.9375rem">' + esc(p.name) + '</span>' +
      '<span style="font-size: 0.8125rem; color: #56625c">' + esc(p.designation) + '</span>' +
      '<span style="font-size: 0.75rem; color: #56625c">' + esc(p.schoolShort) + '</span>' +
      '</span></span>' +
      '<span style="' + p.pillStyle + '"><span style="' + p.dotStyle + '"></span>' + esc(p.statusLabel) + '</span>' +
      (p.how ? '<span style="margin-top: -0.375rem; font-size: 0.75rem; color: #56625c">' + esc(p.how) + '</span>' : '') +
      '</button>';
  }).join('');

  // filters
  const inSchool = st.school ? all.filter((p) => p.school === st.school) : all;
  const roleCount = {};
  inSchool.forEach((p) => roleKeys(p).forEach((k) => { roleCount[k] = (roleCount[k] || 0) + 1; }));
  const roleOptions = [{ value: 'all', label: 'All roles (' + inSchool.length + ')' }].concat(
    Object.keys(roleCount)
      .sort((a, b) => (a.startsWith('role:') ? 0 : 1) - (b.startsWith('role:') ? 0 : 1)
        || designationRank(a.slice(a.indexOf(':') + 1)) - designationRank(b.slice(b.indexOf(':') + 1))
        || a.localeCompare(b))
      .map((k) => ({ value: k, label: k.slice(k.indexOf(':') + 1) + ' (' + roleCount[k] + ')' })));
  $('role-options').innerHTML = roleOptions.map((o) =>
    '<button type="button" data-role="' + esc(o.value) + '" aria-pressed="' + (st.role === o.value) + '" style="' + chipStyle(st.role === o.value) + '">' + esc(o.label) + '</button>').join('');
  $('status-options').innerHTML = ['all', 'available', 'meeting', 'not_available', 'unknown', 'not_set_up'].map((k) =>
    '<button type="button" data-status="' + k + '" aria-pressed="' + (st.status === k) + '" style="' + chipStyle(st.status === k) + '">' + (k === 'all' ? 'Any status' : STATUS[k].label) + '</button>').join('');
  const active = (st.role !== 'all' ? 1 : 0) + (st.status !== 'all' ? 1 : 0);
  $('filters-label').textContent = 'Filters' + (active ? ' · ' + active : '');
  $('filters-btn').setAttribute('aria-expanded', st.filtersOpen ? 'true' : 'false');
  $('filters-btn').style.cssText = 'position: relative; z-index: 1; flex: none; display: inline-flex; align-items: center; gap: 0.375rem; min-height: 2.25rem; padding: 0 0.75rem; border-radius: 0.5rem; font: inherit; font-size: 0.875rem; font-weight: 600; cursor: pointer; ' + (active || st.filtersOpen ? 'background: #ffffff; color: #1b2d4b; border: 1px solid #ffffff' : 'background: transparent; color: #ffffff; border: 1px solid rgba(255,255,255,0.4)');
  $('filters').hidden = !(st.filtersOpen && st.loaded);
  $('filters-backdrop').hidden = !(st.filtersOpen && st.loaded);
  $('modal').hidden = !(st.open && all.some((p) => p.id === st.picked));
}

// The details window: the design's fields, plus the real timetable and last report
async function fillDetails() {
  const found = state.all.find((p) => p.id === state.picked);
  if (!found) return;
  const sel = decorate(found);
  $('sel-initials').textContent = sel.initials;
  $('sel-name').textContent = sel.name;
  $('sel-designation').textContent = sel.designation;
  $('sel-pill').style.cssText = sel.pillStyle;
  $('sel-dot').style.cssText = sel.dotStyle;
  $('sel-status').textContent = sel.statusLabel;
  $('sel-how').textContent = sel.how || '';
  $('sel-how').hidden = !sel.how;
  $('sel-cabin').textContent = sel.cabinText;
  const data = await api('GET', '/api/person?id=' + encodeURIComponent(sel.id));
  if (!data.ok) {
    $('sel-timetable').innerHTML = '<div style="padding: 0.75rem 0.875rem; border-radius: 0.5rem; background: #f8dcd5; color: #8a2412; font-size: 0.875rem">' + esc(data.message) + '</div>';
    return;
  }
  const p = data.person;
  $('sel-seen').textContent = p.updated || (p.status === 'not_set_up' ? 'no cabin device' : '–');
  state.person = p;
  drawTimetable();
}

// The timetable in the details window: the whole week, today highlighted (no Week / Today switch: the user's call)
function drawTimetable() {
  const p = state.person;
  if (!p) return;
  const time = '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 0.8125rem; color: #3c4842; white-space: nowrap">';
  // The week as the university's section timetable (periods across, days down) is wider than the window
  $('sel-timetable').closest('section').style.maxWidth = p.grid ? '78rem' : '28.75rem';
  if (p.grid) {
    // min-width 0 lets the wide grid scroll inside the window instead of stretching it past the screen
    $('sel-timetable').style.minWidth = '0';
    $('sel-timetable').parentElement.style.minWidth = '0';
    $('sel-timetable').innerHTML = gridHtml(p.grid, p.day);
    return;
  }
  $('sel-timetable').innerHTML = (p.week || []).map((d) => {
    const today = d.day === p.day;
    const lines = d.items.length
      ? d.items.map((i) => '<div style="display: flex; flex-wrap: wrap; gap: 0.125rem 0.75rem">' + time + esc(i.start) + '–' + esc(i.end) +
          '</span><span style="font-size: 0.8125rem">' + esc(i.activity) + '</span></div>').join('')
      : '<span style="font-size: 0.8125rem; color: #56625c">Free</span>';
    return '<div style="display: flex; gap: 0.75rem; padding: 0.625rem 0.75rem; border-radius: 0.5rem; ' +
      (today ? 'background: #e6ecf5; border: 2px solid #1b2d4b' : 'background: #f4f5f8; border: 2px solid transparent') + '">' +
      '<span style="flex: none; width: 3rem; display: flex; flex-direction: column; gap: 0.125rem">' +
      '<span style="font-size: 0.8125rem; font-weight: 700; color: #1b2d4b">' + esc(d.day.slice(0, 3)) + '</span>' +
      (today ? '<span style="font-size: 0.6875rem; font-weight: 600; color: #1b2d4b">Today</span>' : '') + '</span>' +
      '<span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.375rem">' + lines + '</span></div>';
  }).join('');
}

// The week grid, laid out like the university's section timetable (aSc): one column per period with its
// time, the short breaks as narrow "Break" columns, one row per day, each class in the period(s) it takes
// (section on top, course in the middle, batch and room at the bottom), lunch as "Lunch Break". Today's row is outlined.
function gridHtml(g, todayName) {
  const colours = ['#eef1f4', '#eef1f4'];   // headings and day labels: the site's soft grey (no PDF cyan / yellow)
  const cols = [];                       // {period} or {brk}, in time order
  g.periods.forEach((per) => {
    cols.push({ period: per });
    const brk = g.breaks.find((b) => b.start === per.end);
    if (brk) cols.push({ brk: brk });
  });
  const colOf = {};
  cols.forEach((c, i) => { if (c.period) colOf[c.period.n] = i + 2; });   // grid column (1 is the day)
  const rows = g.days.length;
  const cell = (row, col, span, style, html) => '<div style="grid-row: ' + row + '; grid-column: ' + col + ' / span ' + span +
    '; ' + style + '">' + html + '</div>';
  const out = [cell(1, 1, 1, 'background: #ffffff', '')];
  const brkText = 'writing-mode: vertical-rl; transform: rotate(180deg); font-size: 2.25rem; line-height: 1';
  cols.forEach((c, i) => {
    const head = 'background: ' + colours[i % 2] + '; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.375rem; padding: 0.625rem 0.25rem 0.375rem; text-align: center';
    out.push(cell(1, i + 2, 1, head, c.period
      ? '<span style="font-size: 1.875rem; line-height: 1">' + c.period.n + '</span><span style="font-size: 0.75rem; white-space: nowrap">' + esc(c.period.start) + ' - ' + esc(c.period.end) + '</span>'
      : '<span style="font-size: 1rem; line-height: 1">Break</span><span style="font-size: 0.625rem; line-height: 1.3">' + esc(c.brk.start) + '<br>' + esc(c.brk.end) + '</span>'));
    if (c.brk) {
      out.push('<div style="grid-row: 2 / span ' + rows + '; grid-column: ' + (i + 2) + '; background: #ffffff; display: flex; align-items: center; justify-content: center">' +
        '<span style="' + brkText + '">Break</span></div>');
    }
  });
  g.days.forEach((d, r) => {
    const row = r + 2;
    const today = d.day === todayName;
    out.push(cell(row, 1, 1, 'background: ' + (today ? '#1b2d4b; color: #ffffff' : colours[r % 2]) + '; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 0.25rem; padding: 0 0.375rem',
      '<span style="font-size: 2.5rem; line-height: 1">' + esc(d.day.slice(0, 3)) + '</span>' +
      (today ? '<span style="font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em">TODAY</span>' : '')));
    const groups = {};                   // batches of one lab share a cell, one under the other
    const taken = {};
    d.items.forEach((it) => {
      if (it.kind === 'lunch') { taken[it.from] = true; return; }   // drawn below, like the breaks
      const k = it.from + '-' + it.to; (groups[k] = groups[k] || []).push(it);
    });
    const bg = today ? '#dce6f5' : '#ffffff';
    Object.values(groups).forEach((list) => {
      const first = list[0];
      if (!colOf[first.from] || !colOf[first.to]) return;
      for (let n = first.from; n <= first.to; n++) taken[n] = true;
      const inner = list.map((it) => '<div style="flex: 1; display: flex; flex-direction: column; padding: 0.375rem 0.5rem 0.25rem">' +
          '<span style="font-size: 0.75rem; text-align: center">' + esc(it.section) + '</span>' +
          '<span style="flex: 1; display: flex; align-items: center; justify-content: center; padding: 0.375rem 0; font-size: 1.125rem; text-align: center; overflow-wrap: anywhere">' + esc(it.course) + '</span>' +
          '<span style="display: flex; justify-content: space-between; gap: 0.25rem; font-size: 0.75rem"><span>' + esc(it.batch) + '</span><span style="font-size: 0.9375rem">' + esc(it.room) + '</span></span></div>'
      ).join('<div style="height: 1px; background: #1a211e"></div>');
      out.push(cell(row, colOf[first.from], colOf[first.to] - colOf[first.from] + 1,
        'background: ' + bg + '; display: flex; flex-direction: column', inner));
    });
    g.periods.forEach((per) => {
      if (!taken[per.n]) out.push(cell(row, colOf[per.n], 1, 'background: ' + bg, ''));
    });
  });
  // Lunch Break like the breaks: days in a row with lunch in the same period share one tall cell with the words
  // written upwards (the whole column when it is the same period every day, as on the section sheet)
  const lunchAt = g.days.map((d) => (d.items.find((it) => it.kind === 'lunch') || {}).from);
  for (let r = 0; r < rows; r++) {
    const n = lunchAt[r];
    if (!n || !colOf[n] || (r > 0 && lunchAt[r - 1] === n)) continue;
    let span = 1;
    while (r + span < rows && lunchAt[r + span] === n) span++;
    const size = span >= 3 ? '2.25rem' : span === 2 ? '1.5rem' : '1rem';
    out.push('<div style="grid-row: ' + (r + 2) + ' / span ' + span + '; grid-column: ' + colOf[n] + '; background: #ffffff; display: flex; align-items: center; justify-content: center; text-align: center">' +
      (span >= 2 ? '<span style="' + brkText + '; font-size: ' + size + '; white-space: nowrap">Lunch Break</span>' : '<span style="font-size: 1rem; padding: 0 0.25rem">Lunch Break</span>') + '</div>');
  }
  // Today's row: one navy frame over the whole row (on top of the cells, clicks pass through)
  const t = g.days.findIndex((d) => d.day === todayName);
  if (t >= 0) {
    out.push('<div style="grid-row: ' + (t + 2) + '; grid-column: 1 / -1; border: 3px solid #1b2d4b; pointer-events: none; z-index: 1"></div>');
  }
  // Sizes as on the printed sheet: tall day rows, wide period columns, narrow break columns
  const template = '5rem ' + cols.map((c) => (c.period ? 'minmax(6rem, 1fr)' : '3.25rem')).join(' ');
  return '<div style="overflow-x: auto; -webkit-overflow-scrolling: touch">' +
    '<div style="display: grid; grid-template-columns: ' + template + '; grid-template-rows: auto repeat(' + rows + ', minmax(7.5rem, auto)); gap: 1px; background: #1a211e; border: 2px solid #1a211e; min-width: 60rem; color: #1a211e; font-family: Arial, Helvetica, sans-serif">' +
    out.join('') + '</div></div>';
}


// ---------- clicks and typing ----------
$('school-grid').addEventListener('click', (e) => {
  const b = e.target.closest('[data-school]');
  if (b) { Object.assign(state, { school: b.dataset.school, q: '', status: 'all', role: 'all' }); $('q').value = ''; render(); }
});
$('people-grid').addEventListener('click', (e) => {
  const b = e.target.closest('[data-id]');
  if (b) { Object.assign(state, { picked: b.dataset.id, open: true }); render(); fillDetails(); }
});
$('role-options').addEventListener('click', (e) => {
  const b = e.target.closest('[data-role]');
  if (b) { state.role = b.dataset.role; render(); }
});
$('status-options').addEventListener('click', (e) => {
  const b = e.target.closest('[data-status]');
  if (b) { state.status = b.dataset.status; render(); }
});
$('q').addEventListener('input', (e) => { state.q = e.target.value; render(); });
$('back').addEventListener('click', () => { Object.assign(state, { school: '', q: '', status: 'all', role: 'all', filtersOpen: false }); $('q').value = ''; render(); });
$('filters-btn').addEventListener('click', () => { state.filtersOpen = !state.filtersOpen; render(); });
$('filters-backdrop').addEventListener('click', () => { state.filtersOpen = false; render(); });
$('filters-done').addEventListener('click', () => { state.filtersOpen = false; render(); });
$('clear-filters').addEventListener('click', () => { Object.assign(state, { role: 'all', status: 'all' }); render(); });
$('modal-close').addEventListener('click', () => { state.open = false; render(); });
$('modal-backdrop').addEventListener('click', () => { state.open = false; render(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && (state.open || state.filtersOpen)) { state.open = false; state.filtersOpen = false; render(); } });

// Logged in already (admin or faculty)? The header button shows who, and leads to their own page instead of Login
api('GET', '/api/me').then((me) => {
  if (!me.ok || !me.role || me.must_change) return;
  const link = $('login-link');
  link.textContent = (me.username || me.person_id) + ' · ' + (me.role === 'admin' ? 'Devices' : 'My cabin');
  link.href = me.role === 'admin' ? 'Devices.dc.html' : 'Faculty.dc.html';
});

load();
setInterval(() => everySecond(load), 1000);
