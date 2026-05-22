const Documents = (() => {
  let _docs = [];
  let _selectedIds = new Set(); // UUIDs of checked docs

  // ── Render ──────────────────────────────────────────────
  function _iconClass(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    if (ext === 'pdf') return 'pdf';
    if (ext === 'md' || ext === 'markdown') return 'md';
    return 'txt';
  }

  function _ext(filename) {
    return filename.split('.').pop().toUpperCase().slice(0, 3);
  }

  function _formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function _renderList() {
    const el = document.getElementById('doc-list');
    if (!_docs.length) {
      el.innerHTML = '<div class="empty-hint">Chưa có tài liệu nào</div>';
      return;
    }
    el.innerHTML = _docs.map(doc => `
      <div class="doc-item ${_selectedIds.has(doc.id) ? 'selected' : ''}" data-id="${doc.id}">
        <input type="checkbox" class="doc-checkbox" data-id="${doc.id}"
          ${_selectedIds.has(doc.id) ? 'checked' : ''}
          title="Chọn để dùng trong truy vấn" />
        <div class="doc-icon ${_iconClass(doc.filename)}">${_ext(doc.filename)}</div>
        <div class="doc-info">
          <div class="doc-name" title="${doc.original_filename}">${doc.original_filename}</div>
          <div class="doc-meta">${_formatSize(doc.file_size)} · ${doc.chunk_count ?? 0} chunks</div>
        </div>
        <div class="doc-status ${doc.status}" title="${doc.status}"></div>
        <button class="doc-delete" data-id="${doc.id}" title="Xoá tài liệu">×</button>
      </div>
    `).join('');

    // Checkbox toggle
    el.querySelectorAll('.doc-checkbox').forEach(cb => {
      cb.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = cb.dataset.id;
        if (cb.checked) _selectedIds.add(id);
        else _selectedIds.delete(id);
        cb.closest('.doc-item').classList.toggle('selected', cb.checked);
      });
    });

    // Click row → preview
    el.querySelectorAll('.doc-item').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.classList.contains('doc-checkbox')) return;
        if (e.target.classList.contains('doc-delete')) return;
        const id = row.dataset.id;
        const doc = _docs.find(d => d.id === id);
        if (doc) _openPreview(doc);
      });
    });

    // Delete
    el.querySelectorAll('.doc-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        const doc = _docs.find(d => d.id === id);
        if (!confirm(`Xoá tài liệu "${doc?.original_filename}"?`)) return;
        try {
          await API.deleteDocument(id);
          _selectedIds.delete(id);
          await refresh();
        } catch (err) {
          alert(`Lỗi khi xoá: ${err.message}`);
        }
      });
    });
  }

  // ── Preview modal ────────────────────────────────────────
  let _currentBlobUrl = null;

  async function _openPreview(doc) {
    document.getElementById('preview-title').textContent = doc.original_filename;
    document.getElementById('preview-meta').innerHTML = `
      <div class="meta-item"><span class="meta-label">Trạng thái</span><span class="meta-value">${doc.status}</span></div>
      <div class="meta-item"><span class="meta-label">Kích thước</span><span class="meta-value">${_formatSize(doc.file_size)}</span></div>
      <div class="meta-item"><span class="meta-label">Chunks</span><span class="meta-value">${doc.chunk_count ?? 0}</span></div>
      <div class="meta-item"><span class="meta-label">Trang</span><span class="meta-value">${doc.page_count ?? '—'}</span></div>
    `;

    const previewEl = document.getElementById('preview-chunks');
    previewEl.innerHTML = '<div class="empty-hint">Đang tải file…</div>';
    document.getElementById('preview-modal').classList.remove('hidden');

    // Revoke previous blob URL
    if (_currentBlobUrl) { URL.revokeObjectURL(_currentBlobUrl); _currentBlobUrl = null; }

    try {
      const { url, type } = await API.getDocumentFileUrl(doc.id);
      _currentBlobUrl = url;

      if (type === 'application/pdf') {
        previewEl.innerHTML = `<iframe class="preview-iframe" src="${url}" title="${_esc(doc.original_filename)}"></iframe>`;
      } else {
        // TXT / Markdown — fetch text and display
        const text = await fetch(url).then(r => r.text());
        previewEl.innerHTML = `<pre class="preview-text">${_esc(text)}</pre>`;
      }
    } catch {
      previewEl.innerHTML = '<div class="empty-hint">Không thể tải file</div>';
    }
  }

  async function openPreviewById(docId) {
    let doc = _docs.find(d => d.id === docId);
    if (!doc) {
      // Not in cache — fetch from API
      try { doc = await API.getDocument(docId); } catch { return; }
    }
    if (doc) _openPreview(doc);
  }

  function _esc(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── Upload modal ─────────────────────────────────────────
  let _pendingFiles = [];

  function _setupUploadModal() {
    const modal     = document.getElementById('upload-modal');
    const addBtn    = document.getElementById('add-source-btn');
    const closeBtn  = document.getElementById('upload-close');
    const cancelBtn = document.getElementById('upload-cancel');
    const confirmBtn = document.getElementById('upload-confirm');
    const fileInput = document.getElementById('file-input');
    const dropZone  = document.getElementById('file-drop-zone');

    addBtn.addEventListener('click', () => {
      _pendingFiles = [];
      document.getElementById('upload-list').innerHTML = '';
      confirmBtn.disabled = true;
      modal.classList.remove('hidden');
    });
    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));

    fileInput.addEventListener('change', () => _addFiles([...fileInput.files]));

    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      _addFiles([...e.dataTransfer.files]);
    });

    confirmBtn.addEventListener('click', _doUpload);
  }

  function _addFiles(files) {
    files.forEach(f => {
      if (!_pendingFiles.find(p => p.name === f.name)) _pendingFiles.push(f);
    });
    _renderUploadList();
    document.getElementById('upload-confirm').disabled = _pendingFiles.length === 0;
  }

  function _renderUploadList() {
    const el = document.getElementById('upload-list');
    el.innerHTML = _pendingFiles.map((f, i) => `
      <div class="upload-item" id="upload-item-${i}">
        <div class="upload-item-name">
          <div class="name" title="${_esc(f.name)}">${_esc(f.name)}</div>
          <div class="size">${(f.size / 1024).toFixed(1)} KB</div>
        </div>
        <span class="upload-status pending" id="upload-status-${i}">Chờ</span>
        <button class="upload-remove" onclick="Documents._removeFile(${i})">×</button>
      </div>
    `).join('');
  }

  function _removeFile(i) {
    _pendingFiles.splice(i, 1);
    _renderUploadList();
    document.getElementById('upload-confirm').disabled = _pendingFiles.length === 0;
  }

  async function _doUpload() {
    const confirmBtn = document.getElementById('upload-confirm');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Đang tải…';

    const fd = new FormData();
    _pendingFiles.forEach(f => fd.append('files', f));

    _pendingFiles.forEach((_, i) => {
      const s = document.getElementById(`upload-status-${i}`);
      if (s) { s.textContent = 'Đang tải…'; s.className = 'upload-status uploading'; }
    });

    try {
      await API.uploadDocuments(fd);
      _pendingFiles.forEach((_, i) => {
        const s = document.getElementById(`upload-status-${i}`);
        if (s) { s.textContent = 'Xong ✓'; s.className = 'upload-status done'; }
      });
      setTimeout(async () => {
        document.getElementById('upload-modal').classList.add('hidden');
        await refresh();
      }, 800);
    } catch (err) {
      _pendingFiles.forEach((_, i) => {
        const s = document.getElementById(`upload-status-${i}`);
        if (s) { s.textContent = 'Lỗi'; s.className = 'upload-status error'; }
      });
      alert(`Lỗi khi tải lên: ${err.message}`);
    } finally {
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Tải lên';
    }
  }

  // ── Public ───────────────────────────────────────────────
  async function refresh() {
    try {
      const res = await API.listDocuments(1, 50);
      _docs = (res.items ?? []).filter(d => !d.deleted_at);
    } catch { _docs = []; }
    _renderList();
  }

  function getSelectedIds() {
    // [] = no docs selected → backend retrieves nothing
    // [id1, ...] = filter to selected docs
    // null is never returned — always explicit
    return [..._selectedIds];
  }

  function init() {
    _setupUploadModal();

    // Preview close
    document.getElementById('preview-close').addEventListener('click', () => {
      document.getElementById('preview-modal').classList.add('hidden');
    });
    document.getElementById('preview-modal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
    });
    document.getElementById('upload-modal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
    });

    refresh();
  }

  return { init, refresh, getSelectedIds, openPreviewById, _removeFile };
})();
