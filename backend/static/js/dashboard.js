/**
 * dashboard.js – Logik für die Session-Übersichtsseite.
 *
 * Lädt alle Sessions des Benutzers, zeigt sie als Karten an
 * und verwaltet Erstellen, Löschen, Suchen, Tag-Vergabe und Tag-Filterung.
 */

// Nicht angemeldete Benutzer zurück zur Login-Seite
if (!getToken()) window.location.href = '/';

// ─── Vordefinierte Tag-Vorschläge ─────────────────────────────────
/** @type {string[]} Immer verfügbare Standard-Tags */
const PRESET_TAGS = [
  'Programmierung', 'Mathematik', 'Sprachen', 'Wissenschaft',
  'Geschichte', 'Musik', 'Design', 'Wirtschaft', 'Sonstiges',
];

// ─── Zustand ──────────────────────────────────────────────────────
/** @type {Array} Alle geladenen Sessions */
let allSessions = [];

/** @type {string[]} Alle Tags die der Benutzer bisher verwendet hat */
let userTags = [];

/** @type {string[]} Aktuell im Formular ausgewählte Tags */
let selectedTags = [];

/** @type {string[]} Aktiv gesetzte Tag-Filter im Dashboard */
let activeFilterTags = [];

/** @type {number|null} Timer für Debounce der Notizsuche */
let searchTimer = null;

// ─── Initialisierung ──────────────────────────────────────────────
const user = getCurrentUser();
if (user) document.getElementById('username-display').textContent = user.username;
if (user && user.username === 'EisKatrin') document.getElementById('lernbuch-nav-link').style.display = '';
document.getElementById('session-date').value = new Date().toISOString().split('T')[0];

loadSessions();
loadUserTags();
checkTosAccepted();

// ─── Sessions laden & anzeigen ────────────────────────────────────

/**
 * Lädt alle Sessions vom Backend und zeigt sie an.
 */
async function loadSessions() {
  try {
    allSessions = await Sessions.list();
    applyFilters();
  } catch (err) {
    document.getElementById('sessions-grid').innerHTML =
      `<div class="empty-state">Fehler beim Laden: ${err.message}</div>`;
  }
}

/**
 * Lädt alle bisher genutzten Tags des Benutzers für Vorschläge.
 */
async function loadUserTags() {
  try {
    userTags = await Sessions.tags();
    renderTagFilterBar();
  } catch (_) {
    userTags = [];
  }
}

/**
 * Rendert eine Liste von Sessions als Karten im Grid.
 * @param {Array} sessions - Die anzuzeigenden Sessions.
 */
function renderSessions(sessions) {
  const grid = document.getElementById('sessions-grid');
  if (sessions.length === 0) {
    grid.innerHTML = '<div class="empty-state">Keine Sessions gefunden.</div>';
    return;
  }
  grid.innerHTML = sessions.map(s => `
    <div class="session-card" onclick="openSession('${s.id}')">
      <button class="session-card-delete" onclick="deleteSession(event,'${s.id}')" title="Session löschen">✕</button>
      <div class="session-card-thumb">
        <img src="https://img.youtube.com/vi/${s.youtube_id}/mqdefault.jpg" alt="${escapeHtml(s.title)}" loading="lazy">
      </div>
      <div class="session-card-title" title="${escapeHtml(s.title)}">${escapeHtml(s.title)}</div>
      ${s.video_title ? `<div class="session-card-video-title" title="${escapeHtml(s.video_title)}">${escapeHtml(s.video_title)}</div>` : ''}
      ${s.channel_name ? `<div class="session-card-channel">${escapeHtml(s.channel_name)}</div>` : ''}
      ${s.tags && s.tags.length > 0 ? `
        <div class="session-card-tags">
          ${s.tags.map(t => `<span class="session-tag">${escapeHtml(t)}</span>`).join('')}
        </div>
      ` : ''}
      <div class="session-card-meta">
        <span>${formatDate(s.date)}</span>
        <span class="session-card-snapshots">
          ${s.has_receipt ? '<span class="session-card-receipt" title="Mit Kassenbon abgeschlossen">🧾</span>' : ''}
          📸 ${s.snapshot_count}
        </span>
      </div>
    </div>
  `).join('');
}

// ─── Suche & Filter ───────────────────────────────────────────────

