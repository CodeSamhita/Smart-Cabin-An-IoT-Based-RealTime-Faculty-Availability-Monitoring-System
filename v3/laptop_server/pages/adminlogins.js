// Smart Cabin - Faculty logins page logic (AdminLogins.dc.html). Loads every faculty member with their username
// (their own, or the suggested one) and ID card number; the admin edits them in the table and makes / updates
// everyone's login at once with one default password. The server checks every username and ID card number.

const SHOWN = 60;
const LOOK = { none: ['No login yet', '#eef1f4', '#3c4842'], change: ['Must change password', '#fbecc6', '#6b4a00'], active: ['Active', '#dcf1e3', '#14532d'] };
let rows = [];

function note(ok, text) {
  $('note').textContent = text;
  $('note').style.color = ok ? '#14532d' : '#8a2412';
  $('note').hidden = !text;
}

function draw() {
  const q = $('q').value.trim().toLowerCase();
  const count = {};
  rows.forEach((r) => { count[r.username] = (count[r.username] || 0) + 1; });
  const matched = rows.filter((r) => !q || r.name.toLowerCase().includes(q) || r.id.includes(q) || r.username.includes(q));
  $('count-text').textContent = matched.length > SHOWN ? 'Showing ' + SHOWN + ' of ' + matched.length + ' · search to find others' : matched.length + ' of ' + rows.length + ' faculty';
  $('rows').innerHTML = matched.slice(0, SHOWN).map((r) => {
    const bad = !/^[a-z0-9.]{3,30}$/.test(r.username) || /^\d+$/.test(r.username) || /^f\d+$/.test(r.username) || count[r.username] > 1;
    const look = LOOK[r.state] || LOOK.none;
    const cell = 'padding: 0.375rem 0.625rem; border-bottom: 1px solid #eef1f4';
    return '<tr data-id="' + esc(r.id) + '">' +
      '<td style="' + cell + "; font-family: 'IBM Plex Mono', monospace\">" + esc(r.id) + '</td>' +
      '<td style="' + cell + '">' + esc(r.name) + '</td>' +
      '<td style="' + cell + '; color: #4a5650; font-size: 0.8125rem">' + esc(r.school.replace(/^Presidency School of /, '')) + '</td>' +
      '<td style="' + cell + '"><input type="text" class="uname" aria-label="Username for ' + esc(r.name) + '" value="' + esc(r.username) + '" style="width: 11rem; min-height: 2.25rem; padding: 0 0.5rem; border-radius: 0.375rem; font-family: \'IBM Plex Mono\', monospace; font-size: 0.8125rem; border: 1px solid ' + (bad ? '#9e2a17; background: #fdf1ee' : '#b8c1cf') + '"></td>' +
      '<td style="' + cell + '"><input type="text" class="card" inputmode="numeric" aria-label="ID card number for ' + esc(r.name) + '" value="' + esc(r.id_card_number) + '" style="width: 9rem; min-height: 2.25rem; padding: 0 0.5rem; border: 1px solid #b8c1cf; border-radius: 0.375rem; font-family: \'IBM Plex Mono\', monospace; font-size: 0.8125rem"></td>' +
      '<td style="' + cell + '"><span style="font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.625rem; border-radius: 999px; white-space: nowrap; background: ' + look[1] + '; color: ' + look[2] + '">' + look[0] + '</span></td></tr>';
  }).join('');
  $('n-all').textContent = rows.length;
  $('n-none').textContent = rows.filter((r) => r.state === 'none').length;
  $('n-change').textContent = rows.filter((r) => r.state === 'change').length;
  $('n-active').textContent = rows.filter((r) => r.state === 'active').length;
  $('create').textContent = rows.some((r) => r.state !== 'none') ? 'Update logins' : 'Create logins for all (' + rows.length + ')';
}

async function load() {
  const data = await api('GET', '/api/admin/logins');
  if (!data.ok) return showBar(data.message);
  rows = data.rows;
  draw();
}

$('rows').addEventListener('change', (e) => {
  const tr = e.target.closest('tr[data-id]');
  if (!tr) return;
  const row = rows.find((r) => r.id === tr.dataset.id);
  if (e.target.classList.contains('uname')) row.username = e.target.value.trim().toLowerCase();
  if (e.target.classList.contains('card')) row.id_card_number = e.target.value.trim();
  draw();
});
$('q').addEventListener('input', draw);

$('create').addEventListener('click', (e) => press(e.currentTarget, async () => {
  if ($('pw').value !== $('pw2').value) return note(false, 'The two default passwords are not the same.');
  const r = await api('POST', '/api/admin/logins/create', { password: $('pw').value, days: $('days').value,
    rows: rows.map((x) => ({ id: x.id, username: x.username, id_card_number: x.id_card_number })) });
  note(r.ok, r.message);
  if (r.ok) { $('pw').value = ''; $('pw2').value = ''; load(); }
}));

$('logout').addEventListener('click', async (e) => {
  e.preventDefault();
  await api('POST', '/api/logout');
  location.href = 'Login.dc.html';
});

api('GET', '/api/admin/me').then((me) => {
  if (!me.ok) return showBar(me.message);
  if (!me.logged_in) return location.href = 'Login.dc.html';
  $('admin-name').textContent = me.username;
  load();
});
