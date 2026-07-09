/**
 * Application bootstrap — initializes all modules in correct order.
 */

// Глобальный перехват 401 — редирект на страницу входа
const _origFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const res = await _origFetch(...args);
  if (res.status === 401) {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
    if (!url.includes('/auth/')) {
      window.location.replace('/login');
    }
  }
  return res;
};

// Текущий пользователь (доступен глобально)
window.CurrentUser = null;

(async function init() {
  // Проверка авторизации перед инициализацией
  let me;
  try {
    const r = await _origFetch('/auth/me', { credentials: 'same-origin' });
    if (!r.ok) { window.location.replace('/login'); return; }
    me = await r.json();
    window.CurrentUser = me;
  } catch { window.location.replace('/login'); return; }

  // Показываем кнопки администрирования только для admin
  if (me.role === 'admin') {
    document.getElementById('topbar-admin-btn')?.classList.add('show');
    document.getElementById('topbar-mgr-btn')?.classList.add('show');
  }

  // Инициализируем профиль (badge + collapse panels)
  if (typeof Profile !== 'undefined') {
    Profile.init(me);
  }

  // Init UI components (order: tabs + alertMode before sidebar/map so Store.activeTab is ready)
  ExtStatus.init();
  await TabSystem.init(); // async: fetches category→tab mapping from DB
  AlertMode.init();
  MapWidget.init();
  Sidebar.init();
  DevicePanel.init();
  IncidentPanel.init();
  Topbar.init();
  Bottombar.init();

  // Инициализация менеджера устройств (только для admin)
  if (me.role === 'admin' && typeof DeviceManager !== 'undefined') {
    DeviceManager.init();
  }

  // Кнопка выхода
  document.getElementById('logout-btn')?.addEventListener('click', async () => {
    await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
    window.location.replace('/login');
  });

  // Connect WebSocket for real-time updates
  Socket.connect();

  // ── Initial data load ─────────────────────────────────────────────────
  const _hideLoader = () => {
    const loader = document.getElementById('page-loader');
    if (!loader) return;
    loader.classList.add('fade-out');
    setTimeout(() => loader.classList.add('gone'), 380);
  };

  try {
    const [devices, incidents, zones] = await Promise.all([
      API.getDevices(),
      API.getIncidents({ limit: 50 }),
      API.getZones(),
    ]);

    Store.set('devices',   devices);
    Store.set('incidents', incidents);
    Store.set('zones',     zones);
    Store.set('lastUpdate', new Date());

    _hideLoader();

    // Render zones on map
    MapWidget.renderZones(zones);

    // Fit map to all devices after short delay (tiles need to load)
    setTimeout(() => MapWidget.fitAll(), 800);

  } catch (err) {
    console.error('[App] Failed to load initial data:', err);
    _hideLoader();
    document.getElementById('sys-status-text').textContent = 'ОШИБКА ЗАГРУЗКИ';
  }
})();
