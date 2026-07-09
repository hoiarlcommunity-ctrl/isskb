const AlertMode = (() => {
  const MODES = [
    { id: 'everyday', label: 'Повседневный', short: 'ПОВСЕДНЕВНЫЙ', icon: '🟢', color: '#22c55e', dotClass: 'dot-online',    ambClass: 'amb-everyday', level: 0 },
    { id: 'mode1',    label: 'ВСБГ',      short: 'ВСБГ',      icon: '🔵', color: '#3b82f6', dotClass: 'dot-online',    ambClass: 'amb-mode1',    level: 1 },
    { id: 'mode2',    label: 'ЛПА',      short: 'ЛПА',      icon: '🟡', color: '#eab308', dotClass: 'dot-warning',   ambClass: 'amb-mode2',    level: 2 },
    { id: 'mode3',    label: 'Антитеррор А',      short: 'АНТИТЕРРОР А',      icon: '🔴', color: '#ef4444', dotClass: 'dot-critical',  ambClass: 'amb-mode3',    level: 3 },
    { id: 'mode4',    label: 'Антитеррор Б',      short: 'АНТИТЕРРОР Б',      icon: '🔴', color: '#b91c1c', dotClass: 'dot-critical',  ambClass: 'amb-mode4',    level: 4 },
    { id: 'mode5',    label: 'Антитеррор В',      short: 'АНТИТЕРРОР В',      icon: '⛔', color: '#7f1d1d', dotClass: 'dot-critical',  ambClass: 'amb-mode5',    level: 5 },
  ];

  const TOAST_MSGS = {
    everyday: 'Штатный режим работы. Стандартные процедуры.',
    mode1:    'Приведение в высшую степень боевой готовности',
    mode2:    'Ликвидация последствий аварий',
    mode3:    'Режим противодействия терроризму. А',
    mode4:    'Режим противодействия терроризму. Б',
    mode5:    'Режим противодействия терроризму. В',
  };

  let currentMode = MODES[0];

  function init() {
    document.querySelectorAll('.amp-btn').forEach(btn => {
      btn.addEventListener('click', () => setMode(btn.dataset.mode));
    });
    _updateTopbarBadge(currentMode);
  }

  function setMode(modeId) {
    const mode = MODES.find(m => m.id === modeId);
    if (!mode || mode.id === currentMode.id) return;
    const prev = currentMode;
    currentMode = mode;

    // Update sidebar buttons
    document.querySelectorAll('.amp-btn').forEach(btn => {
      btn.className = 'amp-btn' + (btn.dataset.mode === modeId ? ` active-${modeId}` : '');
    });

    // Update topbar badge
    _updateTopbarBadge(mode);

    // Emit store event
    Store.set('alertMode', mode);
    Store.emit('alertModeChanged', { mode, prev });

    // Toast notification
    Toast.show({
      icon: mode.icon,
      title: `${mode.label} активирован`,
      msg: TOAST_MSGS[modeId] || '',
      type: mode.level >= 3 ? 'critical' : mode.level >= 2 ? 'warning' : 'info',
      duration: mode.level >= 3 ? 6000 : 3500,
    });

    // Apply body class for visual intensity
    document.body.dataset.alertLevel = mode.level;
  }

  function _updateTopbarBadge(mode) {
    const badge = document.getElementById('topbar-mode-badge');
    const label = document.getElementById('topbar-mode-label');
    const dot   = badge?.querySelector('.amb-dot');
    if (!badge) return;

    badge.className = `alert-mode-badge ${mode.ambClass}`;
    label.textContent = mode.short;
    if (dot) {
      dot.className = `amb-dot ${mode.dotClass}`;
    }
  }

  function getCurrent() { return currentMode; }

  return { init, setMode, getCurrent, MODES };
})();

// ── Toast helper (defined here, used by tabs + alertMode) ─────────────────
const Toast = (() => {
  const container = () => document.getElementById('toast-container');

  function show({ icon = 'ℹ', title = '', msg = '', type = 'info', duration = 4000 } = {}) {
    const el = document.createElement('div');
    el.className = `toast t-${type}`;
    el.style.position = 'relative';
    el.innerHTML = `
      <span class="toast-icon">${icon}</span>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        ${msg ? `<div class="toast-msg">${msg}</div>` : ''}
      </div>
      <button class="toast-close" onclick="this.closest('.toast').remove()">✕</button>
    `;
    container().appendChild(el);

    setTimeout(() => {
      el.classList.add('dismissing');
      setTimeout(() => el.remove(), 300);
    }, duration);
  }

  return { show };
})();