/**
 * Wendet Textsuche und aktive Tag-Filter gleichzeitig an.
 */
function applyFilters() {
  const q = (document.getElementById('search-input').value || '').toLowerCase().trim();
  let result = allSessions;

  // Textfilter (Titel + Datum)
  if (q) {
    result = result.filter(s =>
      s.title.toLowerCase().includes(q) || s.date.includes(q)
    );
  }

  // Tag-Filter (Session muss ALLE aktiven Tags haben)
  if (activeFilterTags.length > 0) {
    result = result.filter(s =>
      activeFilterTags.every(tag => s.tags && s.tags.includes(tag))
    );
  }

  renderSessions(result);
}

/**
 * Wird aufgerufen wenn der Benutzer im Suchfeld tippt.
 * @param {string} query - Der aktuelle Suchbegriff.
 */
function filterSessions(query) {
  applyFilters();

  // Notizsuche mit 300ms Verzögerung
  clearTimeout(searchTimer);
  const q = query.trim();
  if (!q) { clearSnapshotResults(); return; }
  searchTimer = setTimeout(() => searchSnapshotNotes(q), 300);
}

// ─── Tag-Filterleiste ─────────────────────────────────────────────

/**
 * Baut die Tag-Filterleiste aus allen bekannten User-Tags auf.
 */
function renderTagFilterBar() {
  const bar   = document.getElementById('tag-filter-bar');
  const chips = document.getElementById('tag-filter-chips');

  // Alle Tags die in Sessions vorkommen (aus allSessions + userTags)
  const sessionTags = [...new Set(allSessions.flatMap(s => s.tags || []))];
  const allKnown = [...new Set([...sessionTags, ...userTags])].sort();

  if (allKnown.length === 0) { bar.classList.add('hidden'); return; }

  bar.classList.remove('hidden');
  chips.innerHTML = allKnown.map(tag => `
    <button
      class="tag-filter-chip ${activeFilterTags.includes(tag) ? 'active' : ''}"
      onclick="toggleFilterTag('${escapeHtml(tag)}')"
    >${escapeHtml(tag)}</button>
  `).join('');
}

/**
 * Aktiviert oder deaktiviert einen Tag-Filter.
 * @param {string} tag - Der zu togglende Tag.
 */
function toggleFilterTag(tag) {
  if (activeFilterTags.includes(tag)) {
    activeFilterTags = activeFilterTags.filter(t => t !== tag);
  } else {
    activeFilterTags.push(tag);
  }
  renderTagFilterBar();
  applyFilters();
}

// ─── Tag-Eingabe im Modal ─────────────────────────────────────────

/**
 * Gibt alle verfügbaren Vorschläge zurück (Preset + bisher genutzte User-Tags),
 * gefiltert nach dem eingegebenen Text und bereits gewählten Tags.
 * @param {string} input - Der aktuelle Eingabetext.
 * @returns {string[]} Passende Vorschläge.
 */
function getTagSuggestions(input) {
  const all = [...new Set([...PRESET_TAGS, ...userTags])];
  const q = input.toLowerCase().trim();
  return all.filter(t =>
    !selectedTags.includes(t) && (q === '' || t.toLowerCase().includes(q))
  );
}

/**
 * Zeigt das Suggestions-Dropdown an.
 * @param {string} inputVal - Aktueller Texteingabewert.
 */
function showTagSuggestions(inputVal) {
  const suggestions = getTagSuggestions(inputVal);
  const box = document.getElementById('tag-suggestions');
  if (suggestions.length === 0) { box.classList.add('hidden'); return; }
  box.innerHTML = suggestions.map(t =>
    `<div class="tag-suggestion-item" onmousedown="addTag('${escapeHtml(t)}')">${escapeHtml(t)}</div>`
  ).join('');
  box.classList.remove('hidden');
}

/**
 * Versteckt das Suggestions-Dropdown (mit kurzer Verzögerung für onmousedown).
 */
function hideTagSuggestions() {
  setTimeout(() => document.getElementById('tag-suggestions').classList.add('hidden'), 150);
}

/**
 * Reagiert auf Tastatureingaben im Tag-Textfeld.
 * Enter oder Komma: aktuellen Text als Tag hinzufügen.
 * Backspace bei leerem Feld: letzten Tag entfernen.
 * @param {KeyboardEvent} event
 */
