// Smart Cabin - search page logic (Search.dc.html). Filters the real faculty list by name, school, department,
// programme and status, and shows the picked person with today's timetable. Data refreshed every 10 s.

const STATUS = {
  available: { label: 'Available', bg: '#dcf1e3', fg: '#14532d', dot: 'background: #1e8a4c' },
  meeting: { label: 'In a meeting', bg: '#fbecc6', fg: '#6b4a00', dot: 'background: #d39b0b' },
  not_available: { label: 'Not available', bg: '#f8dcd5', fg: '#8a2412', dot: 'background: #9e2a17' },
  unknown: { label: 'Unknown', bg: '#e6eae8', fg: '#3a4540', dot: 'border: 2px solid #6b7570; box-sizing: border-box' },
  not_set_up: { label: 'Not set up', bg: '#ffffff', fg: '#3a4540', dot: 'border: 2px dashed #8a948f; box-sizing: border-box' }
};
const state = { all: [], degreeSchools: {}, status: 'all', picked: '', filled: false };

const pill = (s) => 'display: inline-flex; align-self: flex-start; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 13px; font-weight: 600; background: ' + STATUS[s].bg + '; color: ' + STATUS[s].fg + (s === 'not_set_up' ? '; border: 1px solid #c6d0ca' : '');
const dot = (s) => 'width: 9px; height: 9px; border-radius: 50%; ' + STATUS[s].dot;
const initials = (n) => n.replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s*/i, '').split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
const shortSchool = (s) => s.replace(/^Presidency School of /, '');
const statusOf = (p) => (STATUS[p.status] ? p.status : 'unknown');

function fillSelect(id, values, first, label) {
  const keep = $(id).value;
  $(id).innerHTML = '<option value="">' + first + '</option>' + values.map((v) => '<option value="' + esc(v) + '">' + esc(label ? label(v) : v) + '</option>').join('');
  if (values.includes(keep)) $(id).value = keep;
}

function fillFilters() {
  const uniq = (xs) => Array.from(new Set(xs.filter(Boolean))).sort();
  fillSelect('school', uniq(state.all.map((p) => p.school)), 'All schools', shortSchool);
  const school = $('school').value;
  fillSelect('department', uniq(state.all.filter((p) => !school || p.school === school).map((p) => p.department)), 'All departments');
  fillSelect('programme', Object.keys(state.degreeSchools).sort(), 'All programmes');
}

async function load() {
  const data = await api('GET', '/api/people-status');
  if (!data.ok) {
    $('live-time').textContent = 'not updated';
    showBar('Could not load the faculty list: ' + data.message);
    return;
  }
  state.all = data.people;
  state.degreeSchools = data.degree_schools || {};
  if (!state.filled) { fillFilters(); state.filled = true; }
  $('live-time').textContent = clock();
  render();
}

