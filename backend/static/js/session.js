/**
 * session.js – Logik für die Video-Session-Seite.
 *
 * Verwaltet den YouTube-Player, Snapshot-Erstellung,
 * manuellen Screenshot-Upload, Snapshot-Verwaltung, das Bearbeitungs-Modal
 * sowie den Export als Markdown und PDF.
 */

// Nicht angemeldete Benutzer zur Login-Seite
if (!getToken()) window.location.href = '/';

// Session-ID aus der URL lesen
const urlParams    = new URLSearchParams(window.location.search);
const SESSION_ID   = urlParams.get('id');
if (!SESSION_ID) window.location.href = '/dashboard';

/** @type {Object}  Aktuelle Session-Daten */
let sessionData = null;
/** @type {Array}   Liste aller Snapshots */
let snapshots   = [];
/** @type {Object}  Der aktive YouTube-Player */
let player      = null;
/** @type {string|null} ID des aktuell im Modal geöffneten Snapshots */
let modalSnapshotId = null;
/** @type {boolean} Ob ungespeicherte Änderungen im Modal vorhanden sind */
let isDirty = false;
/** @type {number}  Interval-ID für den Zeitanzeige-Timer */
let clockInterval = null;
/** @type {string|null} ID des Snapshots der auf einen Screenshot wartet */
let activePasteSnapshotId = null;

// ─── Initialisierung ──────────────────────────────────────────────

/** Seite initialisieren: Session laden, dann Player starten */
async function init() {
  try {
    sessionData = await Sessions.get(SESSION_ID);
    document.getElementById('session-title-display').textContent = sessionData.title;
    document.getElementById('session-date-display').textContent  = formatDate(sessionData.date);
    if (sessionData.video_title) {
      const vtEl = document.getElementById('video-title-display');
      vtEl.textContent = sessionData.video_title;
      vtEl.title = sessionData.video_title + (sessionData.channel_name ? ' — ' + sessionData.channel_name : '');
      vtEl.style.display = 'block';
    }
    snapshots = await Snapshots.list(SESSION_ID);
    renderSnapshots();
  } catch (err) {
    alert('Fehler: ' + err.message);
    window.location.href = '/dashboard';
  }
}

init();

// Globaler Paste-Handler für Screenshot-Upload
document.addEventListener('paste', async function(event) {
  // Normales Einfügen in Text-Felder nicht unterbrechen
  const tag = event.target.tagName;
  if (tag === 'TEXTAREA' || tag === 'INPUT') return;
  if (!activePasteSnapshotId) return;

  const items = event.clipboardData?.items;
  if (!items) return;

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault();
      const file = item.getAsFile();
      if (!file) continue;

      const snapId = activePasteSnapshotId;

      // Vorschau sofort anzeigen
      const reader = new FileReader();
      reader.onload = async function(e) {
        const dataUrl = e.target.result;

        const zone = document.getElementById(`paste-zone-${snapId}`);
        if (zone) {
          zone.innerHTML = `
            <img src="${dataUrl}" style="width:100%;height:100%;object-fit:cover;border-radius:5px;" alt="Vorschau">
            <div class="paste-uploading"><span class="frame-spinner"></span></div>`;
        }

        // An Backend senden
        const base64 = dataUrl.split(',')[1];
        try {
          const updated = await Snapshots.uploadFrame(snapId, base64);
          const idx = snapshots.findIndex(s => s.id === snapId);
          if (idx !== -1) snapshots[idx] = updated;
          activePasteSnapshotId = null;
          renderSnapshots();
          // Modal-Thumbnail aktualisieren wenn offen
          if (modalSnapshotId === snapId && updated.frame_url) {
            document.getElementById('modal-thumbnail').innerHTML =
              `<div style="position:relative;"><img src="${updated.frame_url}?t=${Date.now()}" alt="Video-Frame" style="width:100%;display:block;"></div>`;
          }
        } catch (err) {
          alert('Upload fehlgeschlagen: ' + err.message);
          activePasteSnapshotId = null;
          renderSnapshots();
        }
      };
      reader.readAsDataURL(file);
      break;
    }
  }
});

// ─── YouTube Player API ───────────────────────────────────────────

/**
 * Callback der YouTube IFrame API – wird aufgerufen wenn die API bereit ist.
 */
function onYouTubeIframeAPIReady() {
  if (!sessionData) {
    setTimeout(onYouTubeIframeAPIReady, 300);
    return;
  }
  player = new YT.Player('youtube-player', {
    videoId: sessionData.youtube_id,
    playerVars: { rel: 0, modestbranding: 1 },
    events: {
      onReady: () => { startClock(); },
    },
  });
}

