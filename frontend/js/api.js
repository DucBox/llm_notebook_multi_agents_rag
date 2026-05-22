const API = (() => {
  const BASE = '/api/v1';

  async function request(path, opts = {}) {
    const token = localStorage.getItem('token');
    const headers = { ...opts.headers };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    // Don't set Content-Type for FormData (browser sets it with boundary)
    if (!(opts.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const res = await fetch(`${BASE}${path}`, { ...opts, headers });

    if (res.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('userEmail');
      window.location.href = '/ui/index.html';
      return;
    }
    if (res.status === 204) return null;
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = data?.detail ?? `HTTP ${res.status}`;
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  }

  return {
    // System
    health: () => fetch('/api/v1/health').then(r => r.json()),

    // Auth
    register: (email, password) =>
      request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),
    login: (email, password) =>
      request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

    // Documents
    listDocuments: (page = 1, pageSize = 50) =>
      request(`/documents?page=${page}&page_size=${pageSize}`),
    uploadDocuments: (formData) =>
      request('/documents', { method: 'POST', body: formData }),
    deleteDocument: (id) =>
      request(`/documents/${id}`, { method: 'DELETE' }),
    getDocumentChunks: (id, pageSize = 5) =>
      request(`/documents/${id}/chunks?page_size=${pageSize}`),

    // Conversations
    listConversations: () =>
      request('/conversations'),
    createConversation: () =>
      request('/conversations', { method: 'POST', body: JSON.stringify({}) }),
    deleteConversation: (id) =>
      request(`/conversations/${id}`, { method: 'DELETE' }),
    getMessages: (id) =>
      request(`/conversations/${id}/messages`),
    chat: (id, payload) =>
      request(`/conversations/${id}/chat`, { method: 'POST', body: JSON.stringify(payload) }),
    compact: (id) =>
      request(`/conversations/${id}/compact`, { method: 'POST' }),
  };
})();
