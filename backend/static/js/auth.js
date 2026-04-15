/**
 * auth.js – Login, Registrierung und Demo-Login für LernyTube.
 */

// Wenn bereits angemeldet → direkt zum Dashboard
if (getToken()) {
  window.location.href = '/dashboard';
}

/**
 * Wechselt zwischen Login- und Registrierungs-Tab.
 */
function showTab(tab) {
  const loginForm    = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const buttons      = document.querySelectorAll('.tab-btn');
  const errorEl      = document.getElementById('auth-error');

  loginForm.classList.toggle('hidden', tab !== 'login');
  registerForm.classList.toggle('hidden', tab !== 'register');
  errorEl.classList.add('hidden');

  buttons.forEach((btn, i) => {
    btn.classList.toggle('active', (i === 0 && tab === 'login') || (i === 1 && tab === 'register'));
  });
}

function showError(msg) {
  const el = document.getElementById('auth-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function togglePwd(fieldId, btn) {
  const input = document.getElementById(fieldId);
  if (input.type === 'password') {
    input.type = 'text';
    btn.style.opacity = '1';
  } else {
    input.type = 'password';
    btn.style.opacity = '0.5';
  }
}

/**
 * Login-Handler.
 */
async function handleLogin(event) {
  event.preventDefault();
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;

  try {
    const res = await Auth.login(username, password);
    saveAuth(res.access_token, res.user);
    window.location.href = '/dashboard';
  } catch (err) {
    showError(err.message);
  }
}

/**
 * Demo-Login: Loggt direkt mit dem Demo-Account ein.
 */
async function loginAsDemo() {
  try {
    const res = await Auth.login('demo', 'DemoPasswort2026+!');
    saveAuth(res.access_token, res.user);
    window.location.href = '/dashboard';
  } catch (err) {
    showError('Demo-Login fehlgeschlagen: ' + err.message);
    // Fallback: Zum Auth-Bereich scrollen
    document.getElementById('auth-section').scrollIntoView({ behavior: 'smooth' });
  }
}

// ─── Registrierung ─────────────────────────────────────────────────────────

function setFieldError(fieldId, message) {
  const input = document.getElementById(fieldId);
  const errId = 'err-' + fieldId.replace('reg-', '').replace('password-confirm', 'password-confirm');
  const err   = document.getElementById(errId);
  if (!input || !err) return;
  if (message) {
    input.classList.add('invalid');
    input.classList.remove('valid');
    err.textContent = message;
    err.classList.add('visible');
  } else {
    input.classList.remove('invalid');
    input.classList.add('valid');
    err.textContent = '';
    err.classList.remove('visible');
  }
}

function validateAllFields() {
  let valid = true;
  const username = document.getElementById('reg-username').value.trim();
  const email    = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const confirm  = document.getElementById('reg-password-confirm').value;

  if (username.length < 3) {
    setFieldError('reg-username', 'Benutzername muss mindestens 3 Zeichen lang sein.');
    valid = false;
  } else { setFieldError('reg-username', ''); }

  if (!email.includes('@') || !email.includes('.')) {
    setFieldError('reg-email', 'Bitte eine gültige E-Mail-Adresse eingeben.');
    valid = false;
  } else { setFieldError('reg-email', ''); }

  if (password.length < 16) {
    setFieldError('reg-password', 'Mindestens 16 Zeichen erforderlich.');
    valid = false;
  } else if (!/[A-Z]/.test(password)) {
    setFieldError('reg-password', 'Mindestens ein Großbuchstabe erforderlich.');
    valid = false;
  } else if (!/[^a-zA-Z0-9]/.test(password)) {
    setFieldError('reg-password', 'Mindestens ein Sonderzeichen erforderlich.');
    valid = false;
  } else { setFieldError('reg-password', ''); }

  if (confirm !== password) {
    setFieldError('reg-password-confirm', 'Die Passwörter stimmen nicht überein.');
    valid = false;
  } else if (confirm.length > 0) { setFieldError('reg-password-confirm', ''); }

  return valid;
}

function checkPasswordHints(value) {
  document.getElementById('hint-length').className  = value.length >= 16          ? 'hint-ok' : '';
  document.getElementById('hint-upper').className   = /[A-Z]/.test(value)         ? 'hint-ok' : '';
  document.getElementById('hint-special').className = /[^a-zA-Z0-9]/.test(value) ? 'hint-ok' : '';
  document.getElementById('hint-length').textContent  = (value.length >= 16          ? '✓' : '✗') + ' Mindestens 16 Zeichen';
  document.getElementById('hint-upper').textContent   = (/[A-Z]/.test(value)         ? '✓' : '✗') + ' Mindestens ein Großbuchstabe';
  document.getElementById('hint-special').textContent = (/[^a-zA-Z0-9]/.test(value) ? '✓' : '✗') + ' Mindestens ein Sonderzeichen (!@#$%^&*...)';
}

async function handleRegister(event) {
  event.preventDefault();
  if (!validateAllFields()) return;

  const username = document.getElementById('reg-username').value.trim();
  const email    = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;

  try {
    const res = await Auth.register(username, email, password);
    saveAuth(res.access_token, res.user);
    await showTosModal();
  } catch (err) {
    showError(err.message);
  }
}

// ─── Nutzungsbedingungen Modal ─────────────────────────────────────────────

async function showTosModal() {
  const modal = document.getElementById('tosModal');
  modal.classList.remove('hidden');

  try {
    const res = await fetch('/api/auth/tos');
    const data = await res.json();
    document.getElementById('tos-content').innerHTML = data.content;
  } catch (_) {
    document.getElementById('tos-content').innerHTML =
      '<p>Fehler beim Laden der Nutzungsbedingungen. Bitte versuche es erneut.</p>';
  }
}

async function acceptTos() {
  const btn = document.getElementById('tos-accept-btn');
  btn.disabled = true;
  btn.textContent = 'Wird gespeichert…';

  try {
    const user = await apiFetch('/api/auth/accept-tos', 'POST');
    localStorage.setItem('lt_user', JSON.stringify(user));
    window.location.href = '/dashboard';
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Zustimmen & fortfahren';
    alert('Fehler: ' + err.message);
  }
}
