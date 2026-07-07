const TabSystem = (() => {
  // Static metadata only — no hardcoded category codes
  const TABS_DEF = [
    { id: 1, label: 'АИС "ПОЛЕ"',  icon: '📹' },
    { id: 2, label: 'ВИП-117-М3', icon: '🔐' },
    { id: 3, label: 'КАУС',     icon: '🛡' },
    { id: 4, label: 'РАЗВЕДКА',  icon: '🔍' },
    { id: 5, label: 'РЭБ/РЭР',      icon: '📡'  },
    { id: 6, label: 'БпЛА',  icon: '💻' },
    { id: 7, label: 'ОГНЕВЫЕ СРЕДСТВА ПОРАЖЕНИЯ', icon: '🔥' },
    { id: 8, label: 'НРКТ',        icon: '🔥' },
    { id: 9, label: '***',       icon: '🏢' },
  ];

  let TABS = [];
  let activeTabId = 5;

  async function init() {
    // Load category→tab mapping from DB — no hardcoded codes
    const catsByTab = {};
    try {
      const cats = await fetch('/api/categories').then(r => r.json());
      for (const cat of cats) {
        const tid = cat.tab_id ?? 5;
        if (!catsByTab[tid]) catsByTab[tid] = [];
        catsByTab[tid].push(cat.code);
      }
    } catch (e) {
      console.warn('[TabSystem] Could not load categories from API:', e);
    }

    // Build TABS with categories pulled from DB
    TABS = TABS_DEF.map(def => ({
      ...def,
      categories: catsByTab[def.id] ?? [],
    }));

    _renderTabBar();
    Store.set('activeTab', TABS.find(t => t.id === activeTabId));
  }

  function _renderTabBar() {
    const bar = document.getElementById('subsystem-tabs');
    bar.innerHTML = '';
    TABS.forEach(tab => {
      const el = document.createElement('div');
      el.className = 'stab' + (tab.id === activeTabId ? ' active' : '');
      el.dataset.tabId = tab.id;
      el.title = tab.label;
      el.innerHTML = `
        <span class="stab-icon">${tab.icon}</span>
        <span class="stab-label">${tab.label}</span>
        <span class="stab-num">${tab.id}</span>
      `;
      el.addEventListener('click', () => activate(tab.id));
      bar.appendChild(el);
    });
  }

  function activate(tabId) {
    const tab = TABS.find(t => t.id === tabId);
    if (!tab || tabId === activeTabId) return;
    activeTabId = tabId;

    document.querySelectorAll('.stab').forEach(el => {
      el.classList.toggle('active', parseInt(el.dataset.tabId) === tabId);
    });

    Store.set('activeTab', tab);
    Store.emit('tabChanged', tab);

    Toast.show({
      icon: tab.icon,
      title: `Подсистема ${tab.id}: ${tab.label}`,
      msg: tab.categories.length === 0
        ? 'Нет устройств — назначьте tab_id в таблице device_categories'
        : `Категорий в подсистеме: ${tab.categories.length}`,
      type: 'info',
      duration: 2500,
    });
  }

  function getActive() { return TABS.find(t => t.id === activeTabId); }

  return { init, activate, getActive };
})();
