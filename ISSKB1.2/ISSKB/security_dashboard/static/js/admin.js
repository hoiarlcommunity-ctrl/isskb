/**
 * admin.js — Логика панели администрирования (/admin)
 */

// ── Auth check & theme ────────────────────────────────────────────────────────
(async function bootstrap() {
  const THEME_KEY = 'sentinel_theme';
  const saved = localStorage.getItem(THEME_KEY);
  const startLight = saved !== 'dark';
  document.body.classList.toggle('light-theme', startLight);

  const themeBtn = document.getElementById('atp-theme-btn');
  themeBtn.textContent = startLight ? '🌙' : '☀️';
  themeBtn.addEventListener('click', () => {
    const nowLight = document.body.classList.toggle('light-theme');
    localStorage.setItem(THEME_KEY, nowLight ? 'light' : 'dark');
    themeBtn.textContent = nowLight ? '🌙' : '☀️';
  });

  // Auth verification
  let me;
  try {
    const r = await fetch('/auth/me', { credentials: 'same-origin' });
    if (!r.ok) { window.location.replace('/login'); return; }
    me = await r.json();
    if (me.role !== 'admin') { window.location.replace('/'); return; }
  } catch { window.location.replace('/login'); return; }

  document.getElementById('atp-username').textContent =
    me.full_name || me.username || 'Администратор';

  // Logout
  document.getElementById('atp-logout-btn').addEventListener('click', async () => {
    await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
    window.location.replace('/login');
  });

  // Logo
  try {
    const ld = await fetch('/api/config/logo').then(r => r.json());
    if (ld.logo_url) {
      const img = document.getElementById('atp-logo-img');
      img.src = ld.logo_url;
      img.style.display = '';
      document.getElementById('atp-logo-fallback').style.display = 'none';
    }
  } catch {}

  App.init();
})();

// ── Utility ───────────────────────────────────────────────────────────────────

const Toast = {
  show(msg, type = 'info') {
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const titles = { success: 'Успешно', error: 'Ошибка', info: 'Информация' };
    const el = document.createElement('div');
    el.className = `adm-toast ${type}`;
    el.innerHTML = `
      <span class="adm-toast-icon">${icons[type]}</span>
      <div class="adm-toast-body">
        <div class="adm-toast-title">${titles[type]}</div>
        <div class="adm-toast-msg">${msg}</div>
      </div>`;
    document.getElementById('adm-toast-area').appendChild(el);
    setTimeout(() => el.remove(), 4000);
  },
};