function render() {
  const q = $('q').value.trim().toLowerCase();
  const school = $('school').value, department = $('department').value, programme = $('programme').value;
  const programmeSchools = programme ? (state.degreeSchools[programme] || []) : null;
  const matched = state.all.filter((p) => (!q || p.name.toLowerCase().includes(q)) && (!school || p.school === school)
    && (!department || p.department === department) && (!programmeSchools || programmeSchools.includes(p.school))
    && (state.status === 'all' || statusOf(p) === state.status));
  const shown = matched.slice(0, 120);
  $('count-text').textContent = matched.length + ' of ' + state.all.length + ' faculty shown' + (matched.length > shown.length ? ' (first ' + shown.length + '; type more of the name)' : '');
  $('empty').hidden = matched.length !== 0;
  $('people-grid').innerHTML = shown.map((p) => {
    const s = statusOf(p);
    const card = 'display: flex; flex-direction: column; gap: 12px; text-align: left; font: inherit; color: inherit; cursor: pointer; padding: 16px; border-radius: 12px; background: #ffffff; border: ' + (p.id === state.picked ? '2px solid #1f4f3d' : '1px solid #dde3df') + '; margin: ' + (p.id === state.picked ? '0' : '1px');
    return '<button type="button" data-id="' + esc(p.id) + '" style="' + card + '">' +
      '<span style="display: flex; align-items: center; gap: 12px">' +
      '<span style="width: 40px; height: 40px; flex: none; border-radius: 50%; background: #e7efe9; color: #1f4f3d; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px">' + esc(initials(p.name)) + '</span>' +
      '<span style="display: flex; flex-direction: column; min-width: 0">' +
      '<span style="font-weight: 600; font-size: 15px">' + esc(p.name) + '</span>' +
      '<span style="font-size: 13px; color: #56625c">' + esc(p.designation) + '</span></span></span>' +
      '<span style="' + pill(s) + '"><span style="' + dot(s) + '"></span>' + STATUS[s].label + '</span>' +
      (p.how ? '<span style="margin-top: -6px; font-size: 12px; color: #56625c">' + esc(p.how) + '</span>' : '') + '</button>';
  }).join('');
  $('chips').innerHTML = ['all', 'available', 'meeting', 'not_available', 'unknown', 'not_set_up'].map((k) => {
    const on = state.status === k;
    return '<button type="button" data-status="' + k + '" aria-pressed="' + on + '" style="min-height: 44px; padding: 0 16px; border-radius: 999px; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; ' +
      (on ? 'background: #1f4f3d; color: #ffffff; border: 1px solid #1f4f3d' : 'background: #ffffff; color: #1a211e; border: 1px solid #b7c3bc') + '">' + (k === 'all' ? 'Everyone' : STATUS[k].label) + '</button>';
  }).join('');
  if (!state.picked && matched.length) pick(matched[0].id);
}

async function pick(id) {
  state.picked = id;
  const p = state.all.find((x) => x.id === id);
  if (!p) return;
  const s = statusOf(p);
  $('selected').hidden = false;
  $('sel-initials').textContent = initials(p.name);
  $('sel-name').textContent = p.name;
  $('sel-designation').textContent = p.designation;
  $('sel-pill').style.cssText = pill(s);
  $('sel-dot').style.cssText = dot(s);
  $('sel-status').textContent = STATUS[s].label;
  $('sel-how').textContent = p.how || '';
  $('sel-how').hidden = !p.how;
  $('sel-school').textContent = shortSchool(p.school);
  $('sel-cabin').textContent = p.location || 'No cabin set';
  const data = await api('GET', '/api/person?id=' + encodeURIComponent(id));
  if (!data.ok) {
    $('sel-timetable').innerHTML = '<div style="padding: 12px; border-radius: 8px; background: #f8dcd5; color: #8a2412; font-size: 14px">' + esc(data.message) + '</div>';
    return;
  }
  const d = data.person;
  $('sel-seen').textContent = d.updated || (d.status === 'not_set_up' ? 'no cabin device' : '–');
  const time = '<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 13px; color: #3c4842; width: 92px; flex: none">';
  $('sel-timetable').innerHTML = d.today.length
    ? d.today.map((i) => '<div style="display: flex; gap: 12px; padding: 12px; border-radius: 8px; background: #f5f6f2">' + time + esc(i.start) + '–' + esc(i.end) + '</span><span style="font-size: 14px">' + esc(i.activity) + '</span></div>').join('')
    : '<div style="display: flex; gap: 12px; padding: 12px; border-radius: 8px; border: 1px dashed #c6d0ca"><span style="font-size: 14px; color: #4a5650">Nothing on the timetable today (' + esc(d.day) + ')</span></div>';
}

$('people-grid').addEventListener('click', (e) => {
  const b = e.target.closest('[data-id]');
  if (b) { pick(b.dataset.id); render(); }
});
$('chips').addEventListener('click', (e) => {
  const b = e.target.closest('[data-status]');
  if (b) { state.status = b.dataset.status; render(); }
});
$('q').addEventListener('input', render);
$('school').addEventListener('change', () => { fillFilters(); render(); });
$('department').addEventListener('change', render);
$('programme').addEventListener('change', render);

load();
setInterval(() => everySecond(load), 1000);
