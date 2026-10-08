/**
 * klassenzimmer.js – Lehrer-Auswahl und Chat mit den Lehrer-Agenten.
 */

const user = getCurrentUser();
if (user) document.getElementById('username-display').textContent = user.username;

let currentAgentId = null;
let currentAgentTitle = null;

/**
 * Escaped einen String für die sichere Anzeige als HTML-Text.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/** Sehr einfache Markdown-Darstellung (Zeilenumbrüche, **fett**, `code`). */
function renderAnswer(text) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

async function loadAgents() {
  const grid = document.getElementById('agent-grid');
  try {
    const agents = await Klassenzimmer.listAgents();
    if (agents.length === 0) {
      grid.innerHTML = '<div class="empty-state">Noch kein Lehrer verfügbar.</div>';
      return;
    }
    grid.innerHTML = agents.map(a => `
      <div class="agent-card" onclick="openChat('${a.agent_id}', '${escapeHtml(a.display_name)}')">
        <div class="agent-card-title">${escapeHtml(a.display_name)}</div>
        <div class="agent-card-desc">${escapeHtml(a.kurzbeschreibung)}</div>
      </div>
    `).join('');
  } catch (err) {
    grid.innerHTML = `<div class="empty-state">Nicht verfügbar: ${escapeHtml(err.message)}</div>`;
  }
}

async function openChat(agentId, displayName) {
  currentAgentId = agentId;
  currentAgentTitle = displayName;
  document.getElementById('chat-agent-title').textContent = displayName;
  document.getElementById('agent-picker-view').classList.add('hidden');
  document.getElementById('chat-view').classList.remove('hidden');

  const thread = document.getElementById('chat-thread');
  thread.innerHTML = '<div class="loading-state">Lade Gespräch…</div>';
  try {
    const history = await Klassenzimmer.history(agentId);
    renderThread(history.messages);
  } catch (err) {
    thread.innerHTML = `<div class="empty-state">Nicht verfügbar: ${escapeHtml(err.message)}</div>`;
  }
}

function backToPicker() {
  currentAgentId = null;
  document.getElementById('chat-view').classList.add('hidden');
  document.getElementById('agent-picker-view').classList.remove('hidden');
}

function renderThread(messages) {
  const thread = document.getElementById('chat-thread');
  if (!messages || messages.length === 0) {
    thread.innerHTML = `<div class="empty-state">Stell ${escapeHtml(currentAgentTitle)} deine erste Frage.</div>`;
    return;
  }
  thread.innerHTML = messages.map(m => `
    <div class="chat-bubble ${m.role}">${renderAnswer(m.content)}</div>
  `).join('');
  thread.scrollTop = thread.scrollHeight;
}

async function handleChatSubmit(event) {
  event.preventDefault();
  const input = document.getElementById('chat-input');
  const btn = document.getElementById('chat-submit-btn');
  const errorEl = document.getElementById('chat-error');
  const message = input.value.trim();
  if (!message || !currentAgentId) return;

  errorEl.classList.add('hidden');
  btn.disabled = true;
  btn.textContent = `${currentAgentTitle} denkt nach…`;

  const thread = document.getElementById('chat-thread');
  const emptyState = thread.querySelector('.empty-state');
  if (emptyState) thread.innerHTML = '';
  thread.insertAdjacentHTML('beforeend', `<div class="chat-bubble user">${renderAnswer(message)}</div>`);
  thread.scrollTop = thread.scrollHeight;
  input.value = '';

  try {
    const resp = await Klassenzimmer.chat(currentAgentId, message);
    thread.insertAdjacentHTML('beforeend', `<div class="chat-bubble assistant">${renderAnswer(resp.reply)}</div>`);
    thread.scrollTop = thread.scrollHeight;
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Senden';
  }
}

loadAgents();
