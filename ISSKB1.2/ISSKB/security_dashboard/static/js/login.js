(async function () {
  'use strict';

  // ── Тема ──────────────────────────────────────────────────────────────────
  const THEME_KEY = 'sentinel_theme';
  const themeBtn  = document.getElementById('theme-toggle');

  function applyTheme(t) {
    document.body.classList.toggle('light-theme', t === 'light');
    themeBtn.textContent = t === 'light' ? '🌙' : '☀️';
  }

  const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
  applyTheme(savedTheme);

  themeBtn.addEventListener('click', () => {
    const next = document.body.classList.contains('light-theme') ? 'dark' : 'light';
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  });

  // ── Если уже авторизован — на главную ────────────────────────────────────
  try {
    const r = await fetch('/auth/me', { credentials: 'same-origin' });
    if (r.ok) { window.location.replace('/'); return; }
  } catch { /* не подключены — продолжаем */ }

  // ── Показать/скрыть пароль ────────────────────────────────────────────────
  const pwInput  = document.getElementById('f-password');
  const pwToggle = document.getElementById('pw-toggle');
  pwToggle.addEventListener('click', () => {
    const show = pwInput.type === 'password';
    pwInput.type  = show ? 'text' : 'password';
    pwToggle.textContent = show ? '🙈' : '👁';
  });

  // ── Форма входа ───────────────────────────────────────────────────────────
  const form     = document.getElementById('login-form');
  const errorEl  = document.getElementById('login-error');
  const loginBtn = document.getElementById('login-btn');

  function showError(msg) {
    errorEl.textContent = msg;
    errorEl.style.display = 'block';
    // Тряска карточки
    const card = document.querySelector('.login-card');
    card.style.animation = 'none';
    void card.offsetWidth;
    card.style.animation = 'shake 0.35s ease';
  }

  function clearError() {
    errorEl.style.display = 'none';
    errorEl.textContent   = '';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const username = document.getElementById('f-username').value.trim();
    const password = pwInput.value;

    if (!username || !password) {
      showError('Введите имя пользователя и пароль');
      return;
    }

    loginBtn.disabled     = true;
    loginBtn.textContent  = 'Проверка...';

    try {
      const res = await fetch('/auth/login', {
        method:      'POST',
        credentials: 'same-origin',
        headers:     { 'Content-Type': 'application/json' },
        body:        JSON.stringify({ username, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        loginBtn.textContent = '✓ Добро пожаловать';
        setTimeout(() => window.location.replace('/'), 300);
      } else {
        showError(data.detail || 'Ошибка авторизации');
        loginBtn.disabled    = false;
        loginBtn.textContent = 'Войти';
        if (res.status !== 429) pwInput.value = '';
        pwInput.focus();
      }
    } catch {
      showError('Нет соединения с сервером');
      loginBtn.disabled    = false;
      loginBtn.textContent = 'Войти';
    }
  });

  // Фокус на поле имени при загрузке
  document.getElementById('f-username').focus();
})();
