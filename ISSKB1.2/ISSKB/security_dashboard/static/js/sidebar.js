const Sidebar = (() => {
  const listEl    = document.getElementById('device-list');
  const countEl   = document.getElementById('device-count-badge');
  const searchEl  = document.getElementById('device-search');
  const filterBtns= document.querySelectorAll('.filter-btn');

  const msTotal   = document.getElementById('ms-total');
  const msOnline  = document.getElementById('ms-online');
  const msWarning = document.getElementById('ms-warning');
  const msOffline = document.getElementById('ms-offline');

  // Collapsed state per category name
  const collapsedGroups = new Set();

  function init() {
    searchEl.addEventListener('input', () => {
      Store.set('searchQuery', searchEl.value.trim());
      _render();
    });

    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        Store.set('filterMode', btn.dataset.filter);
        _render();
      });
    });

    Store.on('devices', _render);
    Store.on('selectedDeviceId', _highlightSelected);
    Store.on('tabChanged', () => _render());
  }

  function _getTabFilteredDevices() {
    const tab       = TabSystem.getActive();
    const devices   = Store.get('devices');
    const categories = tab ? tab.categories : [];

    return devices.filter(d => {
      // Tab filter: []=ничего, [...]= только эти категории (из БД)
      if (!categories.length || !categories.includes(d.category_code)) return false;
      // Search filter
      const q = (Store.get('searchQuery') || '').toLowerCase();
      if (q && !d.name.toLowerCase().includes(q) &&
               !d.category_name?.toLowerCase().includes(q) &&
               !d.zone_name?.toLowerCase().includes(q)) return false;
      // Status filter
      switch (Store.get('filterMode') || 'all') {
        case 'alarm':   return d.operational_mode === 'alarm';
        case 'warning': return d.operational_mode === 'warning';
        case 'offline': return !d.online_status;
        default:        return true;
      }
    });
  }

  function _render() {
    const allDevices = Store.get('devices');
    const filtered   = _getTabFilteredDevices();
    const tab        = TabSystem.getActive();

    // Counts
    const total   = allDevices.length;
    const online  = allDevices.filter(d => d.online_status).length;
    const warning = allDevices.filter(d => d.operational_mode === 'warning' || d.operational_mode === 'alarm').length;
    const offline = allDevices.filter(d => !d.online_status).length;

    const tabTotal = tab?.categories?.length > 0
      ? allDevices.filter(d => tab.categories.includes(d.category_code)).length
      : 0;
    countEl.textContent   = `${filtered.length}/${tabTotal}`;
    msTotal.textContent   = total;
    msOnline.textContent  = online;
    msWarning.textContent = warning;
    msOffline.textContent = offline;

    // Group
    const groups = {};
    filtered.forEach(d => {
      const g = d.category_name || 'Другое';
      if (!groups[g]) groups[g] = { icon: d.category_icon || '📡', items: [] };
      groups[g].items.push(d);
    });

    const sortedGroups = Object.entries(groups).sort(([, a], [, b]) => {
      return _groupPriority(a.items) - _groupPriority(b.items);
    });

    listEl.innerHTML = '';
    const selectedId = Store.get('selectedDeviceId');

    if (sortedGroups.length === 0) {
      const empty = document.createElement('div');
      empty.style.cssText = 'padding:20px 12px;color:var(--txt-muted);font-size:11px;text-align:center';
      empty.textContent = tab?.categories?.length === 0
        ? 'Устройства этой подсистемы\nбудут отображены после подключения'
        : 'Нет устройств по фильтру';
      listEl.appendChild(empty);
      return;
    }

    sortedGroups.forEach(([groupName, group]) => {
      const isCollapsed = collapsedGroups.has(groupName);
      const wrap = document.createElement('div');
      wrap.className = 'device-group-wrap';

      // Header
      const header = document.createElement('div');
      header.className = 'device-group-header';
      header.innerHTML = `
        <span class="grp-chevron ${isCollapsed ? 'collapsed' : ''}">▼</span>
        <span>${group.icon} ${groupName}</span>
        <span class="grp-count">${group.items.length}</span>
      `;
      header.addEventListener('click', () => _toggleGroup(groupName, wrap));
      wrap.appendChild(header);

      // Items container
      const itemsEl = document.createElement('div');
      itemsEl.className = `device-group-items${isCollapsed ? ' collapsed' : ''}`;
      if (!isCollapsed) itemsEl.style.maxHeight = (group.items.length * 46) + 'px';

      group.items.sort(_compareDevices).forEach(dev => {
        itemsEl.appendChild(_buildItem(dev, dev.id === selectedId));
      });
      wrap.appendChild(itemsEl);
      listEl.appendChild(wrap);
    });
  }

  function _toggleGroup(groupName, wrapEl) {
    const itemsEl  = wrapEl.querySelector('.device-group-items');
    const chevron  = wrapEl.querySelector('.grp-chevron');
    const isNowCollapsed = !collapsedGroups.has(groupName);

    if (isNowCollapsed) {
      collapsedGroups.add(groupName);
      itemsEl.style.maxHeight = itemsEl.scrollHeight + 'px';
      requestAnimationFrame(() => { itemsEl.style.maxHeight = '0'; });
    } else {
      collapsedGroups.delete(groupName);
      itemsEl.style.maxHeight = itemsEl.children.length * 46 + 'px';
    }

    itemsEl.classList.toggle('collapsed', isNowCollapsed);
    chevron.classList.toggle('collapsed', isNowCollapsed);
  }

  function _groupPriority(devs) {
    if (devs.some(d => d.operational_mode === 'alarm'))   return 0;
    if (devs.some(d => d.operational_mode === 'warning')) return 1;
    return 2;
  }

  function _compareDevices(a, b) {
    const ord = { alarm: 0, warning: 1, active: 2, patrol: 3, idle: 4, maintenance: 5, offline: 6 };
    const aO = !a.online_status ? 6 : (ord[a.operational_mode] ?? 4);
    const bO = !b.online_status ? 6 : (ord[b.operational_mode] ?? 4);
    return aO - bO;
  }

  function _buildItem(dev, selected) {
    const el = document.createElement('div');
    el.className = 'device-item' +
      (selected ? ' selected' : '') +
      (dev.operational_mode === 'alarm' ? ' alarm-item' : '');
    el.dataset.id = dev.id;

    const batHtml = dev.battery_level != null
      ? `<span class="di-bat">🔋${dev.battery_level}%</span>`
      : '';
    el.innerHTML = `
      <div class="di-status-dot ${_dotClass(dev)} ${_dotGlowClass(dev)}"></div>
      <div class="di-icon">${dev.category_icon || '📡'}</div>
      <div class="di-info">
        <div class="di-name">${dev.name}</div>
        <div class="di-sub">${_modeLabel(dev)}${dev.serial_number ? ' · ' + dev.serial_number : ''}</div>
      </div>
      ${batHtml}
    `;
    el.addEventListener('click', () => {
      Store.set('selectedDeviceId', dev.id);
      MapWidget.focusDevice(dev.id);
    });
    return el;
  }

  function _highlightSelected(selectedId) {
    document.querySelectorAll('.device-item').forEach(el => {
      el.classList.toggle('selected', Number(el.dataset.id) === selectedId);
    });
  }

  function _dotClass(dev) {
    if (!dev.online_status)                           return 'dot-offline';
    if (dev.operational_mode === 'alarm')             return 'dot-critical';
    if (dev.operational_mode === 'warning')           return 'dot-warning';
    if (dev.operational_mode === 'maintenance')       return 'dot-maintenance';
    if (dev.operational_mode === 'patrol')            return 'dot-patrol';
    return 'dot-online';
  }

  function _dotGlowClass(dev) {
    if (!dev.online_status)                     return '';
    if (dev.operational_mode === 'alarm')       return 'glow-critical';
    if (dev.operational_mode === 'warning')     return 'glow-warning';
    if (dev.operational_mode === 'maintenance') return 'glow-maintenance';
    if (dev.operational_mode === 'patrol')      return 'glow-patrol';
    return 'glow-online';
  }

  function _modeLabel(dev) {
    if (!dev.online_status) return 'ОФФЛАЙН';
    const l = { active:'Активно', idle:'Ожидание', alarm:'⚠ ТРЕВОГА',
                warning:'Предупрежд.', maintenance:'ТО', patrol:'Патруль', offline:'Оффлайн' };
    return l[dev.operational_mode] || dev.operational_mode;
  }

  return { init };
})();
