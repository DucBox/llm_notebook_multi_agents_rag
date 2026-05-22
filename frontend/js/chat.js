const Chat = (() => {
  let _convId = null;
  let _sending = false;

  // ── Token circle ─────────────────────────────────────────
  function _updateCircle(usagePct) {
    const arc  = document.getElementById('token-arc');
    const pct  = document.getElementById('token-pct');
    const clamped = Math.min(usagePct, 100);
    arc.setAttribute('stroke-dasharray', `${clamped} 100`);
    pct.textContent = `${Math.round(clamped)}%`;

    arc.classList.remove('warn', 'crit');
    if (clamped >= 80) arc.classList.add('crit');
    else if (clamped >= 60) arc.classList.add('warn');
  }

  // ── Message rendering ────────────────────────────────────
  function _esc(str) {
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function _renderSources(sources) {
    if (!sources || !sources.length) return '';
    const items = sources.map((s, i) => `
      <div class="source-chip">
        <div class="source-chip-header">
          [${i+1}] ${_esc(s.document_filename)}${s.page_number ? ` · Trang ${s.page_number}` : ''}
          <span style="font-weight:400;color:var(--text-muted);margin-left:8px;">
            ${s.rerank_score != null ? `score: ${s.rerank_score}` : `score: ${s.score}`}
          </span>
        </div>
        <div class="source-chip-text">${_esc(s.text_content)}</div>
      </div>
    `).join('');

    return `
      <div class="msg-sources">
        <div class="sources-toggle" onclick="Chat._toggleSources(this)">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          ${sources.length} nguồn tham khảo
        </div>
        <div class="sources-list">${items}</div>
      </div>
    `;
  }

  function _toggleSources(btn) {
    btn.classList.toggle('open');
    btn.nextElementSibling.classList.toggle('open');
  }

  function _appendMessage(role, content, sources) {
    const el = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `msg-row ${role}`;
    const body = role === 'assistant'
      ? `<div class="md-body">${marked.parse(content)}</div>`
      : `<div class="user-text">${_esc(content)}</div>`;
    div.innerHTML = `
      <div class="msg-bubble">
        ${body}
        ${role === 'assistant' ? _renderSources(sources) : ''}
      </div>
    `;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
    return div;
  }

  function _showTyping() {
    const el = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = 'msg-row assistant msg-typing';
    div.id = 'typing-indicator';
    div.innerHTML = '<div class="msg-bubble"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
  }

  function _removeTyping() {
    document.getElementById('typing-indicator')?.remove();
  }

  // ── Load conversation history ────────────────────────────
  async function loadConversation(convId) {
    _convId = convId;
    const msgEl = document.getElementById('messages');
    msgEl.innerHTML = '';
    _updateCircle(0);
    document.getElementById('token-pct').textContent = '…';

    try {
      const [messages, conv] = await Promise.all([
        API.getMessages(convId),
        API.listConversations().then(list => list.find(c => c.id === convId)),
      ]);

      messages.forEach(m => {
        if (!m.is_compacted) _appendMessage(m.role, m.content, []);
      });

      if (conv) _updateCircle(
        Math.round(conv.total_token_count / (conv.total_token_count || 1) * 0) // will update on next chat
      );
    } catch (err) {
      msgEl.innerHTML = `<div class="empty-hint">Lỗi tải lịch sử: ${_esc(err.message)}</div>`;
    }
  }

  // ── Send message ─────────────────────────────────────────
  async function send(query) {
    if (!_convId || _sending || !query.trim()) return;
    _sending = true;

    const sendBtn = document.getElementById('send-btn');
    const input   = document.getElementById('chat-input');
    sendBtn.disabled = true;
    input.value = '';
    input.style.height = 'auto';

    const rerank      = document.getElementById('rerank-select').value === 'true';
    const documentIds = Documents.getSelectedIds();

    _appendMessage('user', query, null);
    _showTyping();

    try {
      const res = await API.chat(_convId, {
        query,
        rerank,
        document_ids: documentIds,
        top_n: 5,
        retrieve_n: rerank ? 10 : 5,
      });

      _removeTyping();
      _appendMessage('assistant', res.answer, res.sources);
      _updateCircle(res.usage_pct);
      Sessions.updateTokenDisplay(_convId, res.total_token_count, res.context_limit_tokens, res.usage_pct);

      if (res.compacting_triggered) {
        _showCompactBadge();
      }
    } catch (err) {
      _removeTyping();
      _appendMessage('assistant', `⚠ Lỗi: ${err.message}`, null);
    } finally {
      _sending = false;
      sendBtn.disabled = false;
    }
  }

  function _showCompactBadge() {
    const el = document.getElementById('messages');
    const div = document.createElement('div');
    div.style.cssText = 'text-align:center;padding:8px;font-size:12px;color:var(--text-muted);';
    div.textContent = '— Lịch sử đã được compact tự động —';
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
  }

  // ── Manual compact ───────────────────────────────────────
  async function manualCompact() {
    if (!_convId) return;
    const btn = document.getElementById('compact-btn');
    btn.style.opacity = '.5';
    btn.style.pointerEvents = 'none';
    try {
      const res = await API.compact(_convId);
      _updateCircle(res.usage_pct);
      _showCompactBadge();
      Sessions.updateTokenDisplay(_convId, res.total_token_count, res.context_limit_tokens, res.usage_pct);
    } catch (err) {
      alert(`Không compact được: ${err.message}`);
    } finally {
      btn.style.opacity = '';
      btn.style.pointerEvents = '';
    }
  }

  function init() {
    const input   = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    // Auto-grow textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 160) + 'px';
    });

    // Send on Enter (Shift+Enter = newline)
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send(input.value);
      }
    });

    sendBtn.addEventListener('click', () => send(input.value));
    document.getElementById('compact-btn').addEventListener('click', manualCompact);
  }

  return { init, loadConversation, _toggleSources };
})();
