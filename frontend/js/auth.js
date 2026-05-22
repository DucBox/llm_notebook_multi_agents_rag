// ── Login/Register page logic ─────────────────────────────
(function () {
  // If already on app.html, just expose helpers
  if (!document.getElementById('login-form')) return;

  // Redirect if already logged in
  if (localStorage.getItem('token')) {
    window.location.href = '/ui/app.html';
    return;
  }

  const loginForm    = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const errorMsg     = document.getElementById('error-msg');
  const tabs         = document.querySelectorAll('.auth-tab');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.tab;
      loginForm.classList.toggle('hidden', target !== 'login');
      registerForm.classList.toggle('hidden', target !== 'register');
      errorMsg.classList.add('hidden');
    });
  });

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.remove('hidden');
  }

  function onSuccess(data) {
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('userEmail', data.user_id);
    window.location.href = '/ui/app.html';
  }

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMsg.classList.add('hidden');
    const btn = loginForm.querySelector('button[type=submit]');
    btn.disabled = true;
    btn.textContent = 'Đang đăng nhập…';
    try {
      const data = await API.login(
        document.getElementById('login-email').value,
        document.getElementById('login-password').value
      );
      onSuccess(data);
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Đăng nhập';
    }
  });

  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMsg.classList.add('hidden');
    const btn = registerForm.querySelector('button[type=submit]');
    btn.disabled = true;
    btn.textContent = 'Đang tạo tài khoản…';
    try {
      const data = await API.register(
        document.getElementById('reg-email').value,
        document.getElementById('reg-password').value
      );
      onSuccess(data);
    } catch (err) {
      showError(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Tạo tài khoản';
    }
  });
})();

// ── Auth helpers used by app.html ─────────────────────────
function requireAuth() {
  if (!localStorage.getItem('token')) {
    window.location.href = '/ui/index.html';
    return false;
  }
  return true;
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('userEmail');
  window.location.href = '/ui/index.html';
}
