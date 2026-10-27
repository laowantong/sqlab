'use strict';

let sessionId = null;
let editor = null;
let currentToken = null;

// ── Session management ─────────────────────────────────────────────────────

async function initSession() {
  sessionId = localStorage.getItem('session_id');
  if (!sessionId) {
    const data = await apiFetch('/api/session');
    sessionId = data.session_id;
    localStorage.setItem('session_id', sessionId);
  }
}

function updateSession(returnedId) {
  if (returnedId && returnedId !== sessionId) {
    sessionId = returnedId;
    localStorage.setItem('session_id', sessionId);
  }
}

// ── API helpers ────────────────────────────────────────────────────────────

async function apiFetch(url, options) {
  const resp = await fetch(url, options);
  return resp.json();
}

// ── Mission panel ──────────────────────────────────────────────────────────

// A wrong-answer decrypt starts with this character
const WRONG_ANSWER_PREFIX = '🔴';

async function decryptAndShow(token) {
  const data = await apiFetch(`/api/decrypt/${token}?session_id=${sessionId}`);
  updateSession(data.session_id);

  const msg = data.error ? ('⚠️ ' + data.error) : (data.message || '');
  const isWrongAnswer = msg.startsWith(WRONG_ANSWER_PREFIX);

  if (isWrongAnswer) {
    // Don't overwrite the mission — show a friendly nudge in the results area
    showWrongAnswerFeedback(
      "Not quite — that token doesn't match any known answer.\n\n" +
      "Re-read the statement and double-check your formula. " +
      "The hint below can help if you're stuck."
    );
    return;
  }

  // Valid mission: clear the editor and update left panel
  editor.setValue('');
  document.getElementById('mission-text').textContent = msg;

  // Hint
  const hint = data.hint || '';
  const hintContainer = document.getElementById('hint-container');
  const hintText = document.getElementById('hint-text');
  const hintBtn = document.getElementById('btn-hint-toggle');
  if (hint) {
    hintText.textContent = hint;
    hintText.style.display = 'none';
    hintBtn.textContent = '💡 Show Hint';
    hintContainer.style.display = 'block';
  } else {
    hintContainer.style.display = 'none';
  }

  setUnlockButton(null);
}

function showWrongAnswerFeedback(msg) {
  const container = document.getElementById('results-container');
  const banner = `<div class="wrong-answer-banner">${escHtml(msg)}</div>`;
  // Prepend above existing results so the table stays visible
  container.innerHTML = banner + container.innerHTML;
}

// ── Query execution ────────────────────────────────────────────────────────

async function runQuery() {
  const sql = editor.getValue().trim();
  if (!sql) return;

  const resultsEl = document.getElementById('results-container');
  resultsEl.innerHTML = '<span style="color:var(--muted);font-size:0.8rem">Running…</span>';
  setUnlockButton(null);

  const data = await apiFetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql, session_id: sessionId }),
  });
  updateSession(data.session_id);
  renderResults(data);
}

// ── Results rendering ──────────────────────────────────────────────────────

function renderResults(data) {
  const container = document.getElementById('results-container');

  if (data.error) {
    container.innerHTML = `<div class="error-banner">${escHtml(data.error)}</div>`;
    setUnlockButton(null);
    return;
  }

  if (!data.columns || data.columns.length === 0) {
    container.innerHTML = '<div class="success-banner">✓ Statement executed successfully.</div>';
    setUnlockButton(null);
    return;
  }

  const tokenIdx = data.columns.findIndex(c => c.toLowerCase() === 'token');

  let html = '<table class="results-table"><thead><tr>';
  for (const col of data.columns) {
    html += `<th>${escHtml(col)}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const row of data.rows) {
    html += '<tr>';
    for (let i = 0; i < row.length; i++) {
      const val = row[i] === null ? '<em style="color:var(--muted)">NULL</em>' : escHtml(String(row[i]));
      const cls = i === tokenIdx ? ' class="token-cell"' : '';
      html += `<td${cls}>${val}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  html += `<div class="row-count">${data.rows.length} row${data.rows.length !== 1 ? 's' : ''}</div>`;

  container.innerHTML = html;

  // Auto-detect token column → show Unlock button
  if (tokenIdx >= 0 && data.rows.length > 0 && data.rows[0][tokenIdx] !== null) {
    setUnlockButton(data.rows[0][tokenIdx]);
  } else {
    setUnlockButton(null);
  }
}

function setUnlockButton(token) {
  currentToken = token;
  const btn = document.getElementById('btn-unlock');
  btn.style.display = token !== null ? 'inline-block' : 'none';
}

// ── Utilities ──────────────────────────────────────────────────────────────

function escHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Event listeners ────────────────────────────────────────────────────────

document.getElementById('btn-run').addEventListener('click', runQuery);

document.getElementById('btn-unlock').addEventListener('click', () => {
  if (currentToken !== null) decryptAndShow(currentToken);
});

document.getElementById('btn-hint-toggle').addEventListener('click', () => {
  const hintText = document.getElementById('hint-text');
  const btn = document.getElementById('btn-hint-toggle');
  const visible = hintText.style.display !== 'none';
  hintText.style.display = visible ? 'none' : 'block';
  btn.textContent = visible ? '💡 Show Hint' : '💡 Hide Hint';
});

document.getElementById('btn-new-session').addEventListener('click', () => {
  localStorage.removeItem('session_id');
  location.reload();
});

// ── Boot ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  editor = CodeMirror.fromTextArea(document.getElementById('sql-editor'), {
    mode: 'text/x-sql',
    theme: 'dracula',
    lineNumbers: true,
    matchBrackets: true,
    lineWrapping: true,
    extraKeys: {
      'Ctrl-Enter': runQuery,
      'Cmd-Enter': runQuery,
    },
  });

  await initSession();
  await decryptAndShow(42);
});