function onTagKeydown(event) {
  const input = document.getElementById('tag-text');
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault();
    const val = input.value.trim().replace(/,$/, '');
    if (val) addTag(val);
  } else if (event.key === 'Backspace' && input.value === '' && selectedTags.length > 0) {
    selectedTags.pop();
    renderTagBadgesInput();
  }
}

/**
 * Reagiert auf Texteingabe im Tag-Feld — aktualisiert Vorschläge.
 * @param {string} val - Aktueller Eingabewert.
 */
function onTagInput(val) {
  showTagSuggestions(val);
}

/**
 * Fügt einen Tag zur Auswahl hinzu (max. 8 Tags).
 * @param {string} tag - Der hinzuzufügende Tag.
 */
function addTag(tag) {
  const clean = tag.trim().slice(0, 50);
  if (!clean || selectedTags.includes(clean) || selectedTags.length >= 8) return;
  selectedTags.push(clean);
  renderTagBadgesInput();
  const input = document.getElementById('tag-text');
  input.value = '';
  document.getElementById('tag-suggestions').classList.add('hidden');
  input.focus();
}

/**
 * Entfernt einen Tag aus der aktuellen Auswahl.
 * @param {string} tag - Der zu entfernende Tag.
 */
function removeTag(tag) {
  selectedTags = selectedTags.filter(t => t !== tag);
  renderTagBadgesInput();
}

/**
 * Rendert die gewählten Tags als Badges im Eingabefeld.
 */
function renderTagBadgesInput() {
  document.getElementById('tag-badges-input').innerHTML = selectedTags.map(t =>
    `<span class="tag-badge-input">
      ${escapeHtml(t)}
      <button type="button" class="tag-badge-remove" onclick="removeTag('${escapeHtml(t)}')">&times;</button>
    </span>`
  ).join('');
}

// ─── Modal: Neue Session ──────────────────────────────────────────

/**
 * Öffnet das Modal zum Erstellen einer neuen Session.
 */
function openModal() {
  selectedTags = [];
  renderTagBadgesInput();
  document.getElementById('tag-text').value = '';
  document.getElementById('tag-suggestions').classList.add('hidden');
  document.getElementById('modal-overlay').classList.remove('hidden');
  document.getElementById('new-session-modal').classList.remove('hidden');
  document.getElementById('session-title').focus();
}

/**
 * Schließt das Neue-Session-Modal.
 */
function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('new-session-modal').classList.add('hidden');
  document.getElementById('session-error').classList.add('hidden');
}

/**
 * Erstellt eine neue Session mit Tags und lädt die Liste neu.
 * @param {SubmitEvent} event - Das Formular-Submit-Event.
 */
async function createSession(event) {
  event.preventDefault();
  const title    = document.getElementById('session-title').value.trim();
  const date     = document.getElementById('session-date').value;
  const videoUrl = document.getElementById('session-video-url').value.trim();
  const errEl    = document.getElementById('session-error');
  errEl.classList.add('hidden');

  // Noch getippten Tag (falls vorhanden) noch hinzufügen
  const pendingTag = document.getElementById('tag-text').value.trim();
  if (pendingTag) addTag(pendingTag);

  try {
    await Sessions.create(title, date, videoUrl, selectedTags);
    closeModal();
    document.getElementById('session-title').value = '';
    document.getElementById('session-video-url').value = '';
    selectedTags = [];
    renderTagBadgesInput();
    await loadSessions();
    await loadUserTags();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  }
}

/**
 * Löscht eine Session nach Bestätigung durch den Benutzer.
 * @param {MouseEvent} event     - Das Klick-Event.
 * @param {string}     sessionId - Die ID der zu löschenden Session.
 */
async function deleteSession(event, sessionId) {
  event.stopPropagation();
  if (!confirm('Session und alle Snapshots wirklich löschen?')) return;
  try {
    await Sessions.delete(sessionId);
    await loadSessions();
    await loadUserTags();
  } catch (err) {
    alert('Fehler beim Löschen: ' + err.message);
  }
}

/**
 * Öffnet eine Session in der Session-Ansicht.
 * @param {string} sessionId - Die ID der zu öffnenden Session.
 */
