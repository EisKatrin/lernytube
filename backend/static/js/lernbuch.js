/**
 * lernbuch.js – KI-Lehrer und automatisch sortiertes Lernbuch.
 */

const user = getCurrentUser();
if (user) document.getElementById('username-display').textContent = user.username;

let bookTree = [];
let selectedTopicId = null; // null = "Alle Themen"

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

/**
 * Sehr einfache Markdown-Darstellung für Lehrer-Antworten
 * (Zeilenumbrüche, **fett**, `code`). Arbeitet auf bereits escapetem Text.
 * @param {string} text
 * @returns {string}
 */
function renderAnswer(text) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
}

function countEntries(node) {
  return node.entries.length + node.children.reduce((sum, c) => sum + countEntries(c), 0);
}

function findNode(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n;
    const found = findNode(n.children, id);
    if (found) return found;
  }
  return null;
}

function collectEntries(node) {
  let list = node.entries.map(e => ({ entry: e, topicTitle: node.title }));
  node.children.forEach(c => { list = list.concat(collectEntries(c)); });
  return list;
}

function collectAllEntries(nodes) {
  let list = [];
  nodes.forEach(n => { list = list.concat(collectEntries(n)); });
  return list;
}

function sortByDate(items) {
  return items.slice().sort((a, b) => new Date(a.entry.created_at) - new Date(b.entry.created_at));
}

async function loadBook() {
  try {
    bookTree = await Tutor.getBook();
  } catch (err) {
    document.getElementById('topic-tree').innerHTML =
      `<div class="empty-state">Nicht verfügbar: ${escapeHtml(err.message)}</div>`;
    document.getElementById('book-entries').innerHTML = '';
    document.querySelector('.ask-bar').classList.add('hidden');
    return;
  }
  renderSidebar();
  renderEntries();
}

function renderSidebar() {
  const container = document.getElementById('topic-tree');
  const allActiveClass = selectedTopicId === null ? ' active' : '';
  let html = `<div class="topic-node topic-all${allActiveClass}" onclick="selectTopic(null)">
    <span class="topic-node-title">📚 Alle Themen</span>
    <span class="count-badge">${collectAllEntries(bookTree).length}</span>
  </div>`;

  if (bookTree.length === 0) {
    html += '<div class="empty-state">Noch keine Themen — stell einfach eine Frage.</div>';
  } else {
    html += renderTopicList(bookTree, 1);
  }
  container.innerHTML = html;
}

function renderTopicList(nodes, level) {
  return nodes.map(node => {
    const activeClass = selectedTopicId === node.id ? ' active' : '';
    const count = countEntries(node);
    let html = `<div class="topic-node${activeClass}" style="padding-left:${0.9 + level * 0.75}rem" onclick="selectTopic('${node.id}')">
      <span class="topic-node-title">${escapeHtml(node.title)}</span>
      <span class="count-badge">${count}</span>
    </div>`;
    if (node.children.length) html += renderTopicList(node.children, level + 1);
    return html;
  }).join('');
}

function selectTopic(id) {
  selectedTopicId = id;
  renderSidebar();
  renderEntries();
}

function renderEntries() {
  const container = document.getElementById('book-entries');
  let items;
  if (selectedTopicId === null) {
    items = sortByDate(collectAllEntries(bookTree));
  } else {
    const node = findNode(bookTree, selectedTopicId);
    items = node ? sortByDate(collectEntries(node)) : [];
  }

  if (items.length === 0) {
    container.innerHTML = '<div class="empty-state">Noch keine Einträge in diesem Thema.</div>';
    return;
  }

  container.innerHTML = items.map(({ entry, topicTitle }) => `
    <div class="qa-card">
      <div class="qa-topic-label">${escapeHtml(topicTitle)}</div>
      <div class="qa-question">❓ ${escapeHtml(entry.question)}</div>
      <div class="qa-answer">${renderAnswer(entry.answer)}</div>
      <div class="qa-meta">
        <span>${formatDate(entry.created_at)}</span>
        <button class="btn-icon" title="Eintrag löschen" onclick="deleteEntry('${entry.id}')">🗑</button>
      </div>
    </div>
  `).join('');

  container.scrollTop = container.scrollHeight;
}

async function deleteEntry(id) {
  if (!confirm('Diesen Eintrag wirklich löschen?')) return;
  try {
    await Tutor.deleteEntry(id);
    await loadBook();
  } catch (err) {
    alert('Fehler: ' + err.message);
  }
}

async function handleAsk(event) {
  event.preventDefault();
  const input = document.getElementById('ask-input');
  const btn = document.getElementById('ask-submit-btn');
  const errorEl = document.getElementById('ask-error');
  const question = input.value.trim();
  if (!question) return;

  errorEl.classList.add('hidden');
  btn.disabled = true;
  btn.textContent = 'Der Lehrer denkt nach…';

  try {
    const entry = await Tutor.ask(question);
    input.value = '';
    await loadBook();
    selectTopic(entry.topic_id);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Fragen';
  }
}

loadBook();
