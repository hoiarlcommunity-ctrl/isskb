const MapWidget = (() => {
  let map = null;
  let markersLayer = null;
  let zonesLayer   = null;
  let rangesLayer  = null;
  const markerRefs = {};
  const rangeRefs  = {};   // device_id → [L.circle, ...]

  // ── Layers registry ─────────────────────────────────────────────────────
  const LAYERS_DEF = [
    { id: 'devices',       label: 'Устройства',        icon: '📍', checked: true },
    { id: 'ranges_detect', label: 'Зоны обнаружения',  icon: '🔵', checked: true },
    { id: 'ranges_action', label: 'Зоны подавления',   icon: '🔴', checked: true },
    { id: 'zones',         label: 'Зоны охраны',       icon: '⬡',  checked: true },
  ];
  const layerState = Object.fromEntries(LAYERS_DEF.map(l => [l.id, l.checked]));

  // Category visibility: categoryCode → bool
  const catVisibility = {};
  let _catsBuilt = false;

  // ── Tile layers (offline) ────────────────────────────────────────────────
  const TILES = {
    dark: L.tileLayer('/tiles/dark/{z}/{x}/{y}.png', {
      maxZoom: 18, maxNativeZoom: 14, tileSize: 256, keepBuffer: 2,
    }),
    sat: L.tileLayer('/tiles/sat/{z}/{x}/{y}.png', {
      maxZoom: 18, maxNativeZoom: 6, tileSize: 256, keepBuffer: 2,
    }),
  };
  let currentTile = 'dark';

  async function _checkTileStatus() {
    try {
      const resp = await fetch('/tiles/status');
      const data = await resp.json();
      const hint = document.getElementById('tile-hint');
      if (!hint) return;
      const darkOk = (data.dark?.tiles || 0) > 0;
      const satOk  = (data.sat?.tiles  || 0) > 0;
      if (!darkOk && !satOk) {
        hint.textContent = '⚠ Тайлы не загружены — запустите: python download_tiles.py --all';
        hint.style.display = 'block';
      } else {
        hint.style.display = 'none';
        // Adjust maxNativeZoom based on what's actually downloaded
        if (darkOk && data.dark.tiles > 5000) {
          TILES.dark.options.maxNativeZoom = 14;
        }
      }
    } catch { /* ignore */ }
  }

  function init() {
    map = L.map('map', {
      center: [56.0113, 37.8472],
      zoom: 13,
      zoomControl: false,
      attributionControl: false,
    });

    TILES.dark.addTo(map);
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    rangesLayer  = L.layerGroup().addTo(map);
    markersLayer = L.layerGroup().addTo(map);
    zonesLayer   = L.layerGroup().addTo(map);

    _initToolbar();
    _initLayerControl();
    _bindStoreEvents();

    map.on('zoomend moveend', _updateLabelVisibility);
    _checkTileStatus();
  }

  // ── Toolbar ──────────────────────────────────────────────────────────────
  function _initToolbar() {
    document.getElementById('btn-all-devices').onclick = function () {
      Object.keys(catVisibility).forEach(k => { catVisibility[k] = true; });
      LAYERS_DEF.forEach(l => { layerState[l.id] = true; });
      _applyLayerVisibility();
      _applyCategoryVisibility();
      _updateLayerControlUI();
      fitAll();
    };

    document.getElementById('btn-fit-all').onclick = fitAll;

    document.getElementById('btn-toggle-zones').onclick = function () {
      this.classList.toggle('active');
      layerState.zones = !layerState.zones;
      _applyLayerVisibility();
      _updateLayerControlUI();
    };

    document.getElementById('btn-map-dark').onclick = function () {
      if (currentTile === 'dark') return;
      map.removeLayer(TILES[currentTile]);
      TILES.dark.addTo(map);
      currentTile = 'dark';
      this.classList.add('active');
      document.getElementById('btn-map-sat').classList.remove('active');
    };
    document.getElementById('btn-map-dark').classList.add('active');

    document.getElementById('btn-map-sat').onclick = function () {
      if (currentTile === 'sat') return;
      map.removeLayer(TILES[currentTile]);
      TILES.sat.addTo(map);
      currentTile = 'sat';
      this.classList.add('active');
      document.getElementById('btn-map-dark').classList.remove('active');
    };
  }

  // ── Layer control panel ──────────────────────────────────────────────────
  function _initLayerControl() {
    const container = document.getElementById('layer-rows');
    LAYERS_DEF.forEach(def => {
      const row = document.createElement('div');
      row.className = 'layer-row';
      row.dataset.layer = def.id;
      row.innerHTML = `
        <div class="layer-cb ${def.checked ? 'checked' : ''}" data-cb="${def.id}"></div>
        <span class="layer-icon">${def.icon}</span>
        <span class="layer-label">${def.label}</span>
        <span class="layer-count" id="lc-count-${def.id}"></span>
      `;
      row.addEventListener('click', () => _toggleLayer(def.id));
      container.appendChild(row);
    });

    document.getElementById('lc-toggle-all').addEventListener('click', () => {
      const anyOff = LAYERS_DEF.some(l => !layerState[l.id]);
      LAYERS_DEF.forEach(l => { layerState[l.id] = anyOff; });
      _applyLayerVisibility();
      _updateLayerControlUI();
    });

    const lcPanel = document.getElementById('layer-control');
    const lcHideBtn = document.getElementById('lc-hide-btn');
    const lcRows = document.getElementById('layer-rows');
    if (lcHideBtn && lcPanel && lcRows) {
      let collapsed = false;
      lcHideBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        collapsed = !collapsed;
        lcRows.style.display = collapsed ? 'none' : '';
        lcPanel.querySelectorAll('.layer-sep').forEach(el => { el.style.display = collapsed ? 'none' : ''; });
        lcHideBtn.textContent = collapsed ? '▼' : '▲';
        lcHideBtn.title = collapsed ? 'Развернуть' : 'Свернуть';
      });
    }

    _updateLayerCounts();
  }

  function _buildCategoryLayers(devices) {
    if (_catsBuilt) return;
    const cats = {};
    devices.forEach(d => {
      if (d.category_code && !cats[d.category_code]) {
        cats[d.category_code] = { name: d.category_name, icon: d.category_icon || '📡' };
      }
    });
    const codes = Object.keys(cats).sort();
    if (!codes.length) return;
    _catsBuilt = true;

    const container = document.getElementById('layer-rows');
    const sep = document.createElement('div');
    sep.className = 'layer-sep';
    sep.textContent = 'КАТЕГОРИИ';
    container.appendChild(sep);

    codes.forEach(code => {
      catVisibility[code] = true;
      const row = document.createElement('div');
      row.className = 'layer-row';
      row.dataset.layer = code;
      row.innerHTML = `
        <div class="layer-cb checked" data-cb="cat-${code}"></div>
        <span class="layer-icon">${cats[code].icon}</span>
        <span class="layer-label">${cats[code].name}</span>
      `;
      row.addEventListener('click', () => {
        catVisibility[code] = !catVisibility[code];
        row.querySelector('.layer-cb').classList.toggle('checked', catVisibility[code]);
        _applyCategoryVisibility();
      });
      container.appendChild(row);
    });
  }

  function _setRangesVisible(devId, show) {
    const circles = rangeRefs[devId];
    if (!circles) return;
    circles.forEach(c => {
      const typeOk = c._rangeType === 'detect'
        ? layerState.ranges_detect
        : layerState.ranges_action;
      const visible = show && typeOk;
      if (visible) { if (!rangesLayer.hasLayer(c)) rangesLayer.addLayer(c); }
      else          { if (rangesLayer.hasLayer(c))  rangesLayer.removeLayer(c); }
    });
  }

  function _applyCategoryVisibility() {
    const devices = Store.get('devices') || [];
    devices.forEach(d => {
      const m = markerRefs[d.id];
      if (!m) return;
      const el = m.getElement?.();
      if (!el) return;
      const catOk = catVisibility[d.category_code] !== false;
      let show;
      if (!catOk) {
        show = false;
      } else {
        const tab  = TabSystem?.getActive?.();
        const cats = tab ? tab.categories : null;
        show = (cats === null || (cats.length > 0 && cats.includes(d.category_code)));
      }
      el.style.display = show ? '' : 'none';
      _setRangesVisible(d.id, show);
    });
  }

  function _toggleLayer(layerId) {
    layerState[layerId] = !layerState[layerId];
    _applyLayerVisibility();
    _updateLayerControlUI();
  }

  function _applyLayerVisibility() {
    const toggle = (flag, layer) => {
      if (flag) { if (!map.hasLayer(layer)) layer.addTo(map); }
      else       { if (map.hasLayer(layer))  map.removeLayer(layer); }
    };
    toggle(layerState.devices, markersLayer);
    toggle(layerState.zones,   zonesLayer);

    // Ranges: управляем индивидуально с учётом типа и видимости категории/вкладки
    const devices = Store.get('devices') || [];
    const tab  = TabSystem?.getActive?.();
    const cats = tab ? tab.categories : null;
    devices.forEach(d => {
      const catOk = catVisibility[d.category_code] !== false;
      const tabOk = cats === null || (cats.length > 0 && cats.includes(d.category_code));
      _setRangesVisible(d.id, catOk && tabOk);
    });
  }

  function _updateLayerControlUI() {
    LAYERS_DEF.forEach(def => {
      const cb = document.querySelector(`.layer-cb[data-cb="${def.id}"]`);
      if (cb) cb.classList.toggle('checked', layerState[def.id]);
    });
    // Sync zones toolbar button
    const zbtn = document.getElementById('btn-toggle-zones');
    if (zbtn) zbtn.classList.toggle('active', layerState.zones);
  }

  function _updateLayerCounts() {
    const devices = Store.get('devices') || [];
    const el = document.getElementById('lc-count-devices');
    if (el) el.textContent = devices.length || '';
  }

  // ── Label visibility by pixel proximity ─────────────────────────────────
  const LABEL_MIN_PX = 58; // маркеры ближе этого порога — подписи скрываем

  function _updateLabelVisibility() {
    const entries = Object.entries(markerRefs);
    if (!entries.length) return;

    const pts = entries.map(([id, m]) => {
      const el = m.getElement?.();
      if (!el || el.style.display === 'none') return null;
      return { id: Number(id), pt: map.latLngToContainerPoint(m.getLatLng()), el };
    }).filter(Boolean);

    const crowded = new Set();
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].pt.x - pts[j].pt.x;
        const dy = pts[i].pt.y - pts[j].pt.y;
        if (Math.sqrt(dx * dx + dy * dy) < LABEL_MIN_PX) {
          crowded.add(pts[i].id);
          crowded.add(pts[j].id);
        }
      }
    }

    pts.forEach(({ id, el }) => {
      const label = el.querySelector('.dev-label');
      if (label) label.classList.toggle('label-visible', !crowded.has(id));
    });
  }

  // ── Range highlight on selection ─────────────────────────────────────────
  let _prevSelectedId = null;

  function _highlightRanges(devId) {
    const circles = rangeRefs[devId];
    if (!circles) return;
    circles.forEach(c => c.setStyle({ weight: 2.5, opacity: 1, fillOpacity: (c._origStyle?.fillOpacity ?? 0.07) * 2.5 }));
  }

  function _restoreRanges(devId) {
    const circles = rangeRefs[devId];
    if (!circles) return;
    circles.forEach(c => { if (c._origStyle) c.setStyle(c._origStyle); });
  }

  // ── Store binding ────────────────────────────────────────────────────────
  function _bindStoreEvents() {
    Store.on('devices', devices => {
      _buildCategoryLayers(devices);
      renderDevices(devices);
      _updateLayerCounts();
    });

    Store.on('positions', updates => {
      updates.forEach(u => {
        const m = markerRefs[u.device_id];
        if (m) m.setLatLng([u.latitude, u.longitude]);
      });
      _updateLabelVisibility();
    });

    Store.on('device_upserted', dev => {
      _upsertSingleDevice(dev);
      _updateLayerCounts();
    });

    Store.on('change', ({ key }) => {
      if (key === 'devices') {
        Store.get('devices').forEach(d => _updateMarkerStyle(d));
        setTimeout(_updateLabelVisibility, 0);
      }
    });

    // Tab change → re-filter map markers
    Store.on('tabChanged', tab => {
      _filterMarkersByTab(tab);
    });

    // Highlight selected device ranges
    Store.on('selectedDeviceId', id => {
      if (_prevSelectedId != null) {
        _restoreRanges(_prevSelectedId);
        const prevDev = Store.get('devices').find(d => Number(d.id) === Number(_prevSelectedId));
        if (prevDev) _updateMarkerStyle(prevDev);
      }
      if (id != null) {
        _highlightRanges(id);
        const dev = Store.get('devices').find(d => Number(d.id) === Number(id));
        if (dev) _updateMarkerStyle(dev);
      }
      _prevSelectedId = id;
    });
  }

  function _filterMarkersByTab(tab) {
    const categories = tab.categories;
    const devices = Store.get('devices') || [];
    devices.forEach(d => {
      const m = markerRefs[d.id];
      if (!m) return;
      const show = categories.length > 0 && categories.includes(d.category_code);
      const el = m.getElement?.();
      if (el) el.style.display = show ? '' : 'none';
      _setRangesVisible(d.id, show);
    });
  }

  // ── Markers ──────────────────────────────────────────────────────────────
  function _upsertSingleDevice(dev) {
    if (!dev || dev.id == null) return;
    const activeTab = TabSystem.getActive();

    // Если координат нет — убираем только этот маркер, не трогая остальные.
    if (dev.latitude == null || dev.longitude == null) {
      if (markerRefs[dev.id]) {
        markersLayer.removeLayer(markerRefs[dev.id]);
        delete markerRefs[dev.id];
      }
      _setRangesVisible(dev.id, false);
      return;
    }

    if (markerRefs[dev.id]) {
      markerRefs[dev.id].setLatLng([dev.latitude, dev.longitude]);
      markerRefs[dev.id].setPopupContent(_popupHtml(dev));
      _updateMarkerStyle(dev);
    } else {
      _createMarker(dev);
      _renderDeviceRanges(dev);
    }

    if (activeTab) {
      const show = activeTab.categories.length > 0 && activeTab.categories.includes(dev.category_code);
      const el = markerRefs[dev.id]?.getElement?.();
      if (el) el.style.display = show ? '' : 'none';
      _setRangesVisible(dev.id, show);
    }
    setTimeout(_updateLabelVisibility, 0);
  }

  function renderDevices(devices) {
    const existingIds = new Set(Object.keys(markerRefs));
    const incomingIds = new Set();
    const activeTab   = TabSystem.getActive();

    devices.forEach(d => {
      if (d.latitude == null || d.longitude == null) return;
      incomingIds.add(d.id);
      if (markerRefs[d.id]) {
        markerRefs[d.id].setLatLng([d.latitude, d.longitude]);
        _updateMarkerStyle(d);
      } else {
        _createMarker(d);
        _renderDeviceRanges(d);
      }
    });

    existingIds.forEach(id => {
      if (!incomingIds.has(id)) {
        markersLayer.removeLayer(markerRefs[id]);
        delete markerRefs[id];
      }
    });

    if (activeTab) _filterMarkersByTab(activeTab);
    setTimeout(_updateLabelVisibility, 0);
  }

  function _modeClass(dev) {
    if (!dev.online_status) return 's-offline';
    const m = dev.operational_mode;
    if (m === 'alarm')       return 's-alarm';
    if (m === 'warning')     return 's-warning';
    if (m === 'maintenance') return 's-maintenance';
    if (m === 'patrol')      return 's-patrol';
    if (m === 'active')      return 's-active';
    return 's-idle';
  }

  function _makeIcon(dev) {
    const cls = _modeClass(dev);
    const sel = Store.get('selectedDeviceId') === dev.id ? ' selected' : '';
    const inner = dev.icon_path
      ? `<img src="${dev.icon_path}" style="width:20px;height:20px;object-fit:contain;border-radius:2px;">`
      : (dev.category_icon || '📡');
    return L.divIcon({
      html: `<div class="dev-marker-wrap"><div class="dev-marker ${cls}${sel}">${inner}</div><div class="dev-label">${dev.name}</div></div>`,
      className: '', iconSize: [32, 46], iconAnchor: [16, 16], popupAnchor: [0, -20],
    });
  }

  function _createMarker(dev) {
    const marker = L.marker([dev.latitude, dev.longitude], {
      icon: _makeIcon(dev), zIndexOffset: _zIndex(dev),
    }).addTo(markersLayer);

    marker.bindPopup(_popupHtml(dev), { className: 'sentinel-popup', maxWidth: 220 });
    marker.on('click', () => Store.set('selectedDeviceId', dev.id));
    marker._isskbIconSig = _iconSignature(dev);
    marker._isskbRangeSig = _rangesSignature(dev);
    markerRefs[dev.id] = marker;
  }

  function _iconSignature(dev) {
    return [
      dev.online_status ? 1 : 0,
      dev.operational_mode || '',
      dev.category_icon || '',
      dev.icon_path || '',
      Number(Store.get('selectedDeviceId')) === Number(dev.id) ? 1 : 0,
    ].join('|');
  }

  function _rangesSignature(dev) {
    return JSON.stringify({
      online: !!dev.online_status,
      mode: dev.operational_mode || '',
      lat: dev.latitude,
      lon: dev.longitude,
      ranges: dev.detection_ranges || [],
    });
  }

  function _updateMarkerStyle(dev) {
    const m = markerRefs[dev.id];
    if (!m) return;

    const nextIconSig = _iconSignature(dev);
    if (m._isskbIconSig !== nextIconSig) {
      // Leaflet setIcon recreates DOM and causes visible blinking. Do it only
      // when status/icon/selection actually changed, not on every IMD value.
      m.setIcon(_makeIcon(dev));
      m._isskbIconSig = nextIconSig;
    }
    m.setZIndexOffset(_zIndex(dev));

    const nextRangeSig = _rangesSignature(dev);
    if (m._isskbRangeSig !== nextRangeSig) {
      // Rebuilding circles every 5 seconds also looks like disappearing layers.
      _renderDeviceRanges(dev);
      m._isskbRangeSig = nextRangeSig;
    }

    // Restore highlight if this device is still selected
    if (Number(Store.get('selectedDeviceId')) === Number(dev.id)) _highlightRanges(dev.id);
  }

  // ── Detection range circles ──────────────────────────────────────────────
  function _renderDeviceRanges(dev) {
    // Remove existing circles for this device
    if (rangeRefs[dev.id]) {
      rangeRefs[dev.id].forEach(c => rangesLayer.removeLayer(c));
      delete rangeRefs[dev.id];
    }

    const ranges = dev.detection_ranges;
    if (!ranges || !ranges.length || dev.latitude == null) return;

    const isOnline  = dev.online_status;
    const isAlarm   = dev.operational_mode === 'alarm';
    const isWarning = dev.operational_mode === 'warning';

    const circles = ranges.map(range => {
      let color   = isOnline ? (range.color || '#3b82f6') : '#4b5563';
      let opacity = isOnline ? (range.opacity ?? 0.07) : 0.03;
      let strokeO = isOnline ? 0.35 : 0.15;
      let weight  = 1;
      let dash    = isOnline ? null : '6 4';
      let cls     = 'range-circle';

      if (isAlarm)   { color = '#ef4444'; opacity = 0.12; strokeO = 0.6; cls += ' range-alarm'; }
      else if (isWarning) { color = '#eab308'; opacity = 0.08; cls += ' range-warn'; }
      else if (!isOnline) { cls += ' range-inactive'; }

      const style = { color, fillColor: color, fillOpacity: opacity, weight, opacity: strokeO, dashArray: dash };
      const c = L.circle([dev.latitude, dev.longitude], {
        radius: range.radius_m, ...style, className: cls, interactive: false,
      }).bindTooltip(`${dev.name} · ${range.label || 'Зона'} ${range.radius_m}м`, {
        permanent: false, className: 'range-tooltip',
      }).addTo(rangesLayer);
      c._origStyle  = style;
      c._rangeType  = (range.label || '').includes('обнаружен') ? 'detect' : 'action';
      return c;
    });

    if (circles.length) {
      rangeRefs[dev.id] = circles;
      // Применяем текущую видимость: категория + тип слоя + вкладка
      const catOk = catVisibility[dev.category_code] !== false;
      const tab   = TabSystem?.getActive?.();
      const cats  = tab ? tab.categories : null;
      const tabOk = cats === null || (cats.length > 0 && cats.includes(dev.category_code));
      _setRangesVisible(dev.id, catOk && tabOk);
    }
  }

  function _zIndex(dev) {
    if (!dev.online_status)                    return 0;
    if (dev.operational_mode === 'alarm')      return 400;
    if (dev.operational_mode === 'warning')    return 200;
    return 100;
  }

  function _popupHtml(dev) {
    const status = dev.online_status ? 'ОНЛАЙН' : 'ОФФЛАЙН';
    const modeLabels = { active:'Активно', idle:'Ожидание', alarm:'⚠ ТРЕВОГА',
                         warning:'Предупрежд.', maintenance:'ТО', patrol:'Патруль', offline:'Оффлайн' };
    const bat = dev.battery_level != null ? `<div class="map-popup-row"><span>Батарея</span><span>${dev.battery_level}%</span></div>` : '';
    return `
      <div class="map-popup-title">${dev.category_icon || ''} ${dev.name}</div>
      <div class="map-popup-row"><span>Статус</span><span>${status}</span></div>
      <div class="map-popup-row"><span>Режим</span><span>${modeLabels[dev.operational_mode] || dev.operational_mode}</span></div>
      <div class="map-popup-row"><span>Категория</span><span>${dev.category_name || '—'}</span></div>
      ${bat}
      <button class="map-popup-btn" onclick="Store.set('selectedDeviceId',${dev.id})">Подробнее →</button>
    `;
  }

  // ── Zones ────────────────────────────────────────────────────────────────
  function renderZones(zones) {
    zonesLayer.clearLayers();
    zones.forEach(z => {
      if (!z.lat_center || !z.lon_center) return;
      L.circle([z.lat_center, z.lon_center], {
        radius: z.radius_m || 200,
        color: z.color, fillColor: z.color,
        fillOpacity: 0.06, weight: 1, opacity: 0.35, dashArray: '4 4',
      }).bindTooltip(z.name, { permanent: false }).addTo(zonesLayer);
    });
  }

  function focusDevice(deviceId) {
    const dev = Store.get('devices').find(d => d.id === deviceId);
    if (!dev || dev.latitude == null) return;
    map.flyTo([dev.latitude, dev.longitude], 16, { duration: 0.9 });
    const m = markerRefs[deviceId];
    if (m) setTimeout(() => m.openPopup(), 1000);
  }

  function fitAll() {
    const devs = Store.get('devices').filter(d => d.latitude != null);
    if (!devs.length) return;
    map.fitBounds(L.latLngBounds(devs.map(d => [d.latitude, d.longitude])), { padding: [40, 40], maxZoom: 15 });
  }

  return { init, renderDevices, renderZones, focusDevice, fitAll };
})();
