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

  // Populate model name from backend
  API.health().then(info => {
    const sel = document.getElementById('model-select');
    if (info?.generation_model) {
      sel.innerHTML = `<option value="default">${info.generation_model}</option>`;
    }
  }).catch(() => {
    document.getElementById('model-select').innerHTML = '<option value="default">Unknown</option>';
  });

  // Init modules
  Documents.init();
  Sessions.init(onSessionSelect);
  Chat.init();
})();
