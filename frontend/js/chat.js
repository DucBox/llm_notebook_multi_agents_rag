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

  // ── Helpers ──────────────────────────────────────────────
  function _esc(str) {
    return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function _scrollBottom() {
    const el = document.getElementById('messages');
    el.scrollTop = el.scrollHeight;
  }

  // ── Compact UI blocks ────────────────────────────────────
  function _showCompactingIndicator() {
    const el = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = 'compact-divider';
    div.id = 'compacting-indicator';
    div.innerHTML = `
      <span class="compact-dots">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </span>
      Đang compact context…
    `;
    el.appendChild(div);
    _scrollBottom();
    return div;
  }

  function _replaceWithDoneBlock(indicatorEl, compactedHistory) {
    const container = document.createElement('div');
    container.className = 'compact-done-block';

    const badge = document.createElement('div');
    badge.className = 'compact-divider done';
    badge.textContent = '— Context đã được compact —';
    container.appendChild(badge);

    if (compactedHistory) {
      const toggle = document.createElement('div');
      toggle.className = 'compact-history-toggle';
      toggle.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        Xem nội dung đã tóm tắt
      `;
      const body = document.createElement('div');
      body.className = 'compact-history-body';
      body.innerHTML = `<div class="md-body">${marked.parse(compactedHistory)}</div>`;

      toggle.addEventListener('click', () => {
        toggle.classList.toggle('open');
        body.classList.toggle('open');
      });

      container.appendChild(toggle);
      container.appendChild(body);
    }

    indicatorEl.replaceWith(container);
    _scrollBottom();
  }

  // ── Rebuild messages area after compact ──────────────────
  async function _reloadAfterCompact(usagePct, totalTokens, contextLimit) {
    const [conv, messages] = await Promise.all([
      API.listConversations().then(list => list.find(c => c.id === _convId)),
      API.getMessages(_convId),
    ]);

    const msgEl = document.getElementById('messages');
    msgEl.innerHTML = '';

    const indicator = _showCompactingIndicator();

    // Small delay so user sees the "compacting..." state briefly
    await new Promise(r => setTimeout(r, 400));

    // Re-render only active (non-compacted) messages
    messages.forEach(m => {
      if (!m.is_compacted) _appendMessage(m.role, m.content, m.sources ?? []);
    });

    _replaceWithDoneBlock(indicator, conv?.compacted_history ?? null);
    _updateCircle(usagePct);
    Sessions.updateTokenDisplay(_convId, totalTokens, contextLimit, usagePct);
  }

  // ── Message rendering ────────────────────────────────────
  function _renderSources(sources) {
    if (!sources || !sources.length) return '';
    const items = sources.map((s, i) => `
      <div class="source-chip">
        <div class="source-chip-header" onclick="Chat._toggleChip(this)">
          <span class="source-chip-label">
            <svg class="source-chip-caret" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            [${i+1}] ${_esc(s.document_filename)}${s.page_number ? ` · Trang ${s.page_number}` : ''}
          </span>
          <span class="source-chip-score">${s.rerank_score != null ? s.rerank_score : s.score}</span>
        </div>
        <div class="source-chip-body">
          <div class="source-chip-text md-body">${marked.parse(s.text_content)}</div>
          <button class="source-open-doc" onclick="Documents.openPreviewById('${s.document_id}')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
              <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            Xem tài liệu gốc
          </button>
        </div>
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

  function _toggleChip(header) {
    const chip = header.closest('.source-chip');
    chip.classList.toggle('open');
  }

  function _appendMessage(role, content, sources, elapsed) {
    const el = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `msg-row ${role}`;
    const body = role === 'assistant'
      ? `<div class="md-body">${marked.parse(content)}</div>`
      : `<div class="user-text">${_esc(content)}</div>`;
    const timing = (role === 'assistant' && elapsed != null)
      ? `<div class="msg-timing">Response in ${elapsed}s</div>`
      : '';
    div.innerHTML = `
      <div class="msg-bubble">
        ${body}
        ${role === 'assistant' ? _renderSources(sources) : ''}
        ${timing}
      </div>
    `;
    el.appendChild(div);
    _scrollBottom();
    return div;
  }

  function _showTyping() {
    const el = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = 'msg-row assistant msg-typing';
    div.id = 'typing-indicator';
    div.innerHTML = '<div class="msg-bubble"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
    el.appendChild(div);
    _scrollBottom();
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

      // Show compact history block if exists (from previous compact)
      if (conv?.compacted_history) {
        const placeholder = document.createElement('div');
        msgEl.appendChild(placeholder);
        _replaceWithDoneBlock(placeholder, conv.compacted_history);
      }

      messages.forEach(m => {
        if (!m.is_compacted) _appendMessage(m.role, m.content, m.sources ?? []);
      });

      if (conv) _updateCircle(conv.usage_pct);
    } catch (err) {
      msgEl.innerHTML = `<div class="empty-hint">Lỗi tải lịch sử: ${_esc(err.message)}</div>`;
    }
  }

  // ── Send message ─────────────────────────────────────────
  async function send(query) {
    if (!_convId || _sending || !query.trim()) return;
    _sending = true;

    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;

    const rerank      = document.getElementById('rerank-select').value === 'true';
    const modelVal    = document.getElementById('model-select').value;
    const model       = modelVal || null;
    const documentIds = Documents.getSelectedIds();

    _appendMessage('user', query, null);
    _showTyping();

    const t0 = performance.now();
    try {
      const res = await API.chat(_convId, {
        query,
        rerank,
        model,
        document_ids: documentIds,
        top_n: 10,
        retrieve_n: 20,
      });

      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      _removeTyping();
      _appendMessage('assistant', res.answer, res.sources, elapsed);
      _updateCircle(res.usage_pct);
      Sessions.updateTokenDisplay(_convId, res.total_token_count, res.context_limit_tokens, res.usage_pct);

      if (res.compacting_triggered) {
        await _reloadAfterCompact(res.usage_pct, res.total_token_count, res.context_limit_tokens);
      }
    } catch (err) {
      _removeTyping();
      _appendMessage('assistant', `⚠ Lỗi: ${err.message}`, null);
    } finally {
      _sending = false;
      sendBtn.disabled = false;
    }
  }

  // ── Manual compact ───────────────────────────────────────
  async function manualCompact() {
    if (!_convId || _sending) return;
    const btn = document.getElementById('compact-btn');
    btn.style.opacity = '.5';
    btn.style.pointerEvents = 'none';

    const indicator = _showCompactingIndicator();

    try {
      const res = await API.compact(_convId);
      await _reloadAfterCompact(res.usage_pct, res.total_token_count, res.context_limit_tokens);
      // _reloadAfterCompact rebuilds entire message area including the done block
      // but the indicator was appended before reload, so it's gone — that's fine
    } catch (err) {
      indicator?.remove();
      alert(`Không compact được: ${err.message}`);
    } finally {
      btn.style.opacity = '';
      btn.style.pointerEvents = '';
    }
  }

  function init() {
    const input   = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 160) + 'px';
    });

    // !e.isComposing: don't send while IME is still composing (Vietnamese/CJK input)
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        const query = input.value;
        input.value = '';
        input.style.height = 'auto';
        send(query);
      }
    });

    sendBtn.addEventListener('click', () => {
      const query = input.value;
      input.value = '';
      input.style.height = 'auto';
      send(query);
    });
    document.getElementById('compact-btn').addEventListener('click', manualCompact);
  }

  return { init, loadConversation, _toggleSources, _toggleChip };
})();
