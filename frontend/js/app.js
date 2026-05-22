// ── Bootstrap ────────────────────────────────────────────
(function () {
  if (!requireAuth()) return;

  // Show user email
  const emailEl = document.getElementById('user-email');
  if (emailEl) emailEl.textContent = localStorage.getItem('userEmail') ?? '';

  // Logout
  document.getElementById('logout-btn').addEventListener('click', logout);

  // Sidebar toggle
  document.getElementById('sidebar-toggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('collapsed');
  });

  // When a session is selected
  function onSessionSelect(convId) {
    const emptyEl  = document.getElementById('chat-empty');
    const activeEl = document.getElementById('chat-active');
    if (!convId) {
      emptyEl.classList.remove('hidden');
      activeEl.classList.add('hidden');
      return;
    }
    emptyEl.classList.add('hidden');
    activeEl.classList.remove('hidden');
    Chat.loadConversation(convId);
  }

  // Populate model dropdown — switches based on Online/Offline mode
  let _models = { online: [], offline: [] };

  function _populateModelSelect(mode) {
    const sel = document.getElementById('model-select');
    const list = mode === 'offline' ? _models.offline : _models.online;
    if (!list.length) {
      sel.innerHTML = `<option value="">– ${mode === 'offline' ? 'Offline không có model' : 'Không rõ'} –</option>`;
    } else {
      sel.innerHTML = list.map(m => `<option value="${m}">${m}</option>`).join('');
    }
  }

  API.getModels().then(data => {
    _models = data;
    _populateModelSelect('online'); // default mode is online
  }).catch(() => {
    document.getElementById('model-select').innerHTML = '<option value="">Unknown</option>';
  });

  // Mode toggle: update active state + model dropdown (single authoritative listener)
  document.getElementById('mode-toggle').addEventListener('click', async (e) => {
    const btn = e.target.closest('.mode-btn');
    if (!btn) return;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const mode = btn.dataset.mode;
    // Re-fetch models on every switch so list is always fresh (Ollama ps changes)
    if (mode === 'offline') {
      const sel = document.getElementById('model-select');
      sel.innerHTML = '<option value="">Đang kiểm tra Ollama…</option>';
      try {
        const data = await API.getModels();
        _models = data;
      } catch (_) {}
    }
    _populateModelSelect(mode);
  });

  // Init modules
  Documents.init();
  Sessions.init(onSessionSelect);
  Chat.init();
})();
