const Sessions = (() => {
  let _sessions = [];
  let _activeId = null;
  let _onSelect = null; // callback(conversationId)

  function _formatDate(isoStr) {
    const d = new Date(isoStr);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'Vừa xong';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} phút trước`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} giờ trước`;
    return d.toLocaleDateString('vi-VN');
  }

  function _render() {
    const el = document.getElementById('session-list');
    if (!_sessions.length) {
      el.innerHTML = '<div class="empty-hint">Chưa có phiên nào</div>';
      return;
    }
    el.innerHTML = _sessions.map(s => `
      <div class="session-item ${s.id === _activeId ? 'active' : ''}" data-id="${s.id}">
        <svg class="session-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        </svg>
        <div class="session-info">
          <div class="session-date">${_formatDate(s.updated_at)}</div>
          <div class="session-preview">${s.total_token_count} tokens</div>
        </div>
        <button class="session-delete" data-id="${s.id}" title="Xoá phiên">×</button>
      </div>
    `).join('');

    el.querySelectorAll('.session-item').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.classList.contains('session-delete')) return;
        const id = row.dataset.id;
        _setActive(id);
        if (_onSelect) _onSelect(id);
      });
    });

    el.querySelectorAll('.session-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        if (!confirm('Xoá phiên chat này?')) return;
        try {
          await API.deleteConversation(id);
          if (_activeId === id) {
            _activeId = null;
            if (_onSelect) _onSelect(null);
          }
          await refresh();
        } catch (err) {
          alert(`Lỗi: ${err.message}`);
        }
      });
    });
  }

  function _setActive(id) {
    _activeId = id;
    document.querySelectorAll('.session-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === id);
    });
  }

  async function refresh() {
    try {
      _sessions = await API.listConversations() ?? [];
    } catch { _sessions = []; }
    _render();
  }

  async function createNew() {
    const conv = await API.createConversation();
    await refresh();
    _setActive(conv.id);
    if (_onSelect) _onSelect(conv.id);
    return conv;
  }

  function updateTokenDisplay(convId, totalTokens, contextLimit, usagePct) {
    // Update session preview in sidebar
    const item = document.querySelector(`.session-item[data-id="${convId}"] .session-preview`);
    if (item) item.textContent = `${totalTokens} tokens`;
  }

  function init(onSelectCallback) {
    _onSelect = onSelectCallback;

    document.getElementById('new-session-btn').addEventListener('click', async () => {
      try { await createNew(); }
      catch (err) { alert(`Không tạo được phiên: ${err.message}`); }
    });

    refresh();
  }

  return { init, refresh, createNew, updateTokenDisplay, getActiveId: () => _activeId };
})();
