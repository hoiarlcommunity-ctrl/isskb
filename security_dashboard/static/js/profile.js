/**
 * profile.js — Профиль пользователя + сворачивание боковых панелей через краевые зоны.
 * Загружается ПЕРЕД app.js, инициализируется через Profile.init(user).
 */

const Profile = (() => {
  const ROLE_LABELS = { admin: 'Администратор', operator: 'Оператор', viewer: 'Наблюдатель' };
  const ROLE_ICONS  = { admin: '🛡', operator: '👤', viewer: '👁' };

  let _user = null;

  // ── Panel collapse (edge zones) ────────────────────────────────────────────

  const LS_KEY = 'sentinel_panels';

  function _initPanels() {
    const dashboard  = document.getElementById('dashboard');
    const edgeLeft   = document.getElementById('panel-edge-left');
    const edgeRight  = document.getElementById('panel-edge-right');
    if (!dashboard) return;

    // Read panel widths from CSS variables
    const style  = getComputedStyle(document.documentElement);
    const leftW  = parseInt(style.getPropertyValue('--left-w'))  || 272;
    const rightW = parseInt(style.getPropertyValue('--right-w')) || 308;
    const EDGE_W = 8;

    function _positionEdges(leftCollapsed, rightCollapsed) {
      if (edgeLeft) {
        edgeLeft.style.left = leftCollapsed ? '0px' : `${leftW - EDGE_W}px`;
        edgeLeft.setAttribute('data-collapsed', String(leftCollapsed));
        const arr = document.getElementById('panel-edge-left-arr');
        if (arr) arr.textContent = leftCollapsed ? '▶' : '◀';
      }
      if (edgeRight) {
        edgeRight.style.right = rightCollapsed ? '0px' : `${rightW - EDGE_W}px`;
        edgeRight.setAttribute('data-collapsed', String(rightCollapsed));
        const arr = document.getElementById('panel-edge-right-arr');
        if (arr) arr.textContent = rightCollapsed ? '◀' : '▶';
      }
    }

    // Restore state from localStorage
    const saved = (() => {
      try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; } catch { return {}; }
    })();
    if (saved.left)  dashboard.classList.add('left-collapsed');
    if (saved.right) dashboard.classList.add('right-collapsed');
    _updateBothClass(dashboard);
    _positionEdges(!!saved.left, !!saved.right);

    edgeLeft?.addEventListener('click', () => {
      const collapsed = dashboard.classList.toggle('left-collapsed');
      _updateBothClass(dashboard);
      _saveState(dashboard);
      _positionEdges(collapsed, dashboard.classList.contains('right-collapsed'));
      setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
    });

    edgeRight?.addEventListener('click', () => {
      const collapsed = dashboard.classList.toggle('right-collapsed');
      _updateBothClass(dashboard);
      _saveState(dashboard);
      _positionEdges(dashboard.classList.contains('left-collapsed'), collapsed);
      setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
    });
  }

  function _updateBothClass(dashboard) {
    const l = dashboard.classList.contains('left-collapsed');
    const r = dashboard.classList.contains('right-collapsed');
    dashboard.classList.toggle('both-collapsed', l && r);
  }

  function _saveState(dashboard) {
    localStorage.setItem(LS_KEY, JSON.stringify({
      left:  dashboard.classList.contains('left-collapsed'),
      right: dashboard.classList.contains('right-collapsed'),
    }));
  }

  // ── Profile modal ──────────────────────────────────────────────────────────

  function _open() {
    if (!_user) return;
    _fillInfo();
    _fillEditForm();
    _resetSecurityForm();
    document.getElementById('prof-modal').classList.add('visible');
    _switchTab('info');
  }

  function _close() {
    document.getElementById('prof-modal').classList.remove('visible');
  }

  function _switchTab(name) {
    document.querySelectorAll('.prof-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.ptab === name)
    );
    document.querySelectorAll('.prof-body').forEach(b =>
      b.classList.toggle('hidden', b.id !== `ptab-${name}`)
    );
  }

  function _fillInfo() {
    const u = _user;
    if (!u) return;
    const roleLabel = ROLE_LABELS[u.role] || u.role || '—';
    const roleIcon  = ROLE_ICONS[u.role]  || '👤';

    _set('prof-avatar',   roleIcon);
    _set('prof-fullname', u.full_name || u.username || '—');
    _set('prof-office',   u.office_id ? `Офис: ${u.office_id}` : '');

    const rb = document.getElementById('prof-role-badge');
    if (rb) { rb.textContent = roleLabel; rb.className = `prof-role-badge r-${u.role}`; }

    _set('pf-username',    u.username    || '—');
    _set('pf-jobtitle',    u.job_title   || '—');
    _set('pf-phone',       u.phone       || '—');
    _set('pf-phone-work',  u.phone_work  || '—');
    _set('pf-office-info', u.office_id   ? String(u.office_id) : '—');
    _set('pf-role-info',   roleLabel);
    _set('pf-notes-info',  u.notes       || '—');

    // Update topbar badge
    const opName  = document.getElementById('op-name');
    const opBadge = document.getElementById('op-badge');
    const opIcon  = document.getElementById('op-icon');
    if (opIcon)  opIcon.textContent  = roleIcon;
    if (opName)  opName.textContent  = u.full_name ? u.full_name.split(' ')[0] : (u.username || '—');
    if (opBadge) opBadge.textContent = `${roleLabel}${u.office_id ? ' · ' + u.office_id : ''}`;
  }

  function _fillEditForm() {
    const u = _user;
    if (!u) return;
    _val('pf-edit-fullname',    u.full_name  || '');
    _val('pf-edit-jobtitle',    u.job_title  || '');
    _val('pf-edit-phone',       u.phone      || '');
    _val('pf-edit-phone-work',  u.phone_work || '');
    _val('pf-edit-notes',       u.notes      || '');
    _hide('pf-edit-error');
  }

  function _resetSecurityForm() {
    ['pf-cur-pwd', 'pf-new-pwd', 'pf-confirm-pwd'].forEach(id => _val(id, ''));
    _hide('pf-pwd-error');
  }

  async function _saveProfile() {
    const btn = document.getElementById('pf-save-btn');
    _hide('pf-edit-error');
    btn.disabled = true;
    btn.textContent = 'Сохраняем...';
    try {
      const body = {
        full_name:  document.getElementById('pf-edit-fullname').value.trim()    || null,
        job_title:  document.getElementById('pf-edit-jobtitle').value.trim()    || null,
        phone:      document.getElementById('pf-edit-phone').value.trim()       || null,
        phone_work: document.getElementById('pf-edit-phone-work').value.trim()  || null,
        notes:      document.getElementById('pf-edit-notes').value.trim()       || null,
      };
      const r = await fetch('/auth/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      Object.assign(_user, body);
      window.CurrentUser = { ...(window.CurrentUser || {}), ...body };
      _fillInfo();
      _switchTab('info');
      if (typeof Toast !== 'undefined') {
        Toast.show({ icon: '✓', title: 'Профиль обновлён', msg: 'Данные сохранены', type: 'success', duration: 3000 });
      }
    } catch (e) {
      _showErr('pf-edit-error', e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Сохранить изменения';
    }
  }

  async function _changePassword() {
    const btn     = document.getElementById('pf-change-pwd-btn');
    const cur     = document.getElementById('pf-cur-pwd').value;
    const newPwd  = document.getElementById('pf-new-pwd').value;
    const confirm = document.getElementById('pf-confirm-pwd').value;
    _hide('pf-pwd-error');

    if (!cur)               { _showErr('pf-pwd-error', 'Введите текущий пароль'); return; }
    if (newPwd.length < 6)  { _showErr('pf-pwd-error', 'Новый пароль — минимум 6 символов'); return; }
    if (newPwd !== confirm)  { _showErr('pf-pwd-error', 'Пароли не совпадают'); return; }

    btn.disabled = true; btn.textContent = 'Сохраняем...';
    try {
      const r = await fetch('/auth/profile/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ current_password: cur, new_password: newPwd }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      _resetSecurityForm();
      if (typeof Toast !== 'undefined') {
        Toast.show({ icon: '✓', title: 'Пароль изменён', msg: 'Новый пароль установлен', type: 'success', duration: 3500 });
      }
    } catch (e) {
      _showErr('pf-pwd-error', e.message);
    } finally {
      btn.disabled = false; btn.textContent = 'Изменить пароль';
    }
  }

  function _wireEye(btnId, inputId) {
    document.getElementById(btnId)?.addEventListener('click', () => {
      const inp = document.getElementById(inputId);
      if (inp) inp.type = inp.type === 'password' ? 'text' : 'password';
    });
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  function _set(id, text)    { const el = document.getElementById(id); if (el) el.textContent = text; }
  function _val(id, v)       { const el = document.getElementById(id); if (el) el.value = v; }
  function _hide(id)         { const el = document.getElementById(id); if (el) el.style.display = 'none'; }
  function _showErr(id, msg) { const el = document.getElementById(id); if (el) { el.textContent = msg; el.style.display = ''; } }

  // ── Public init ────────────────────────────────────────────────────────────

  function init(user) {
    _user = user;

    _initPanels();

    // Wire profile modal events
    document.getElementById('profile-btn')?.addEventListener('click', _open);
    document.getElementById('prof-close')?.addEventListener('click', _close);

    // Close on backdrop click
    document.getElementById('prof-modal')?.addEventListener('click', e => {
      if (e.target.id === 'prof-modal') _close();
    });

    // Tab switching
    document.querySelectorAll('.prof-tab').forEach(tab => {
      tab.addEventListener('click', () => _switchTab(tab.dataset.ptab));
    });

    // Form actions
    document.getElementById('pf-save-btn')?.addEventListener('click', _saveProfile);
    document.getElementById('pf-change-pwd-btn')?.addEventListener('click', _changePassword);

    // Eye toggles
    _wireEye('pf-cur-eye',     'pf-cur-pwd');
    _wireEye('pf-new-eye',     'pf-new-pwd');
    _wireEye('pf-confirm-eye', 'pf-confirm-pwd');

    // Populate topbar badge immediately
    _fillInfo();
  }

  function setUser(user) {
    _user = user;
    _fillInfo();
  }

  return { init, setUser };
})();