function fmt(dt) {
  if (!dt) return '—';
  const d = new Date(dt);
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function roleBadge(role) {
  const map = { admin: 'role-admin', operator: 'role-operator', viewer: 'role-viewer' };
  const labels = { admin: 'Администратор', operator: 'Оператор', viewer: 'Наблюдатель' };
  return `<span class="role-badge ${map[role] || ''}">${labels[role] || role}</span>`;
}

function statusPill(u) {
  const now = new Date();
  if (u.locked_until && new Date(u.locked_until) > now) {
    return `<span class="status-pill locked"><span class="sdot"></span>Заблокирован</span>`;
  }
  if (!u.is_active) {
    return `<span class="status-pill inactive"><span class="sdot"></span>Неактивен</span>`;
  }
  return `<span class="status-pill active"><span class="sdot"></span>Активен</span>`;
}

// ── Navigation ────────────────────────────────────────────────────────────────

const Nav = (() => {
  const btns = document.querySelectorAll('.an-btn[data-section]');
  const sections = document.querySelectorAll('.ac-section');

  function activate(name) {
    btns.forEach(b => b.classList.toggle('active', b.dataset.section === name));
    sections.forEach(s => s.classList.toggle('active', s.id === `sec-${name}`));
    SectionLoaders[name]?.();
  }

  btns.forEach(b => b.addEventListener('click', () => activate(b.dataset.section)));

  return { activate };
})();

// ── Section loaders ───────────────────────────────────────────────────────────

const SectionLoaders = {
  users:       () => { SystemStatus.stopAutoRefresh(); Logs.stopAutoRefresh(); Users.load(); },
  audit:       () => { SystemStatus.stopAutoRefresh(); Logs.stopAutoRefresh(); Audit.load(); },
  sessions:    () => { SystemStatus.stopAutoRefresh(); Logs.stopAutoRefresh(); Sessions.load(); },
  system:      () => { Logs.stopAutoRefresh(); SystemStatus.load(); SystemStatus.startAutoRefresh(); },
  integration: () => { SystemStatus.stopAutoRefresh(); Logs.stopAutoRefresh(); Integration.load(); },
  logs:        () => { SystemStatus.stopAutoRefresh(); Logs.load(); Logs.startAutoRefresh(); },
};

// ── Users ─────────────────────────────────────────────────────────────────────

const Users = (() => {
  let _data = [];
  let _editId = null;
  let _pwdUserId = null;
  let _delUserId = null;

  async function load() {
    try {
      _data = await fetch('/api/admin/users', { credentials: 'same-origin' }).then(r => r.json());
      _render();
      const badge = document.getElementById('nav-users-count');
      badge.textContent = _data.length;
      badge.style.display = '';
    } catch { Toast.show('Не удалось загрузить список пользователей', 'error'); }
  }

  function _filter() {
    const q    = document.getElementById('users-search').value.toLowerCase();
    const role = document.getElementById('users-role-filter').value;
    const stat = document.getElementById('users-status-filter').value;
    const now  = new Date();
    return _data.filter(u => {
      const matchQ   = !q || (u.username||'').toLowerCase().includes(q) || (u.full_name||'').toLowerCase().includes(q);
      const matchR   = !role || u.role === role;
      const isLocked = u.locked_until && new Date(u.locked_until) > now;
      const matchS   = !stat
        || (stat === 'active'   && u.is_active && !isLocked)
        || (stat === 'inactive' && !u.is_active)
        || (stat === 'locked'   && isLocked);
      return matchQ && matchR && matchS;
    });
  }

  function _render() {
    const rows = _filter();
    const tbody = document.getElementById('users-tbody');
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-state-icon">👥</div><div class="empty-state-text">Пользователи не найдены</div></div></td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(u => `
      <tr data-id="${u.id}">
        <td class="td-id">${u.id}</td>
        <td><strong>${escHtml(u.username)}</strong></td>
        <td>${escHtml(u.full_name) || '<span style="color:var(--txt-dim)">—</span>'}</td>
        <td style="color:var(--txt-muted);font-size:11px">${escHtml(u.job_title) || '—'}</td>
        <td>${roleBadge(u.role)}</td>
        <td style="color:var(--txt-muted);font-size:12px">${escHtml(u.office_id)}</td>
        <td>${statusPill(u)}</td>
        <td class="audit-time">${fmt(u.last_login)}</td>
        <td class="td-actions">
          <button class="btn btn-ghost btn-sm btn-icon" data-action="edit" data-id="${u.id}" title="Редактировать">✏</button>
          <button class="btn btn-ghost btn-sm btn-icon" data-action="pwd" data-id="${u.id}" title="Сброс пароля">🔑</button>
          ${u.locked_until && new Date(u.locked_until) > new Date()
            ? `<button class="btn btn-ghost btn-sm btn-icon" data-action="unlock" data-id="${u.id}" title="Разблокировать">🔓</button>`
            : ''}
          <button class="btn btn-danger btn-sm btn-icon" data-action="del" data-id="${u.id}" title="Удалить">🗑</button>
        </td>
      </tr>`).join('');

    tbody.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id);
        const u  = _data.find(x => x.id === id);
        if (!u) return;
        const action = btn.dataset.action;
        if (action === 'edit')   openEdit(u);
        if (action === 'pwd')    openPwd(u);
        if (action === 'del')    openDel(u);
        if (action === 'unlock') unlockUser(id);
      });
    });
  }

  // ── Create / Edit Modal ───────────────────────────────────────────────────

  function openCreate() {
    _editId = null;
    document.getElementById('user-modal-title').textContent   = 'Создать пользователя';
    document.getElementById('user-modal-subtitle').textContent = 'Заполните данные новой учётной записи';
    document.getElementById('uf-pw-label').textContent = 'Пароль *';
    _clearForm();
    _setModalVisible('user-modal', true);
    document.getElementById('uf-username').focus();
  }

  function openEdit(u) {
    _editId = u.id;
    document.getElementById('user-modal-title').textContent   = 'Редактировать пользователя';
    document.getElementById('user-modal-subtitle').textContent = `Учётная запись: ${u.username}`;
    document.getElementById('uf-pw-label').textContent = 'Новый пароль (оставьте пустым, чтобы не менять)';
    _clearForm();
    document.getElementById('uf-username').value  = u.username;
    document.getElementById('uf-username').disabled = true;
    document.getElementById('uf-fullname').value  = u.full_name || '';
    document.getElementById('uf-jobtitle').value  = u.job_title || '';
    document.getElementById('uf-role').value      = u.role;
    document.getElementById('uf-office').value    = u.office_id || '';
    document.getElementById('uf-phone').value     = u.phone || '';
    document.getElementById('uf-phone-work').value= u.phone_work || '';
    document.getElementById('uf-notes').value     = u.notes || '';
    document.getElementById('uf-active').checked  = u.is_active;
    _setModalVisible('user-modal', true);
  }

  function _clearForm() {
    ['uf-username','uf-password','uf-fullname','uf-jobtitle','uf-office','uf-phone','uf-phone-work','uf-notes'].forEach(id => {
      const el = document.getElementById(id);
      el.value = '';
      el.disabled = false;
    });
    document.getElementById('uf-role').value    = 'operator';
    document.getElementById('uf-active').checked = true;
    document.getElementById('uf-gen-box').style.display  = 'none';
    document.getElementById('user-modal-error').style.display = 'none';
  }

  async function saveUser() {
    const btn = document.getElementById('user-modal-save');
    const errEl = document.getElementById('user-modal-error');
    errEl.style.display = 'none';

    const username  = document.getElementById('uf-username').value.trim();
    const password  = document.getElementById('uf-password').value;
    const full_name = document.getElementById('uf-fullname').value.trim() || null;
    const job_title = document.getElementById('uf-jobtitle').value.trim() || null;
    const role      = document.getElementById('uf-role').value;
    const office_id = document.getElementById('uf-office').value.trim() || 'main';
    const phone      = document.getElementById('uf-phone').value.trim()      || null;
    const phone_work = document.getElementById('uf-phone-work').value.trim() || null;
    const notes      = document.getElementById('uf-notes').value.trim()      || null;
    const is_active = document.getElementById('uf-active').checked;

    if (!_editId && !username) {
      errEl.textContent = 'Введите логин пользователя';
      errEl.style.display = '';
      return;
    }
    if (!_editId && !password) {
      errEl.textContent = 'Введите пароль';
      errEl.style.display = '';
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Сохраняем...';

    try {
      let res, body;
      if (_editId) {
        const upd = { full_name, job_title, role, office_id, phone, phone_work, notes, is_active };
        if (password) upd.password = password;
        res = await fetch(`/api/admin/users/${_editId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(upd),
          credentials: 'same-origin',
        });
        if (password && res.ok) {
          await fetch(`/api/admin/users/${_editId}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: password }),
            credentials: 'same-origin',
          });
        }
      } else {
        res = await fetch('/api/admin/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, full_name, job_title, role, office_id, phone, phone_work, notes, is_active }),
          credentials: 'same-origin',
        });
      }
      body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);

      _setModalVisible('user-modal', false);
      Toast.show(_editId ? 'Пользователь обновлён' : 'Пользователь создан', 'success');
      await load();
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = '';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Сохранить';
    }
  }

  // ── Password Reset Modal ──────────────────────────────────────────────────

  function openPwd(u) {
    _pwdUserId = u.id;
    document.getElementById('pwd-modal-sub').textContent = `Пользователь: ${u.username} (${u.full_name || '—'})`;
    document.getElementById('pf-password').value = '';
    document.getElementById('pf-gen-box').style.display = 'none';
    document.getElementById('pwd-modal-error').style.display = 'none';
    _setModalVisible('pwd-modal', true);
  }

  async function savePwd() {
    const btn   = document.getElementById('pwd-modal-save');
    const errEl = document.getElementById('pwd-modal-error');
    const pw    = document.getElementById('pf-password').value;

    if (!pw) {
      errEl.textContent = 'Введите новый пароль';
      errEl.style.display = '';
      return;
    }

    btn.disabled = true; btn.textContent = 'Сохраняем...';
    try {
      const r = await fetch(`/api/admin/users/${_pwdUserId}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_password: pw }),
        credentials: 'same-origin',
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      _setModalVisible('pwd-modal', false);
      Toast.show('Пароль успешно сброшен', 'success');
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = '';
    } finally {
      btn.disabled = false; btn.textContent = 'Сбросить пароль';
    }
  }

  // ── Delete Confirm ────────────────────────────────────────────────────────

  function openDel(u) {
    _delUserId = u.id;
    document.getElementById('del-modal-user').textContent = `${u.username}${u.full_name ? ' (' + u.full_name + ')' : ''}`;
    document.getElementById('del-modal-sub').textContent  = 'Удалённые данные не восстанавливаются';
    _setModalVisible('del-modal', true);
  }

  async function confirmDel() {
    const btn = document.getElementById('del-modal-confirm');
    btn.disabled = true;
    try {
      const r = await fetch(`/api/admin/users/${_delUserId}`, {
        method: 'DELETE', credentials: 'same-origin',
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      _setModalVisible('del-modal', false);
      Toast.show('Пользователь удалён', 'success');
      await load();
    } catch (e) {
      Toast.show(e.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  async function unlockUser(id) {
    try {
      const r = await fetch(`/api/admin/users/${id}/unlock`, {
        method: 'POST', credentials: 'same-origin',
      });
      if (!r.ok) throw new Error('Ошибка');
      Toast.show('Пользователь разблокирован', 'success');
      await load();
    } catch { Toast.show('Не удалось разблокировать', 'error'); }
  }

  // ── Generate password helper (client-side) ───────────────────────────────

  function generatePassword(inputId, boxId, valId) {
    const uppers  = 'ABCDEFGHJKMNPQRSTUVWXYZ';
    const lowers  = 'abcdefghjkmnpqrstuvwxyz';
    const digits  = '23456789';
    const specials = '!@#$%';
    const all = uppers + lowers + digits + specials;
    let pwd = [
      uppers[Math.floor(Math.random() * uppers.length)],
      lowers[Math.floor(Math.random() * lowers.length)],
      digits[Math.floor(Math.random() * digits.length)],
      specials[Math.floor(Math.random() * specials.length)],
    ];
    for (let i = 0; i < 8; i++) pwd.push(all[Math.floor(Math.random() * all.length)]);
    pwd = pwd.sort(() => Math.random() - 0.5).join('');
    document.getElementById(inputId).value = pwd;
    document.getElementById(valId).textContent = pwd;
    document.getElementById(boxId).style.display = 'flex';
    return pwd;
  }

  // ── Wire events ───────────────────────────────────────────────────────────

  function wireEvents() {
    document.getElementById('btn-create-user').addEventListener('click', openCreate);
    document.getElementById('btn-refresh-users').addEventListener('click', load);

    // Filter inputs
    ['users-search','users-role-filter','users-status-filter'].forEach(id =>
      document.getElementById(id).addEventListener('input', _render)
    );

    // Modal close
    ['user-modal-close','user-modal-cancel'].forEach(id =>
      document.getElementById(id)?.addEventListener('click', () => _setModalVisible('user-modal', false))
    );
    document.getElementById('user-modal-save').addEventListener('click', saveUser);

    // Password eye toggle
    const pwInput = document.getElementById('uf-password');
    document.getElementById('uf-pw-eye').addEventListener('click', () => {
      pwInput.type = pwInput.type === 'password' ? 'text' : 'password';
    });

    // Generate password in user form
    document.getElementById('uf-pw-gen').addEventListener('click', () =>
      generatePassword('uf-password', 'uf-gen-box', 'uf-gen-val')
    );
    document.getElementById('uf-gen-copy').addEventListener('click', () => {
      navigator.clipboard.writeText(document.getElementById('uf-gen-val').textContent)
        .then(() => Toast.show('Пароль скопирован', 'success'));
    });

    // Pwd modal
    ['pwd-modal-close','pwd-modal-cancel'].forEach(id =>
      document.getElementById(id)?.addEventListener('click', () => _setModalVisible('pwd-modal', false))
    );
    document.getElementById('pwd-modal-save').addEventListener('click', savePwd);
    document.getElementById('pf-pw-eye').addEventListener('click', () => {
      const pf = document.getElementById('pf-password');
      pf.type = pf.type === 'password' ? 'text' : 'password';
    });
    document.getElementById('pf-generate').addEventListener('click', () =>
      generatePassword('pf-password', 'pf-gen-box', 'pf-gen-val')
    );
    document.getElementById('pf-gen-copy').addEventListener('click', () => {
      navigator.clipboard.writeText(document.getElementById('pf-gen-val').textContent)
        .then(() => Toast.show('Пароль скопирован', 'success'));
    });

    // Del modal
    ['del-modal-close','del-modal-cancel'].forEach(id =>
      document.getElementById(id)?.addEventListener('click', () => _setModalVisible('del-modal', false))
    );
    document.getElementById('del-modal-confirm').addEventListener('click', confirmDel);

    // Backdrop click to close
    ['user-modal','pwd-modal','del-modal'].forEach(id => {
      document.getElementById(id).addEventListener('click', e => {
        if (e.target.id === id) _setModalVisible(id, false);
      });
    });
  }

  return { load, wireEvents };
})();

// ── Audit ─────────────────────────────────────────────────────────────────────

const Audit = (() => {
  const PAGE = 100;
  let _offset = 0;
  let _total  = 0;

  async function load(reset = false) {
    if (reset) _offset = 0;
    const username = document.getElementById('audit-user-filter').value.trim();
    const action   = document.getElementById('audit-action-filter').value;
    const params   = new URLSearchParams({ limit: PAGE, offset: _offset });
    if (username) params.set('username', username);
    if (action)   params.set('action', action);

    try {
      const d = await fetch(`/api/admin/audit?${params}`, { credentials: 'same-origin' }).then(r => r.json());
      _total = d.total;
      _renderRows(d.items);
      _updatePagination();
    } catch { Toast.show('Не удалось загрузить журнал', 'error'); }
  }

  const ACTION_LABELS = {
    login_ok:         { text: 'Вход',              cls: 'action-ok' },
    login_fail:       { text: 'Ошибка входа',      cls: 'action-fail' },
    logout:           { text: 'Выход',             cls: 'action-info' },
    token_refresh:    { text: 'Обновление токена', cls: 'action-info' },
    account_locked:   { text: 'Блокировка',        cls: 'action-warn' },
    password_changed: { text: 'Смена пароля',      cls: 'action-warn' },
  };

  function _renderRows(items) {
    const tbody = document.getElementById('audit-tbody');
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-text">Записей не найдено</div></div></td></tr>`;
      return;
    }
    tbody.innerHTML = items.map((a, i) => {
      const al = ACTION_LABELS[a.action] || { text: a.action, cls: 'action-info' };
      return `
        <tr>
          <td class="td-id">${_offset + i + 1}</td>
          <td class="audit-time">${fmt(a.created_at)}</td>
          <td><strong>${escHtml(a.username) || '—'}</strong></td>
          <td><span class="action-badge ${al.cls}">${al.text}</span></td>
          <td class="audit-ip">${escHtml(a.ip_address) || '—'}</td>
          <td><span class="action-badge ${a.success ? 'action-ok' : 'action-fail'}">${a.success ? 'OK' : 'FAIL'}</span></td>
          <td style="font-size:11px;color:var(--txt-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(a.detail) || '—'}</td>
        </tr>`;
    }).join('');
  }

  function _updatePagination() {
    document.getElementById('audit-page-info').textContent =
      `${_offset + 1}–${Math.min(_offset + PAGE, _total)} из ${_total}`;
    document.getElementById('audit-prev').disabled = _offset === 0;
    document.getElementById('audit-next').disabled = _offset + PAGE >= _total;
  }

  function wireEvents() {
    document.getElementById('btn-refresh-audit').addEventListener('click', () => load(true));
    document.getElementById('btn-apply-audit-filter').addEventListener('click', () => load(true));
    document.getElementById('audit-prev').addEventListener('click', () => { _offset = Math.max(0, _offset - PAGE); load(); });
    document.getElementById('audit-next').addEventListener('click', () => { _offset += PAGE; load(); });
    document.getElementById('audit-user-filter').addEventListener('keydown', e => { if (e.key === 'Enter') load(true); });
  }

  return { load: () => load(true), wireEvents };
})();

// ── Sessions ──────────────────────────────────────────────────────────────────

const Sessions = (() => {
  async function load() {
    const container = document.getElementById('session-cards');
    try {
      const data = await fetch('/api/admin/sessions', { credentials: 'same-origin' }).then(r => r.json());
      if (!data.length) {
        container.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-state-icon">🔌</div><div class="empty-state-text">Активных сессий не найдено</div></div>`;
        return;
      }
      const ROLE_ICONS = { admin: '🛡', operator: '👤', viewer: '👁' };
      container.innerHTML = data.map(s => `
        <div class="session-card">
          <div class="sc-avatar">${ROLE_ICONS[s.role] || '👤'}</div>
          <div class="sc-info">
            <div class="sc-name">${escHtml(s.full_name || s.username)}</div>
            <div class="sc-meta">${escHtml(s.username)} · ${roleBadge(s.role)}</div>
            <div class="sc-meta" style="margin-top:3px">Офис: ${escHtml(s.office_id)}</div>
            <div class="sc-expires">Токен до: ${fmt(s.expires_at)}</div>
          </div>
          <button class="btn btn-danger btn-sm btn-icon" data-uid="${s.user_id}" title="Завершить сессию">✕</button>
        </div>`).join('');

      container.querySelectorAll('[data-uid]').forEach(btn => {
        btn.addEventListener('click', async () => {
          if (!confirm('Завершить сессию пользователя?')) return;
          await fetch(`/api/admin/sessions/${btn.dataset.uid}`, { method: 'DELETE', credentials: 'same-origin' });
          Toast.show('Сессия завершена', 'success');
          load();
        });
      });
    } catch { Toast.show('Не удалось загрузить сессии', 'error'); }
  }

  function wireEvents() {
    document.getElementById('btn-refresh-sessions').addEventListener('click', load);
  }

  return { load, wireEvents };
})();

// ── System Status ─────────────────────────────────────────────────────────────

const SystemStatus = (() => {
  let _timer = null;

  function _fmtUptime(s) {
    const d  = Math.floor(s / 86400);
    const h  = Math.floor((s % 86400) / 3600);
    const m  = Math.floor((s % 3600) / 60);
    return `${d > 0 ? d + 'д ' : ''}${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
  }

  function _fmtMb(mb) {
    if (mb >= 1024) return `${(mb/1024).toFixed(1)} ГБ`;
    return `${mb} МБ`;
  }

  function _setBar(id, pct) {
    const el = document.getElementById(id);
    if (!el) return;
    const w = Math.min(100, Math.max(0, pct));
    el.style.width = `${w}%`;
    el.classList.toggle('mc-bar-warn', w >= 70 && w < 90);
    el.classList.toggle('mc-bar-crit', w >= 90);
  }

  function _set(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function _dotCls(dot, ok) {
    if (!dot) return;
    dot.className = `dbc-dot ${ok ? 'dbc-dot-ok' : 'dbc-dot-err'}`;
  }

  async function load() {
    try {
      const d = await fetch('/api/admin/metrics', { credentials: 'same-origin' }).then(r => r.json());

      // ── OS / Process ──────────────────────────────────────────────────────
      if (d.system && !d.system.error) {
        const s = d.system;
        _set('mc-cpu-val',    `${s.cpu_percent}%`);
        _set('mc-cpu-sub',    `${s.cpu_count} ядер (логических)`);
        _setBar('mc-cpu-bar', s.cpu_percent);

        _set('mc-ram-val',    `${s.ram_percent}%`);
        _set('mc-ram-sub',    `${_fmtMb(s.ram_used_mb)} / ${_fmtMb(s.ram_total_mb)}`);
        _setBar('mc-ram-bar', s.ram_percent);

        _set('mc-proc-val',   `${s.process_rss_mb}`);
        _set('mc-uptime-val', _fmtUptime(s.os_uptime_s));
      }

      // ── Main DB ───────────────────────────────────────────────────────────
      const mdb = d.main_db || {};
      const mok = mdb.status === 'ok';
      _dotCls(document.getElementById('dbc-main-dot'), mok);
      _set('dbc-main-latency', mok ? `${mdb.latency_ms} мс` : 'Ошибка');
      _set('dbc-main-size',    mok ? _fmtMb(mdb.size_mb)     : '—');
      _set('dbc-main-active',  mok ? String(mdb.active_conns) : '—');
      _set('dbc-main-total',   mok ? `${mdb.total_conns} (${mdb.idle_conns} простаивает)` : '—');
      _set('dbc-main-devices', mok ? String(mdb.devices)       : '—');
      _set('dbc-main-inc',     mok ? String(mdb.open_incidents): '—');

      // ── Auth DB ───────────────────────────────────────────────────────────
      const adb = d.auth_db || {};
      const aok = adb.status === 'ok';
      _dotCls(document.getElementById('dbc-auth-dot'), aok);
      _set('dbc-auth-latency',  aok ? `${adb.latency_ms} мс` : 'Ошибка');
      _set('dbc-auth-size',     aok ? _fmtMb(adb.size_mb)    : '—');
      _set('dbc-auth-total',    aok ? String(adb.total_conns) : '—');
      _set('dbc-auth-users',    aok ? String(adb.active_users): '—');
      _set('dbc-auth-sessions', aok ? String(adb.active_sessions): '—');

    } catch (e) { Toast.show('Ошибка загрузки метрик: ' + e.message, 'error'); }
  }

  function wireEvents() {
    document.getElementById('btn-refresh-system').addEventListener('click', load);
    document.getElementById('btn-restart').addEventListener('click', async () => {
      if (!confirm('Перезапустить сервер? Все пользователи будут отключены на ~3 секунды.')) return;
      try {
        const r = await fetch('/api/admin/server/restart', { method: 'POST', credentials: 'same-origin' });
        const d = await r.json();
        Toast.show(d.message || 'Перезапуск...', 'info');
      } catch { Toast.show('Ошибка перезапуска', 'error'); }
    });
  }

  function startAutoRefresh() {
    _timer = setInterval(load, 15000);
  }

  function stopAutoRefresh() {
    if (_timer) { clearInterval(_timer); _timer = null; }
  }

  return { load, wireEvents, startAutoRefresh, stopAutoRefresh };
})();

// ── Modal helper ──────────────────────────────────────────────────────────────

function _setModalVisible(id, show) {
  document.getElementById(id).classList.toggle('visible', show);
}

// ── Integration / Data Sources ────────────────────────────────────────────────

const Integration = (() => {
  let _data       = [];
  let _editId     = null;
  let _customRows = [];   // [{sysKey, apiKey}]

  const FIXED_KEYS = new Set(['name', 'online', 'status', 'lat', 'lon']);

  const _DB_TARGETS = {
    battery_level:   'device_states.battery_level',
    signal_strength: 'device_states.signal_strength',
    error_code:      'device_states.error_code',
    altitude:        'device_positions.altitude',
    speed:           'device_positions.speed',
    heading:         'device_positions.heading',
  };

  function _dbTarget(sysKey) {
    if (!sysKey) return '—';
    return _DB_TARGETS[sysKey] || `extra_state["${sysKey}"]`;
  }

  function _renderCustomFields() {
    const tbody = document.getElementById('fm-custom-tbody');
    if (!tbody) return;
    tbody.innerHTML = _customRows.map((row, idx) => `
      <tr data-cidx="${idx}" style="border-bottom:1px solid var(--border-dim)">
        <td style="padding:4px 10px">
          <input class="form-control fm-sys-key" list="fm-sys-datalist"
                 value="${escHtml(row.sysKey)}"
                 placeholder="battery_level"
                 style="height:26px;font-size:12px;font-family:monospace"
                 data-cidx="${idx}" />
        </td>
        <td style="padding:4px 10px">
          <input class="form-control fm-api-key"
                 value="${escHtml(row.apiKey)}"
                 placeholder="api_field_name"
                 style="height:26px;font-size:12px"
                 data-cidx="${idx}" />
        </td>
        <td style="padding:5px 10px;color:var(--txt-muted);font-size:11px;font-family:monospace" class="fm-db-cell" data-cidx="${idx}">
          ${escHtml(_dbTarget(row.sysKey))}
        </td>
        <td style="padding:4px 6px;text-align:center">
          <button class="btn btn-ghost btn-sm" type="button" data-rm="${idx}" title="Удалить поле"
                  style="color:var(--s-critical);width:26px;height:26px;padding:0;font-size:13px">✕</button>
        </td>
      </tr>`).join('');

    tbody.querySelectorAll('.fm-sys-key').forEach(inp => {
      inp.addEventListener('input', e => {
        const i = parseInt(e.target.dataset.cidx);
        _customRows[i].sysKey = e.target.value.trim();
        const cell = tbody.querySelector(`.fm-db-cell[data-cidx="${i}"]`);
        if (cell) cell.textContent = _dbTarget(_customRows[i].sysKey);
      });
    });
    tbody.querySelectorAll('.fm-api-key').forEach(inp => {
      inp.addEventListener('input', e => {
        const i = parseInt(e.target.dataset.cidx);
        _customRows[i].apiKey = e.target.value.trim();
      });
    });
    tbody.querySelectorAll('[data-rm]').forEach(btn => {
      btn.addEventListener('click', () => {
        const i = parseInt(btn.dataset.rm);
        _customRows.splice(i, 1);
        _renderCustomFields();
      });
    });

    // Show/hide DB info box based on whether custom rows exist
    const info = document.getElementById('fm-db-info');
    if (info) info.style.display = _customRows.length ? '' : 'none';
  }

  async function load() {
    try {
      _data = await fetch('/api/settings/sources', { credentials: 'same-origin' }).then(r => r.json());
      _render();
      _loadBuffer();
    } catch { Toast.show('Не удалось загрузить источники данных', 'error'); }
  }

  function _render() {
    const tbody = document.getElementById('sources-tbody');
    if (!_data.length) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="empty-state-icon">🔗</div><div class="empty-state-text">Источники не настроены. Нажмите «+ Добавить источник».</div></div></td></tr>`;
      return;
    }
    tbody.innerHTML = _data.map(s => `
      <tr data-id="${s.id}">
        <td class="td-id">${s.id}</td>
        <td>
          <strong>${escHtml(s.name)}</strong>
          ${s.description ? `<div style="font-size:10px;color:var(--txt-muted);margin-top:2px">${escHtml(s.description)}</div>` : ''}
        </td>
        <td style="font-family:monospace;font-size:11px;color:var(--txt-secondary);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(s.base_url)}</td>
        <td style="font-family:monospace;font-size:11px;color:var(--txt-muted)">${escHtml(s.ping_path || '/')}</td>
        <td style="color:var(--txt-muted);font-size:12px">${s.timeout_s}с</td>
        <td>${s.is_heartbeat ? '<span class="action-badge action-ok">ДА</span>' : '<span style="color:var(--txt-dim)">—</span>'}</td>
        <td>${s.is_active
          ? '<span class="status-pill active"><span class="sdot"></span>Активен</span>'
          : '<span class="status-pill inactive"><span class="sdot"></span>Отключён</span>'}</td>
        <td class="td-actions">
          <button class="btn btn-ghost btn-sm" data-action="ping" data-id="${s.id}" title="Проверить связь">🔌</button>
          <button class="btn btn-ghost btn-sm btn-icon" data-action="edit" data-id="${s.id}" title="Редактировать">✏</button>
          <button class="btn btn-danger btn-sm btn-icon" data-action="del" data-id="${s.id}" title="Удалить">🗑</button>
        </td>
      </tr>`).join('');

    tbody.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id);
        const s  = _data.find(x => x.id === id);
        if (!s && btn.dataset.action !== 'ping') return;
        const action = btn.dataset.action;
        if (action === 'edit') openEdit(s);
        if (action === 'del')  _deleteSrc(id);
        if (action === 'ping') _testPing(id, btn);
      });
    });
  }

  async function _testPing(id, btn) {
    const orig = btn.textContent;
    btn.disabled = true; btn.textContent = '⏳';
    try {
      const r = await fetch(`/api/settings/sources/${id}/ping`, {
        method: 'POST', credentials: 'same-origin',
      }).then(r => r.json());
      if (r.ok) Toast.show(`Связь установлена! HTTP ${r.status_code}`, 'success');
      else       Toast.show(`Нет связи: ${r.error || 'Ошибка'}`, 'error');
    } catch { Toast.show('Ошибка проверки связи', 'error'); }
    finally { btn.disabled = false; btn.textContent = orig; }
  }

  async function _deleteSrc(id) {
    const s = _data.find(x => x.id === id);
    if (!confirm(`Удалить источник "${s?.name || id}"?`)) return;
    try {
      const r = await fetch(`/api/settings/sources/${id}`, {
        method: 'DELETE', credentials: 'same-origin',
      });
      if (!r.ok) throw new Error('Ошибка');
      Toast.show('Источник удалён', 'success');
      await load();
    } catch { Toast.show('Не удалось удалить источник', 'error'); }
  }

  async function _loadBuffer() {
    try {
      const d = await fetch('/api/settings/buffer', { credentials: 'same-origin' }).then(r => r.json());
      const total = d.total ?? 0;
      document.getElementById('buf-total').textContent  = total;
      document.getElementById('buf-online').textContent = d.online ?? '—';
      document.getElementById('buf-first').textContent  = d.first_received ? fmt(d.first_received) : '—';
      document.getElementById('buf-last').textContent   = d.last_received  ? fmt(d.last_received)  : '—';
      document.getElementById('buffer-badge').textContent = `${total} записей`;
      document.getElementById('buffer-dot').className =
        `dbc-dot ${total > 0 ? 'dbc-dot-ok' : 'dbc-dot-err'}`;
    } catch {}
  }

  // ── Source Modal ──────────────────────────────────────────────────────────

  function openCreate() {
    _editId = null;
    document.getElementById('src-modal-title').textContent = 'Добавить источник данных';
    _clearForm();
    _setModalVisible('src-modal', true);
    document.getElementById('sf-name').focus();
  }

  function openEdit(s) {
    _editId = s.id;
    document.getElementById('src-modal-title').textContent = `Редактировать: ${s.name}`;
    _clearForm();
    document.getElementById('sf-name').value        = s.name || '';
    document.getElementById('sf-base-url').value    = s.base_url || '';
    document.getElementById('sf-ping-path').value   = s.ping_path || '/';
    document.getElementById('sf-ping-ok').value     = s.ping_ok_text || '';
    document.getElementById('sf-timeout').value     = s.timeout_s ?? 10;
    document.getElementById('sf-active').checked    = !!s.is_active;
    document.getElementById('sf-heartbeat').checked = !!s.is_heartbeat;
    document.getElementById('sf-description').value = s.description || '';

    // Data polling fields
    document.getElementById('sf-data-path').value       = s.data_path || '';
    document.getElementById('sf-response-format').value = s.response_format || 'json';
    document.getElementById('sf-poll-interval').value   = s.poll_interval_s ?? 60;

    const fm = s.field_map || {};
    document.getElementById('fm-name').value   = fm.name   || 'name';
    document.getElementById('fm-online').value = fm.online || 'online';
    document.getElementById('fm-status').value = fm.status || 'status';
    document.getElementById('fm-lat').value    = fm.lat    || 'lat';
    document.getElementById('fm-lon').value    = fm.lon    || 'lon';

    // Populate custom field rows from field_map (exclude fixed keys)
    _customRows = Object.entries(fm)
      .filter(([k]) => !FIXED_KEYS.has(k))
      .map(([sysKey, apiKey]) => ({ sysKey, apiKey }));
    _renderCustomFields();

    _setModalVisible('src-modal', true);
  }

  function _clearForm() {
    ['sf-name','sf-base-url','sf-ping-path','sf-ping-ok','sf-description'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    document.getElementById('sf-timeout').value          = 10;
    document.getElementById('sf-active').checked         = true;
    document.getElementById('sf-heartbeat').checked      = false;
    document.getElementById('sf-data-path').value        = '';
    document.getElementById('sf-response-format').value  = 'json';
    document.getElementById('sf-poll-interval').value    = 60;
    ['fm-name','fm-online','fm-status','fm-lat','fm-lon'].forEach((id, i) => {
      document.getElementById(id).value = ['name','online','status','lat','lon'][i];
    });
    _customRows = [];
    _renderCustomFields();
    document.getElementById('src-modal-error').style.display = 'none';
  }

  async function _save() {
    const errEl = document.getElementById('src-modal-error');
    errEl.style.display = 'none';

    const name     = document.getElementById('sf-name').value.trim();
    const base_url = document.getElementById('sf-base-url').value.trim();
    if (!name)     { errEl.textContent = 'Введите название источника'; errEl.style.display = ''; return; }
    if (!base_url) { errEl.textContent = 'Введите базовый URL';        errEl.style.display = ''; return; }

    const body = {
      name, base_url,
      ping_path:    document.getElementById('sf-ping-path').value.trim()   || '/',
      ping_ok_text: document.getElementById('sf-ping-ok').value.trim()     || null,
      timeout_s:    parseInt(document.getElementById('sf-timeout').value)   || 10,
      is_active:    document.getElementById('sf-active').checked,
      is_heartbeat: document.getElementById('sf-heartbeat').checked,
      description:     document.getElementById('sf-description').value.trim() || null,
      data_path:       document.getElementById('sf-data-path').value.trim()   || null,
      response_format: document.getElementById('sf-response-format').value    || 'json',
      poll_interval_s: parseInt(document.getElementById('sf-poll-interval').value) || 60,
      field_map: (() => {
        const fm = {
          name:   document.getElementById('fm-name').value.trim()   || 'name',
          online: document.getElementById('fm-online').value.trim() || 'online',
          status: document.getElementById('fm-status').value.trim() || 'status',
          lat:    document.getElementById('fm-lat').value.trim()    || 'lat',
          lon:    document.getElementById('fm-lon').value.trim()    || 'lon',
        };
        _customRows.forEach(({ sysKey, apiKey }) => {
          if (sysKey && apiKey) fm[sysKey] = apiKey;
        });
        return fm;
      })(),
    };

    const btn = document.getElementById('src-modal-save');
    btn.disabled = true; btn.textContent = 'Сохраняем...';
    try {
      const url    = _editId ? `/api/settings/sources/${_editId}` : '/api/settings/sources';
      const method = _editId ? 'PUT' : 'POST';
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin',
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      _setModalVisible('src-modal', false);
      Toast.show(_editId ? 'Источник обновлён' : 'Источник добавлен', 'success');
      await load();
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = '';
    } finally {
      btn.disabled = false; btn.textContent = 'Сохранить';
    }
  }

  async function _testFromModal() {
    if (!_editId) {
      Toast.show('Сначала сохраните источник, затем проверьте связь', 'info');
      return;
    }
    const btn = document.getElementById('src-modal-test');
    const orig = btn.textContent;
    btn.disabled = true; btn.textContent = '⏳ Проверка...';
    try {
      const r = await fetch(`/api/settings/sources/${_editId}/ping`, {
        method: 'POST', credentials: 'same-origin',
      }).then(r => r.json());
      if (r.ok) Toast.show(`Связь установлена! Ответ: ${r.response || ('HTTP ' + r.status_code)}`, 'success');
      else       Toast.show(`Нет связи: ${r.error || 'Ошибка'}`, 'error');
    } catch { Toast.show('Ошибка проверки', 'error'); }
    finally { btn.disabled = false; btn.textContent = orig; }
  }

  function wireEvents() {
    document.getElementById('btn-add-source').addEventListener('click', openCreate);
    document.getElementById('btn-refresh-sources').addEventListener('click', load);

    document.getElementById('fm-add-btn')?.addEventListener('click', () => {
      _customRows.push({ sysKey: '', apiKey: '' });
      _renderCustomFields();
      // Focus the new sys-key input
      const tbody = document.getElementById('fm-custom-tbody');
      const inputs = tbody?.querySelectorAll('.fm-sys-key');
      if (inputs?.length) inputs[inputs.length - 1].focus();
    });

    ['src-modal-close','src-modal-cancel'].forEach(id =>
      document.getElementById(id)?.addEventListener('click', () => _setModalVisible('src-modal', false))
    );
    document.getElementById('src-modal')?.addEventListener('click', e => {
      if (e.target.id === 'src-modal') _setModalVisible('src-modal', false);
    });
    document.getElementById('src-modal-save').addEventListener('click', _save);
    document.getElementById('src-modal-test').addEventListener('click', _testFromModal);

    document.getElementById('btn-clear-buffer').addEventListener('click', async () => {
      if (!confirm('Очистить буфер ext_devices? Все записи в буферной таблице будут удалены.')) return;
      try {
        const r = await fetch('/api/settings/buffer', {
          method: 'DELETE', credentials: 'same-origin',
        });
        if (!r.ok) throw new Error('Ошибка');
        Toast.show('Буфер очищен', 'success');
        await _loadBuffer();
      } catch { Toast.show('Ошибка очистки буфера', 'error'); }
    });
  }

  return { load, wireEvents };
})();

