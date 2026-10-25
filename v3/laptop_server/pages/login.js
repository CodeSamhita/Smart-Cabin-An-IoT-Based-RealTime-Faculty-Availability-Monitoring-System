// Smart Cabin - login page logic (Login.dc.html). Logs the admin in and opens the Devices page.
// The very first time (no admin yet) the same form makes the admin account; that only works on the server laptop.

let creating = false;          // true = no admin account yet, so the form makes one

function showError(text) {
  $('login-error-text').textContent = text;
  $('login-error').hidden = !text;
}

async function start() {
  const me = await api('GET', '/api/admin/me');
  if (!me.ok) return showError(me.message);
  if (me.logged_in) return location.href = 'Devices.dc.html';
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
    const r = await api('POST', '/api/admin/login', body);
    if (!r.ok) return showError(r.message);
    location.href = 'Devices.dc.html';
  });
});

start();