function openSession(sessionId) {
  window.location.href = `/session?id=${sessionId}`;
}

// ─── Snapshot-Suche ───────────────────────────────────────────────

/**
 * Durchsucht alle Snapshot-Notizen des Benutzers über die API.
 * @param {string} q - Der Suchbegriff.
 */
async function searchSnapshotNotes(q) {
  const container = document.getElementById('snapshot-results');
  if (!q) { clearSnapshotResults(); return; }
  container.innerHTML = '<div class="snapshot-search-loading">Notizen werden durchsucht…</div>';
  container.classList.remove('hidden');
  try {
    const results = await Snapshots.search(q);
    if (results.length === 0) { clearSnapshotResults(); return; }
    container.innerHTML = `
      <div class="snapshot-search-header">
        <span class="snapshot-search-title">📝 Gefunden in Notizen (${results.length})</span>
      </div>
      <div class="snapshot-search-grid">
        ${results.map(r => `
          <div class="snapshot-search-card" onclick="window.location.href='/session?id=${r.session_id}'">
            <div class="snapshot-search-thumb">
              <img src="https://img.youtube.com/vi/${r.session_youtube_id}/mqdefault.jpg" alt="" loading="lazy">
              <span class="snapshot-search-ts">⏱ ${r.timestamp_label}</span>
            </div>
            <div class="snapshot-search-body">
              <div class="snapshot-search-session">${escapeHtml(r.session_title)}</div>
              <div class="snapshot-search-notes">${highlightMatch(r.notes, q)}</div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (_) {
    clearSnapshotResults();
  }
}

/** Leert und versteckt den Snapshot-Ergebnisse-Container. */
function clearSnapshotResults() {
  const c = document.getElementById('snapshot-results');
  c.innerHTML = '';
  c.classList.add('hidden');
}

/**
 * Hebt den Suchbegriff im Text farbig hervor (XSS-sicher).
 * @param {string} text  - Originaltext.
 * @param {string} query - Suchbegriff.
 * @returns {string} HTML mit hervorgehobenen Treffern.
 */
function highlightMatch(text, query) {
  const escaped  = escapeHtml(text);
  const escapedQ = escapeHtml(query);
  const safeQ    = escapedQ.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return escaped.replace(new RegExp(`(${safeQ})`, 'gi'), '<mark>$1</mark>');
}

// ─── Hilfsfunktionen ──────────────────────────────────────────────

/**
 * Maskiert HTML-Sonderzeichen zur XSS-Prävention.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

/**
 * Formatiert ein ISO-Datum in deutsches Format (TT.MM.JJJJ).
 * @param {string} iso
 * @returns {string}
 */
function formatDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y}`;
}


// ─── ToS-Check beim Dashboard-Start ──────────────────────────────────────────

async function checkTosAccepted() {
  if (!getToken()) return;

  // Immer vom Server holen (localStorage kann veraltet sein)
  try {
    const freshUser = await Auth.me();
    localStorage.setItem('lt_user', JSON.stringify(freshUser));
    if (freshUser.tos_accepted) return;
  } catch (_) {
    return;
  }

  await showTosModal();
}

async function showTosModal() {
  // Warten bis DOM vollständig geladen
  await new Promise(resolve => {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      resolve();
    } else {
      document.addEventListener('DOMContentLoaded', resolve);
    }
  });
  const modal = document.getElementById('tosModal');
  if (!modal) { console.error('tosModal nicht gefunden'); return; }
  modal.classList.remove('hidden');
  try {
    const res = await fetch('/api/auth/tos');
    const data = await res.json();
    document.getElementById('tos-content').innerHTML = data.content;
  } catch (_) {
    document.getElementById('tos-content').innerHTML =
      '<p>Fehler beim Laden der Nutzungsbedingungen.</p>';
  }
}

async function acceptTos() {
  const btn = document.getElementById('tos-accept-btn');
  btn.disabled = true;
  btn.textContent = 'Wird gespeichert…';
  try {
    const user = await apiFetch('/api/auth/accept-tos', 'POST');
    localStorage.setItem('lt_user', JSON.stringify(user));
    document.getElementById('tosModal').classList.add('hidden');
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Zustimmen & fortfahren';
    alert('Fehler: ' + err.message);
  }
}
