/**
 * api.js – Zentrale API-Kommunikationsschicht für LernyTube.
 *
 * Stellt Funktionen für alle Backend-Anfragen bereit und
 * verwaltet das JWT-Token im localStorage.
 */

const API_BASE = '';  // Gleiche Domain, kein separater API-Server nötig

/**
 * Gibt den gespeicherten JWT-Token zurück.
 * @returns {string|null} Der Token oder null wenn nicht angemeldet.
 */
function getToken() {
  return localStorage.getItem('lt_token');
}

/**
 * Speichert Token und Benutzerdaten nach erfolgreichem Login.
 * @param {string} token - Der JWT-Token.
 * @param {Object} user  - Die Benutzerdaten.
 */
function saveAuth(token, user) {
  localStorage.setItem('lt_token', token);
  localStorage.setItem('lt_user', JSON.stringify(user));
}

/**
 * Löscht alle gespeicherten Authentifizierungsdaten und leitet zur Login-Seite.
 */
function logout() {
  localStorage.removeItem('lt_token');
  localStorage.removeItem('lt_user');
  window.location.href = '/';
}

/**
 * Gibt den angemeldeten Benutzer aus dem localStorage zurück.
 * @returns {Object|null} Die Benutzerdaten oder null.
 */
function getCurrentUser() {
  const raw = localStorage.getItem('lt_user');
  return raw ? JSON.parse(raw) : null;
}

/**
 * Führt einen authentifizierten API-Request aus.
 *
 * @param {string} path    - Der API-Pfad (z.B. "/api/sessions").
 * @param {string} method  - HTTP-Methode (GET, POST, PUT, DELETE).
 * @param {Object} [body]  - Optionaler Request-Body als Objekt.
 * @returns {Promise<any>} Die geparste JSON-Antwort.
 * @throws {Error} Bei Netzwerkfehlern oder HTTP-Fehlerstatus.
 */
async function apiFetch(path, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  if (res.status === 401) {
    logout();
    return;
  }

  if (res.status === 204) return null;  // No Content

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Ein Fehler ist aufgetreten');
  return data;
}

// ─── Authentifizierung ────────────────────────────────────────────────
const Auth = {
  register: (username, email, password) =>
    apiFetch('/api/auth/register', 'POST', { username, email, password }),
  login: (username, password) =>
    apiFetch('/api/auth/login', 'POST', { username, password }),
  me: () => apiFetch('/api/auth/me'),
};

// ─── Sessions ─────────────────────────────────────────────────────────
const Sessions = {
  list:   ()             => apiFetch('/api/sessions/'),
  get:    (id)           => apiFetch(`/api/sessions/${id}`),
  tags: ()                => apiFetch("/api/sessions/tags"),
  create: (title, date, video_url, tags = []) =>
    apiFetch('/api/sessions/', 'POST', { title, date, video_url }),
  delete: (id)           => apiFetch(`/api/sessions/${id}`, 'DELETE'),
};

// ─── Snapshots ─────────────────────────────────────────────────────────
const Snapshots = {
  list:        (session_id)            => apiFetch(`/api/snapshots/?session_id=${session_id}`),
  search:      (q)                     => apiFetch(`/api/snapshots/search?q=${encodeURIComponent(q)}`),
  create:      (session_id, timestamp_sec, notes, frame_data = null, frame_url = null) =>
    apiFetch('/api/snapshots/', 'POST', { session_id, timestamp_sec, notes, frame_data, frame_url }),
  update:      (id, notes)             => apiFetch(`/api/snapshots/${id}`, 'PUT', { notes }),
  uploadFrame: (id, frame_data)        => apiFetch(`/api/snapshots/${id}/upload-frame`, 'POST', { frame_data }),
  delete:      (id)                    => apiFetch(`/api/snapshots/${id}`, 'DELETE'),
};
