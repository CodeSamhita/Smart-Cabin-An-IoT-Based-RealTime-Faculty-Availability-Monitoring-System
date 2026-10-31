// Smart Cabin - login page logic (Login.dc.html). One box for everyone: the admin opens the Devices page, a faculty
// member opens My cabin (Faculty.dc.html). A faculty member still on the admin's default password sets their own first.
// The very first time (no admin yet) the same form makes the admin account; that only works on the server laptop.

let creating = false;          // true = no admin account yet, so the form makes one

function showError(text) {
  $('login-error-text').textContent = text;
  $('login-error').hidden = !text;
}

function askNewPassword() {
  $('login-title').textContent = 'Set your password';
  $('login-form').hidden = true;
  $('set-form').hidden = false;
  $('new-password').focus();
}

async function start() {
  const me = await api('GET', '/api/me');
  if (!me.ok) return showError(me.message);
  if (me.role === 'admin') return location.href = 'Devices.dc.html';
  if (me.role === 'faculty') return me.must_change ? askNewPassword() : (location.href = 'Faculty.dc.html');
  creating = !me.admin_exists;
  if (creating) {
    $('login-title').textContent = 'Create the admin account';
    $('login-btn').textContent = 'Create account';
    $('password').autocomplete = 'new-password';
    if (!me.from_this_laptop) showError('There is no admin account yet. Make it on the laptop that runs the server (open https://localhost:8080/login there).');
  }
}

$('login-form').addEventListener('submit', (e) => {
  e.preventDefault();
  showError('');
  press($('login-btn'), async () => {
    const body = { username: $('username').value, password: $('password').value };
    if (creating) {
      const made = await api('POST', '/api/admin/create', body);
      if (!made.ok) return showError(made.message);
    }
    const r = await api('POST', '/api/login', body);
    if (!r.ok) return showError(r.message);
    if (r.role === 'admin') return location.href = 'Devices.dc.html';
    if (r.must_change) return askNewPassword();
    location.href = 'Faculty.dc.html';
  });
});

$('set-form').addEventListener('submit', (e) => {
  e.preventDefault();
  showError('');
  press($('set-btn'), async () => {
    const r = await api('POST', '/api/faculty/first-password', { new: $('new-password').value, again: $('new-again').value });
    if (!r.ok) return showError(r.message);
    location.href = 'Faculty.dc.html';
  });
});

start();
