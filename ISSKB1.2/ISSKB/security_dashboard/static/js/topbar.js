const Topbar = (() => {
  const statOnline   = document.getElementById('stat-online');
  const statWarning  = document.getElementById('stat-warning');
  const statCritical = document.getElementById('stat-critical');
  const statOffline  = document.getElementById('stat-offline');
  const pillCritical = document.getElementById('pill-critical');
  const sysLed       = document.getElementById('sys-led');
  const sysText      = document.getElementById('sys-status-text');
  const smTotal      = document.getElementById('sm-total');
  const smOpenInc    = document.getElementById('sm-open-inc');
  const smCritInc    = document.getElementById('sm-crit-inc');
  const smLastUpdate = document.getElementById('sm-last-update');

  function init() {
    _startClock();
    _initThemeToggle();
    Store.on('devices', _updateStats);
    Store.on('incidents', _updateIncidentStats);
    Store.on('lastUpdate', _updateTimestamp);
  }

  function _initThemeToggle() {
    const THEME_KEY = 'sentinel_theme';
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;

    const saved = localStorage.getItem(THEME_KEY);
    const startLight = saved !== 'dark'; // default light unless explicitly set to dark
    document.body.classList.toggle('light-theme', startLight);
    btn.textContent = startLight ? '🌙' : '☀️';
    btn.title = startLight ? 'Тёмная тема' : 'Светлая тема';

    btn.addEventListener('click', () => {
      const nowLight = document.body.classList.toggle('light-theme');
      localStorage.setItem(THEME_KEY, nowLight ? 'light' : 'dark');
      btn.textContent = nowLight ? '🌙' : '☀️';
      btn.title = nowLight ? 'Тёмная тема' : 'Светлая тема';
    });
  }

  function _updateStats(devices) {
    const online  = devices.filter(d => d.online_status).length;
    const warning = devices.filter(d => d.operational_mode === 'warning').length;
    const alarm   = devices.filter(d => d.operational_mode === 'alarm').length;
    const offline = devices.filter(d => !d.online_status).length;

    statOnline.textContent   = online;
    statWarning.textContent  = warning;
    statOffline.textContent  = offline;
    smTotal.textContent      = devices.length;

    _updateSystemStatus(alarm, warning, offline, devices.length);
  }

  function _updateIncidentStats(incidents) {
    const open     = incidents.filter(i => i.status === 'open' || i.status === 'acknowledged').length;
    const critical = incidents.filter(i => i.severity === 'critical' && i.status !== 'resolved').length;
    statCritical.textContent = open;
    smOpenInc.textContent    = open;
    smCritInc.textContent    = critical;

    if (open > 0) {
      pillCritical.classList.add('has-critical');
    } else {
      pillCritical.classList.remove('has-critical');
    }
  }

  function _updateSystemStatus(alarm, warning, offline, total) {
    if (alarm > 0) {
      sysLed.className  = 'status-led led-critical';
      sysText.textContent = `ТРЕВОГА ${alarm}`;
      sysText.style.color = 'var(--s-critical)';
    } else if (warning > 0 || offline > Math.floor(total * 0.3)) {
      sysLed.className  = 'status-led';
      sysText.textContent = 'ПРЕДУПРЕЖДЕНИЕ';
      sysText.style.color = 'var(--s-warning)';
    } else if (total === 0) {
      sysLed.className  = 'status-led';
      sysText.textContent = 'НЕТ ДАННЫХ';
      sysText.style.color = 'var(--txt-muted)';
    } else {
      sysLed.className  = 'status-led led-ok';
      sysText.textContent = 'ШТАТНЫЙ РЕЖИМ';
      sysText.style.color = 'var(--s-online)';
    }
  }

  function _updateTimestamp(date) {
    if (!date) return;
    const h = date.getHours().toString().padStart(2, '0');
    const m = date.getMinutes().toString().padStart(2, '0');
    const s = date.getSeconds().toString().padStart(2, '0');
    smLastUpdate.textContent = `${h}:${m}:${s}`;
  }

  function _startClock() {
    const clockEl    = document.getElementById('clock');
    const datelineEl = document.getElementById('dateline');
    const MONTHS     = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'];

    function tick() {
      const now = new Date();
      const h   = now.getHours().toString().padStart(2, '0');
      const m   = now.getMinutes().toString().padStart(2, '0');
      const s   = now.getSeconds().toString().padStart(2, '0');
      const d   = now.getDate().toString().padStart(2, '0');
      const mo  = MONTHS[now.getMonth()];
      const y   = now.getFullYear();
      clockEl.textContent    = `${h}:${m}:${s}`;
      datelineEl.textContent = `${d} ${mo} ${y}`;
    }
    tick();
    setInterval(tick, 1000);
  }

  return { init };
})();