// ── System Logs ───────────────────────────────────────────────────────────────

const Logs = (() => {
  let _timer = null;
  let _autoRefresh = true;

  const _CAT_LABELS = {
    api: 'API', poller: 'Опрос', heartbeat: 'Heartbeat',
    sync: 'Синхр.', system: 'Система', ws: 'WS',
  };
  const _CAT_COLORS = {
    api: 'var(--accent-br)', poller: '#6bbbff', heartbeat: '#a8e6a3',
    sync: '#d4a8f0', system: 'var(--txt-secondary)', ws: '#f0c87a',
  };
  const _LEVEL_COLORS = {
    error: 'var(--s-critical)', warn: 'var(--s-warning)',
    info: 'var(--s-online)', debug: 'var(--txt-dim)',
  };

  function _fmtTs(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      + ' ' + d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  }

  async function load() {
    try {
      const cat   = document.getElementById('log-filter-cat')?.value || '';
      const level = document.getElementById('log-filter-level')?.value || '';
      let url = '/api/admin/logs?limit=200';
      if (cat)   url += `&category=${cat}`;
      if (level) url += `&level=${level}`;

      const data = await fetch(url, { credentials: 'same-origin' }).then(r => r.json());
      _render(data);
    } catch (e) { /* silent on auto-refresh */ }
  }

  function _render(rows) {
    const tbody = document.getElementById('logs-tbody');
    const countEl = document.getElementById('logs-count');
    if (countEl) countEl.textContent = rows.length;

    // Warn badge in nav if there are errors
    const hasError = rows.some(r => r.level === 'error');
    const badge = document.getElementById('nav-logs-badge');
    if (badge) badge.style.display = hasError ? '' : 'none';

    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><div class="empty-state-icon">📡</div><div class="empty-state-text">Событий нет</div></div></td></tr>`;
      return;
    }

    tbody.innerHTML = rows.map(r => `
      <tr style="border-bottom:1px solid var(--border-dim)">
        <td style="padding:5px 12px;color:var(--txt-muted);white-space:nowrap;font-family:monospace;font-size:11px">${_fmtTs(r.ts)}</td>
        <td style="padding:5px 10px">
          <span style="display:inline-block;padding:1px 7px;border-radius:3px;font-size:10px;font-weight:700;letter-spacing:0.05em;background:${_CAT_COLORS[r.category] || 'var(--txt-muted)'}22;color:${_CAT_COLORS[r.category] || 'var(--txt-muted)'}">${_CAT_LABELS[r.category] || r.category}</span>
        </td>
        <td style="padding:5px 10px">
          <span style="font-size:10px;font-weight:700;color:${_LEVEL_COLORS[r.level] || 'var(--txt-muted)'}">${(r.level || '').toUpperCase()}</span>
        </td>
        <td style="padding:5px 10px;color:var(--txt-primary)">${escHtml(r.message)}</td>
        <td style="padding:5px 10px;color:var(--txt-muted);font-size:11px;font-family:monospace;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(r.detail || '')}">${escHtml(r.detail || '—')}</td>
      </tr>`).join('');
  }

  function startAutoRefresh() {
    _autoRefresh = true;
    _timer = setInterval(() => { if (_autoRefresh) load(); }, 5000);
    const btn = document.getElementById('btn-toggle-autolog');
    if (btn) btn.textContent = '⏸ Стоп';
  }

  function stopAutoRefresh() {
    _autoRefresh = false;
    if (_timer) { clearInterval(_timer); _timer = null; }
    const btn = document.getElementById('btn-toggle-autolog');
    if (btn) btn.textContent = '▶ Старт';
  }

  function wireEvents() {
    document.getElementById('btn-refresh-logs')?.addEventListener('click', load);
    document.getElementById('log-filter-cat')?.addEventListener('change', load);
    document.getElementById('log-filter-level')?.addEventListener('change', load);
    document.getElementById('btn-toggle-autolog')?.addEventListener('click', () => {
      if (_autoRefresh) stopAutoRefresh(); else { startAutoRefresh(); load(); }
    });
  }

  return { load, wireEvents, startAutoRefresh, stopAutoRefresh };
})();


// ── App init ──────────────────────────────────────────────────────────────────

const App = {
  init() {
    Users.wireEvents();
    Audit.wireEvents();
    Sessions.wireEvents();
    SystemStatus.wireEvents();
    Integration.wireEvents();
    Logs.wireEvents();
    Users.load();
  },
};