/**
 * Startet den Timer der die aktuelle Videozeit anzeigt.
 */
function startClock() {
  clearInterval(clockInterval);
  clockInterval = setInterval(() => {
    if (player && player.getCurrentTime) {
      const sec = Math.floor(player.getCurrentTime());
      document.getElementById('current-time-display').textContent = formatSec(sec);
    }
  }, 500);
}

// ─── Snapshots ────────────────────────────────────────────────────

/**
 * Erstellt einen neuen Snapshot an der aktuellen Videoposition.
 * Pausiert das Video und aktiviert das Paste-Feld für einen Screenshot.
 */
async function createSnapshot() {
  if (!player || !player.getCurrentTime) {
    alert('Der Video-Player ist noch nicht bereit.');
    return;
  }
  const sec = Math.floor(player.getCurrentTime());

  // Video pausieren
  player.pauseVideo();

  // YouTube-Thumbnail als Standard-Bild
  const frame_url = `https://img.youtube.com/vi/${sessionData.youtube_id}/maxresdefault.jpg`;
  try {
    const snap = await Snapshots.create(SESSION_ID, sec, '', null, frame_url);
    snapshots.unshift(snap);
    snapshots.sort((a, b) => a.timestamp_sec - b.timestamp_sec);

    // Paste-Feld für diesen Snapshot aktivieren
    activePasteSnapshotId = snap.id;
    renderSnapshots();

    // Zur neuen Karte scrollen
    const card = document.getElementById(`snap-card-${snap.id}`);
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (err) {
    alert('Fehler beim Erstellen: ' + err.message);
  }
}

/**
 * Deaktiviert das Paste-Feld ohne Screenshot zu laden.
 */
function skipPaste() {
  activePasteSnapshotId = null;
  renderSnapshots();
}

/**
 * Rendert alle Snapshots als Karten in der Seitenleiste.
 */
function renderSnapshots() {
  const list = document.getElementById('snapshots-list');
  document.getElementById('snapshot-count').textContent = snapshots.length;

  if (snapshots.length === 0) {
    list.innerHTML = `<div class="empty-state">
      Noch keine Snapshots.<br>
      Klicke auf <strong>📸 Snapshot erstellen</strong> um einen hinzuzufügen.
    </div>`;
    return;
  }

  list.innerHTML = snapshots.map(s => {
    const isPasteActive = s.id === activePasteSnapshotId;
    const thumbSrc = s.frame_url || `https://img.youtube.com/vi/${sessionData.youtube_id}/mqdefault.jpg`;
    const isManual = s.frame_source === 'manual';

    const thumbArea = isPasteActive
      ? `<div class="paste-zone" id="paste-zone-${s.id}" onclick="event.stopPropagation()">
           <span class="paste-zone-icon">📋</span>
           <span class="paste-zone-text">Screenshot einfügen<br><kbd>Strg+V</kbd></span>
           <button class="paste-zone-skip" onclick="event.stopPropagation(); skipPaste()">Überspringen</button>
         </div>`
      : `<img src="${thumbSrc}" alt="Frame" loading="lazy"
             onerror="this.onerror=null;this.src='https://img.youtube.com/vi/${sessionData.youtube_id}/hqdefault.jpg'">
         ${isManual ? '<span class="frame-source-badge" title="Eigener Screenshot">✎</span>' : ''}`;

    return `
      <div class="snapshot-card${isPasteActive ? ' paste-active' : ''}" id="snap-card-${s.id}" onclick="openSnapshotModal('${s.id}')">
        <button class="snapshot-delete-btn" onclick="quickDelete(event,'${s.id}')" title="Löschen">✕</button>
        <div class="snapshot-card-thumb">
          ${thumbArea}
          <span class="snapshot-ts">${escapeHtml(s.timestamp_label)}</span>
        </div>
        <button class="snapshot-card-ts-btn" onclick="seekTo(event,${s.timestamp_sec})">
          ▶ ${escapeHtml(s.timestamp_label)}
        </button>
        <div class="snapshot-card-notes ${s.notes ? '' : 'empty'}">
          ${s.notes ? escapeHtml(s.notes) : 'Keine Notizen – klicken zum Bearbeiten'}
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Springt im Video zur angegebenen Position.
 * @param {MouseEvent} event   - Das Klick-Event (verhindert Modal-Öffnung).
 * @param {number}     seconds - Zielposition in Sekunden.
 */
function seekTo(event, seconds) {
  event.stopPropagation();
  if (player && player.seekTo) {
    player.seekTo(seconds, true);
    player.playVideo();
  }
}

/**
 * Löscht einen Snapshot direkt von der Karte (ohne Modal).
 * @param {MouseEvent} event      - Das Klick-Event.
 * @param {string}     snapshotId - Die ID des Snapshots.
 */
async function quickDelete(event, snapshotId) {
  event.stopPropagation();
  if (!confirm('Snapshot löschen?')) return;
  try {
    await Snapshots.delete(snapshotId);
    snapshots = snapshots.filter(s => s.id !== snapshotId);
    if (activePasteSnapshotId === snapshotId) activePasteSnapshotId = null;
    renderSnapshots();
  } catch (err) {
    alert('Fehler: ' + err.message);
  }
}

// ─── Snapshot-Modal ───────────────────────────────────────────────

/**
 * Öffnet das Vergrößerungs-Modal für einen Snapshot.
 * @param {string} snapshotId - Die ID des anzuzeigenden Snapshots.
 */
function openSnapshotModal(snapshotId) {
  const snap = snapshots.find(s => s.id === snapshotId);
  if (!snap) return;

  modalSnapshotId = snapshotId;
  isDirty = false;

  document.getElementById('modal-timestamp').textContent = snap.timestamp_label;
  document.getElementById('modal-notes').value = snap.notes;

  const thumbSrc = snap.frame_url
    ? `${snap.frame_url}${snap.frame_source === 'manual' ? '?t=' + Date.now() : ''}`
    : `https://img.youtube.com/vi/${sessionData.youtube_id}/hqdefault.jpg`;

  document.getElementById('modal-thumbnail').innerHTML = `
    <div style="position:relative;">
      <img src="${thumbSrc}" alt="Video-Frame" style="width:100%;display:block;"
           onerror="this.onerror=null;this.src='https://img.youtube.com/vi/${sessionData.youtube_id}/hqdefault.jpg'">
    </div>
  `;

  document.getElementById('modal-overlay').classList.remove('hidden');
  document.getElementById('snapshot-modal').classList.remove('hidden');
  document.getElementById('modal-notes').focus();
}

/**
 * Schließt das Snapshot-Modal (mit Hinweis bei ungespeicherten Änderungen).
 */
function closeSnapshotModal() {
  if (isDirty) {
    if (!confirm('Ungespeicherte Änderungen verwerfen?')) return;
  }
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('snapshot-modal').classList.add('hidden');
  modalSnapshotId = null;
  isDirty = false;
}

/** Markiert das Modal als "verändert" (ungespeichert). */
function markDirty() { isDirty = true; }

/**
 * Speichert die Notizen des aktuell geöffneten Snapshots.
 */
async function saveModalNotes() {
  if (!modalSnapshotId) return;
  const notes = document.getElementById('modal-notes').value;
  try {
    const updated = await Snapshots.update(modalSnapshotId, notes);
    const idx = snapshots.findIndex(s => s.id === modalSnapshotId);
    if (idx !== -1) snapshots[idx] = updated;
    renderSnapshots();
    isDirty = false;
    closeSnapshotModal();
  } catch (err) {
    alert('Fehler beim Speichern: ' + err.message);
  }
}

/**
 * Löscht den aktuell im Modal geöffneten Snapshot.
 */
async function deleteCurrentSnapshot() {
  if (!modalSnapshotId) return;
  if (!confirm('Snapshot wirklich löschen?')) return;
  try {
    await Snapshots.delete(modalSnapshotId);
    snapshots = snapshots.filter(s => s.id !== modalSnapshotId);
    if (activePasteSnapshotId === modalSnapshotId) activePasteSnapshotId = null;
    renderSnapshots();
    isDirty = false;
    closeSnapshotModal();
  } catch (err) {
    alert('Fehler beim Löschen: ' + err.message);
  }
}

/**
 * Springt zum Zeitstempel des Modal-Snapshots und schließt das Modal.
 */
function jumpToModalTimestamp() {
  const snap = snapshots.find(s => s.id === modalSnapshotId);
  if (!snap) return;
  if (player && player.seekTo) {
    player.seekTo(snap.timestamp_sec, true);
    player.playVideo();
  }
  closeSnapshotModal();
}

// ─── Export ───────────────────────────────────────────────────────

/**
 * Exportiert die aktuelle Session als Markdown-Datei (.md).
 */
function exportMarkdown() {
  if (!sessionData) return;

  const title    = sessionData.title;
  const date     = formatDate(sessionData.date);
  const tags     = sessionData.tags && sessionData.tags.length > 0
    ? sessionData.tags.join(', ')
    : '—';
  const videoUrl = sessionData.video_url;

  let md = `# ${title}\n\n`;
  md += `**Datum:** ${date}  \n`;
  md += `**Tags:** ${tags}  \n`;
  md += `**Video:** ${videoUrl}  \n\n`;
  md += `---\n\n`;
  md += `## Snapshots (${snapshots.length})\n\n`;

  if (snapshots.length === 0) {
    md += '_Keine Snapshots vorhanden._\n';
  } else {
    for (const snap of snapshots) {
      md += `### ⏱ ${snap.timestamp_label}\n\n`;
      md += snap.notes ? `${snap.notes}\n\n` : '_Keine Notizen._\n\n';
    }
  }

  const filename = title
    .replace(/[^\w\s\-äöüÄÖÜß]/g, '')
    .trim()
    .replace(/\s+/g, '-') + '.md';

  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Exportiert die aktuelle Session als PDF.
 */
function exportPdf() {
  if (!sessionData) return;

  const title    = sessionData.title;
  const date     = formatDate(sessionData.date);
  const tags     = sessionData.tags && sessionData.tags.length > 0
    ? sessionData.tags.map(t => `<span class="tag">${t}</span>`).join(' ')
    : '<em>—</em>';
  const videoUrl = sessionData.video_url;

  const snapshotsHtml = snapshots.length === 0
    ? '<p class="empty">Keine Snapshots vorhanden.</p>'
    : snapshots.map(snap => `
        <div class="snap">
          <div class="snap-ts">⏱ ${snap.timestamp_label}</div>
          ${snap.frame_url ? `<img src="${snap.frame_url}" style="width:100%;border-radius:6px;margin-bottom:8px;" alt="Frame">` : ''}
          <div class="snap-notes">${snap.notes
            ? snap.notes.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>')
            : '<em class="empty">Keine Notizen.</em>'
          }</div>
        </div>
      `).join('');

  const html = `<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <title>${title.replace(/</g,'&lt;')}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      font-size: 13px;
      color: #1a1a1a;
      max-width: 760px;
      margin: 32px auto;
      padding: 0 24px 48px;
    }
    h1 { font-size: 22px; margin-bottom: 12px; }
    .meta { color: #555; line-height: 2; margin-bottom: 20px; }
    .meta strong { color: #1a1a1a; }
    .tag { display:inline-block; font-size:11px; font-weight:600; background:#eee; border-radius:20px; padding:2px 8px; margin:0 2px; }
    hr { border: none; border-top: 2px solid #e0e0e0; margin: 20px 0; }
    h2 { font-size: 15px; color: #444; margin-bottom: 16px; }
    .snap { border:1px solid #ddd; border-radius:8px; padding:14px 16px; margin-bottom:14px; page-break-inside:avoid; }
    .snap-ts { font-family:monospace; font-size:13px; font-weight:700; color:#c0392b; margin-bottom:8px; }
    .snap-notes { font-size:13px; line-height:1.7; color:#333; }
    .empty { color:#999; font-style:italic; }
    .footer { margin-top:32px; font-size:11px; color:#bbb; border-top:1px solid #eee; padding-top:12px; }
    @media print { body { margin:0; } }
  </style>
</head>
<body>
  <h1>${title.replace(/</g,'&lt;')}</h1>
  <div class="meta">
    <strong>Datum:</strong> ${date}<br>
    <strong>Tags:</strong> ${tags}<br>
    <strong>Video:</strong> <a href="${videoUrl}">${videoUrl}</a>
  </div>
  <hr>
  <h2>Snapshots (${snapshots.length})</h2>
  ${snapshotsHtml}
  <div class="footer">Exportiert mit LernyTube · lernytube.eiskopani.de</div>
  <script>window.onload = function() { window.print(); }<\/script>
</body>
</html>`;

  const win = window.open('', '_blank');
  if (!win) { alert('Bitte erlaube Popups für diese Seite, um den PDF-Export zu nutzen.'); return; }
  win.document.write(html);
  win.document.close();
}

// ─── Hilfsfunktionen ──────────────────────────────────────────────

/**
 * Konvertiert Sekunden in das Format M:SS oder H:MM:SS.
 * @param {number} sec - Die Anzahl der Sekunden.
 * @returns {string} Formatierter Zeitstempel.
 */
function formatSec(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${m}:${String(s).padStart(2,'0')}`;
}

/**
 * Formatiert ein ISO-Datum in deutsches Format (TT.MM.JJJJ).
 * @param {string} iso - Datum im Format YYYY-MM-DD.
 * @returns {string} Datum im Format TT.MM.JJJJ.
 */
function formatDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y}`;
}

/**
 * Maskiert HTML-Sonderzeichen zur XSS-Prävention.
 * @param {string} str - Die zu maskierende Zeichenkette.
 * @returns {string} Die maskierte Zeichenkette.
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}
