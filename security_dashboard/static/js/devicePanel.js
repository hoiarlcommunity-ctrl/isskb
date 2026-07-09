const DevicePanel = (() => {
  const detailPanel = document.getElementById('device-detail-panel');
  const noSelection = document.getElementById('no-selection');

  const refs = {
    icon:         document.getElementById('dd-icon'),
    name:         document.getElementById('dd-name'),
    serial:       document.getElementById('dd-serial'),
    statusBadge:  document.getElementById('dd-status-badge'),
    modeBadge:    document.getElementById('dd-mode-badge'),
    model:        document.getElementById('dd-model'),
    ip:           document.getElementById('dd-ip'),
    fw:           document.getElementById('dd-fw'),
    responsible:  document.getElementById('dd-responsible'),
    batteryRow:   document.getElementById('dd-battery-row'),
    batteryVal:   document.getElementById('dd-battery-val'),
    batteryBar:   document.getElementById('dd-battery-bar'),
    portRow:      document.getElementById('dd-port-row'),
    portVal:      document.getElementById('dd-port'),
    typeRow:      document.getElementById('dd-type-row'),
    typeVal:      document.getElementById('dd-device-type'),
    priorityRow:  document.getElementById('dd-priority-row'),
    priorityVal:  document.getElementById('dd-priority'),
    extKeyRow:    document.getElementById('dd-extkey-row'),
    extKeyVal:    document.getElementById('dd-external-key'),
    signalRow:    document.getElementById('dd-signal-row'),
    signalVal:    document.getElementById('dd-signal-val'),
    signalBar:    document.getElementById('dd-signal-bar'),
    lastSeen:     document.getElementById('dd-last-seen'),
    coords:       document.getElementById('dd-coords'),
    metrics:      document.getElementById('dd-metrics'),
    maintenanceBtn: document.getElementById('action-maintenance'),
    iconInput:    document.getElementById('dd-icon-upload'),
  };

  // Cache last non-empty extra_state for each device. Some periodic state/list
  // updates arrive without extra_state and should not clear IMD readings in
  // the details panel.
  const _extraCache = new Map();
  let _metricsPanelDeviceId = null;

  const IMD_EXTRA_KEYS = [
    'dose_rate', 'error_percent', 'accumulated_dose', 'vbd_data',
    'imd_power', 'imd_mode', 'imd_time', 'imd_ext_type',
    'imd_alarm_pult_dr', 'imd_alarm_pult_ed', 'imd_alarm_vbd', 'imd_last_error',
    'imd_packet_len', 'imd_packet_type', 'imd_crc', 'imd_status_byte', 'imd_error_byte',
    'imd_low_battery', 'imd_external_power', 'imd_pult_dr_base', 'imd_pult_ed_base',
    'imd_vbd_base', 'imd_raw_packet',
  ];

  function _rememberExtra(devOrId, extraMaybe) {
    const id = typeof devOrId === 'object' ? devOrId?.id : devOrId;
    const dev = typeof devOrId === 'object' ? devOrId : null;

    // Полные данные ИМД иногда приходят не только в extra_state, а также
    // отдельными верхнеуровневыми полями. Сохраняем оба варианта, чтобы
    // очередной частичный пакет не очищал ПОКАЗАТЕЛИ.
    const incoming = {
      ..._coerceExtra(dev ? dev.extra_state : extraMaybe),
      ..._extractTopLevelImd(dev),
    };
    const prev = _extraCache.get(Number(id)) || {};
    const merged = Object.keys(incoming).length ? { ...prev, ...incoming } : prev;
    if (id != null && Object.keys(merged).length) _extraCache.set(Number(id), merged);
    return merged;
  }

  function _extractTopLevelImd(dev) {
    if (!dev || typeof dev !== 'object') return {};
    const out = {};
    IMD_EXTRA_KEYS.forEach(k => {
      if (dev[k] !== null && dev[k] !== undefined && String(dev[k]) !== '') out[k] = dev[k];
    });
    return out;
  }

  function _extraForDevice(dev) {
    return _rememberExtra(dev);
  }

  function init() {
    document.getElementById('dd-close').addEventListener('click', () => {
      Store.set('selectedDeviceId', null);
    });

    document.getElementById('action-focus').addEventListener('click', () => {
      const id = Store.get('selectedDeviceId');
      if (id) MapWidget.focusDevice(id);
    });

    // Acknowledge open incidents
    document.getElementById('action-ack').addEventListener('click', async () => {
      const id = Store.get('selectedDeviceId');
      if (!id) return;
      const incidents = Store.get('incidents').filter(i => i.device_id === id && i.status === 'open');
      for (const inc of incidents) {
        await API.updateIncidentStatus(inc.id, { status: 'in_progress', comment: 'Подтверждено оператором' });
      }
      const fresh = await API.getIncidents();
      Store.set('incidents', fresh);
    });

    // Maintenance mode button
    if (refs.maintenanceBtn) {
      refs.maintenanceBtn.addEventListener('click', () => {
        const id = Store.get('selectedDeviceId');
        if (!id) return;
        const dev = Store.get('devices').find(d => d.id === id);
        if (!dev) return;
        const modal = document.getElementById('maintenance-modal');
        if (modal) {
          modal.dataset.deviceId = id;
          const title = modal.querySelector('#mm-device-name');
          if (title) title.textContent = dev.name;
          const commentEl = modal.querySelector('#mm-comment');
          if (commentEl) commentEl.value = '';
          modal.classList.add('visible');
        }
      });
    }

    // Icon upload
    if (refs.iconInput) {
      refs.iconInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const id = Store.get('selectedDeviceId');
        if (!id) return;
        try {
          const res = await API.uploadDeviceIcon(id, file);
          // Update the icon element with uploaded image
          refs.icon.innerHTML = `<img src="${res.icon_path}" style="width:32px;height:32px;object-fit:contain">`;
          Toast?.show?.('Иконка загружена', 'success');
        } catch (err) {
          Toast?.show?.('Ошибка загрузки иконки', 'error');
        }
        refs.iconInput.value = '';
      });
    }

    Store.on('selectedDeviceId', async (id) => {
      if (!id) { _showEmpty(); return; }
      const dev = Store.get('devices').find(d => Number(d.id) === Number(id));
      if (!dev) { _showEmpty(); return; }
      _renderDevice(dev, true);
      try {
        const full = await API.getDevice(id);
        if (Number(Store.get('selectedDeviceId')) === Number(id)) {
          const extra = _rememberExtra(id, full.extra_state || dev.extra_state);
          _renderDevice({ ...dev, ...full, extra_state: extra }, false);
          _renderMetrics(full.metrics || {}, extra);
        }
      } catch(e) { /* silent */ }
    });

    Store.on('metrics_update', (batch) => {
      const selId = Store.get('selectedDeviceId');
      if (!selId || !Array.isArray(batch)) return;
      const entry = batch.find(b => Number(b.device_id) === Number(selId));
      if (!entry || !Array.isArray(entry.metrics)) return;

      // Обновляем значения в уже открытой карточке без полной перерисовки.
      // Если строк ещё нет, создаём их через _renderMetrics(), но без очистки
      // существующего содержимого панели.
      const metricObj = {};
      entry.metrics.forEach(m => {
        metricObj[m.key] = [{
          value: m.raw || m.value,
          unit: m.raw ? '' : (m.unit || ''),
        }];
      });
      const dev = Store.get('devices').find(d => Number(d.id) === Number(selId));
      _renderMetrics(metricObj, _extraForDevice(dev));
    });

    Store.on('device_upserted', (dev) => {
      const id = Store.get('selectedDeviceId');
      if (!id || !dev || Number(dev.id) !== Number(id)) return;
      _renderDevice(dev, false);
      _renderMetrics({}, _extraForDevice(dev));
    });

    // Fallback для полной перезагрузки списка устройств от старых источников.
    Store.on('change', ({ key }) => {
      if (key !== 'devices') return;
      const id = Store.get('selectedDeviceId');
      if (!id) return;
      const dev = Store.get('devices').find(d => Number(d.id) === Number(id));
      if (!dev) return;
      _renderDevice(dev, false);
      _renderMetrics({}, _extraForDevice(dev));
    });
  }

  function _showEmpty() {
    _metricsPanelDeviceId = null;
    detailPanel.classList.add('hidden');
    noSelection.classList.remove('hidden');
  }

  function _renderDevice(dev, animate = true) {
    noSelection.classList.add('hidden');
    detailPanel.classList.remove('hidden');
    if (animate) {
      detailPanel.classList.add('anim-slide-in');
      setTimeout(() => detailPanel.classList.remove('anim-slide-in'), 250);
    }

    // Icon: use uploaded icon_path if available, otherwise emoji
    if (dev.icon_path) {
      refs.icon.innerHTML = `<img src="${dev.icon_path}" style="width:32px;height:32px;object-fit:contain">`;
    } else {
      refs.icon.textContent = dev.category_icon || '📡';
    }

    refs.name.textContent        = dev.name;
    refs.serial.textContent      = dev.serial_number || '—';
    refs.model.textContent       = [dev.model, dev.manufacturer].filter(Boolean).join(' · ') || '—';
    refs.ip.textContent          = dev.ip_address || '—';
    refs.fw.textContent          = dev.firmware_version || '—';
    refs.responsible.textContent = dev.responsible_person || '—';

    // New fields — only show row if value is present
    if (refs.portRow) {
      const hasPort = dev.port != null;
      refs.portRow.style.display = hasPort ? '' : 'none';
      if (hasPort) refs.portVal.textContent = dev.port;
    }
    if (refs.typeRow) {
      const hasType = !!dev.device_type;
      refs.typeRow.style.display = hasType ? '' : 'none';
      if (hasType) refs.typeVal.textContent = dev.device_type;
    }
    if (refs.priorityRow) {
      const hasPri = dev.priority != null && dev.priority !== 0;
      refs.priorityRow.style.display = hasPri ? '' : 'none';
      if (hasPri) refs.priorityVal.textContent = dev.priority;
    }
    if (refs.extKeyRow) {
      const hasKey = !!dev.external_key;
      refs.extKeyRow.style.display = hasKey ? '' : 'none';
      if (hasKey) refs.extKeyVal.textContent = dev.external_key;
    }

    if (dev.latitude != null) {
      refs.coords.textContent = `${parseFloat(dev.latitude).toFixed(5)}, ${parseFloat(dev.longitude).toFixed(5)}`;
    } else {
      refs.coords.textContent = '—';
    }

    _renderLiveState(dev);
    // Показываем extra_state сразу из списка устройств. Если очередной
    // частичный update пришёл без extra_state, берём последнее известное
    // значение из кэша, чтобы ПОКАЗАТЕЛИ не исчезали.
    _renderMetrics({}, _extraForDevice(dev));
  }

  function _renderLiveState(dev) {
    refs.statusBadge.textContent = dev.online_status ? 'ОНЛАЙН' : 'ОФФЛАЙН';
    refs.statusBadge.className   = 'status-badge ' + (dev.online_status ? 'online' : 'offline');
    refs.modeBadge.textContent   = _modeLabel(dev.operational_mode);
    refs.modeBadge.className     = 'mode-badge ' + (dev.operational_mode || 'idle');

    // Battery
    if (dev.battery_level != null) {
      refs.batteryRow.classList.remove('hidden');
      const bat = dev.battery_level;
      refs.batteryVal.textContent = bat;
      refs.batteryBar.style.width = bat + '%';
      refs.batteryBar.style.background = bat >= 50 ? 'var(--s-online)' : bat >= 20 ? 'var(--s-warning)' : 'var(--s-critical)';
    } else {
      refs.batteryRow.classList.add('hidden');
    }

    // Signal strength
    if (refs.signalRow) {
      if (dev.signal_strength != null) {
        refs.signalRow.style.display = '';
        const sig = dev.signal_strength;
        refs.signalVal.textContent = sig;
        refs.signalBar.style.width = sig + '%';
        refs.signalBar.style.background = sig >= 60 ? 'var(--s-online)' : sig >= 30 ? 'var(--s-warning)' : 'var(--s-critical)';
      } else {
        refs.signalRow.style.display = 'none';
      }
    }

    // Last seen
    if (dev.last_heartbeat) {
      const d = _parseDate(dev.last_heartbeat);
      refs.lastSeen.textContent = d ? _relTime(d) : '—';
    } else {
      refs.lastSeen.textContent = '—';
    }

    // Maintenance button label
    if (refs.maintenanceBtn) {
      const isTO = dev.operational_mode === 'maintenance';
      refs.maintenanceBtn.textContent = isTO ? '🔧 В режиме ТО' : '🔧 Перевести в ТО';
      refs.maintenanceBtn.disabled = isTO;
    }
  }

  function _coerceExtra(extraState) {
    if (!extraState) return {};
    if (typeof extraState === 'string') {
      try { return JSON.parse(extraState); } catch { return {}; }
    }
    if (typeof extraState === 'object' && !Array.isArray(extraState)) return extraState;
    return {};
  }

  function _parseDate(value) {
    if (!value) return null;
    const s = String(value);
    const hasTZ = /([zZ]|[+-]\d{2}:?\d{2})$/.test(s);
    const d = new Date(hasTZ ? s : `${s}Z`);
    return Number.isFinite(d.getTime()) ? d : null;
  }

  function _renderMetrics(metricsObj, extraState) {
    extraState = _coerceExtra(extraState);
    metricsObj = metricsObj || {};
    const LABELS = {
      fps: 'Частота кадров', bitrate: 'Битрейт', temperature: 'Температура',
      sensitivity: 'Чувствительность', battery_voltage: 'Напряжение батареи',
      door_events_1h: 'Проходов за час', readers_online: 'Считывателей онлайн',
      speed: 'Скорость', gps_accuracy: 'Точность GPS',
      smoke_density: 'Плотность дыма', humidity: 'Влажность',
      beam_status: 'Луч', alignement: 'Юстировка',
      channels_active: 'Активных каналов', cpu_load: 'Нагрузка CPU',
      storage_used: 'Занято хранилище',

      // ИМД-07: поля приходят из services/imd_reader.py → extra_state JSONB
      dose_rate: 'Мощность дозы',
      error_percent: 'Погрешность',
      accumulated_dose: 'Накопленная доза',
      vbd_data: 'ВБД',
      imd_mode: 'Режим ИМД',
      imd_time: 'Время ИМД',
      imd_power: 'Питание ИМД',
      imd_ext_type: 'Тип ВБД',
      imd_alarm_pult_dr: 'Порог МД пульта',
      imd_alarm_pult_ed: 'Порог НД пульта',
      imd_alarm_vbd: 'Порог ВБД',
      imd_last_error: 'Ошибка ИМД',
      imd_packet_len: 'Длина пакета',
      imd_packet_type: 'Тип пакета',
      imd_crc: 'CRC',
      imd_status_byte: 'Статус-байт',
      imd_error_byte: 'Байт ошибки',
      imd_low_battery: 'Разряд батареи',
      imd_external_power: 'Внешнее питание',
      imd_pult_dr_base: 'МД пульта, базовое',
      imd_pult_ed_base: 'НД пульта, базовое',
      imd_vbd_base: 'ВБД, базовое',
      imd_raw_packet: 'Raw-пакет',
    };

    const EXTRA_ORDER = [
      'dose_rate', 'error_percent', 'accumulated_dose', 'vbd_data',
      'imd_power', 'imd_mode', 'imd_time', 'imd_ext_type',
      'imd_alarm_pult_dr', 'imd_alarm_pult_ed', 'imd_alarm_vbd', 'imd_last_error',
      'imd_packet_type', 'imd_packet_len', 'imd_crc', 'imd_status_byte', 'imd_error_byte',
      'imd_low_battery', 'imd_external_power', 'imd_pult_dr_base', 'imd_pult_ed_base',
      'imd_vbd_base', 'imd_raw_packet',
    ];

    const selectedId = Number(Store.get('selectedDeviceId'));
    if (_metricsPanelDeviceId !== selectedId) {
      // Очищаем блок только при выборе другого устройства. На телеметрии
      // этого же устройства строки обновляются точечно, поэтому карточка не
      // мигает и не показывает «Нет данных» на долю секунды.
      refs.metrics.innerHTML = '';
      _metricsPanelDeviceId = selectedId;
    }

    const rows = [];

    // Standard time-series metrics
    Object.entries(metricsObj).forEach(([key, arr]) => {
      if (!arr || !arr.length) return;
      const latest = arr[0];
      const rawValue = latest.raw || latest.value;
      rows.push({
        domKey: `metric_${key}`,
        altKeys: [key, `es_${key}`],
        label: LABELS[key] || key,
        value: _fmtValue(rawValue, key),
        unit: latest.unit || '',
        kind: 'metric',
      });
    });

    // Extra state JSONB fields (from external API / встроенного IMD sync).
    if (extraState && typeof extraState === 'object' && !Array.isArray(extraState)) {
      Object.entries(extraState)
        .filter(([, val]) => val !== null && val !== undefined && String(val) !== '')
        .sort(([a], [b]) => {
          const ia = EXTRA_ORDER.indexOf(a);
          const ib = EXTRA_ORDER.indexOf(b);
          if (ia >= 0 || ib >= 0) return (ia >= 0 ? ia : 999) - (ib >= 0 ? ib : 999);
          return a.localeCompare(b);
        })
        .forEach(([key, val]) => {
          const displayVal = typeof val === 'object' ? JSON.stringify(val) : String(val);
          rows.push({
            domKey: `es_${key}`,
            altKeys: [`metric_${key}`, key],
            label: LABELS[key] || key,
            value: displayVal,
            unit: '',
            kind: 'extra',
          });
        });
    }

    if (!rows.length) {
      // Не затираем существующие строки пустым частичным обновлением.
      if (refs.metrics.querySelector('.metric-row')) return;
      if (!refs.metrics.querySelector('[data-empty-metrics="1"]')) {
        refs.metrics.innerHTML = '<div data-empty-metrics="1" style="color:var(--txt-muted);font-size:11px;padding:4px 0">Нет данных</div>';
      }
      return;
    }

    refs.metrics.querySelectorAll('[data-empty-metrics="1"]').forEach(el => el.remove());

    // Если одно и то же значение пришло и как metric, и как extra_state,
    // показываем extra_state-строку как основную, а numeric metric используем
    // только для старых устройств без extra_state.
    const seen = new Set();
    const ordered = rows.filter(r => {
      const canonical = r.domKey.replace(/^metric_/, '').replace(/^es_/, '');
      const isExtraPreferred = rows.some(x => x.domKey === `es_${canonical}`);
      if (r.kind === 'metric' && isExtraPreferred) return false;
      if (seen.has(r.domKey)) return false;
      seen.add(r.domKey);
      return true;
    });

    ordered.forEach(r => _upsertMetricRow(r));
  }

  function _findMetricRow(keys) {
    const all = Array.from(refs.metrics.querySelectorAll('.metric-row'));
    return all.find(row => keys.includes(row.dataset.key));
  }

  function _upsertMetricRow(rowData) {
    const keys = [rowData.domKey, ...(rowData.altKeys || [])];
    let row = _findMetricRow(keys);
    if (!row) {
      row = document.createElement('div');
      row.className = 'metric-row';
      row.dataset.key = rowData.domKey;
      row.innerHTML = `
        <span class="m-key"></span>
        <span><span class="m-val"></span><span class="m-unit"></span></span>
      `;
      refs.metrics.appendChild(row);
    }

    row.dataset.key = rowData.domKey;
    const keyEl = row.querySelector('.m-key');
    const valEl = row.querySelector('.m-val');
    const unitEl = row.querySelector('.m-unit');

    if (keyEl && keyEl.textContent !== rowData.label) keyEl.textContent = rowData.label;
    if (valEl && valEl.textContent !== String(rowData.value)) {
      valEl.textContent = rowData.value;
      valEl.classList.add('anim-fade-in');
      setTimeout(() => valEl.classList.remove('anim-fade-in'), 300);
    }
    if (unitEl) unitEl.textContent = rowData.unit ? ` ${rowData.unit}` : '';
  }

  function _fmtValue(v, key) {
    if (v == null) return '—';
    if (key === 'beam_status') return v >= 1 ? 'OK' : 'РАЗРЫВ';
    if (typeof v === 'string' && /[^0-9.,+\-\s]/.test(v)) return v;
    const num = Number(String(v).replace(',', '.'));
    if (!Number.isFinite(num)) return String(v);
    if (Number.isInteger(num)) return num;
    return parseFloat(num.toFixed(3));
  }

  function _modeLabel(mode) {
    const l = { active:'АКТИВНО', idle:'ОЖИДАНИЕ', alarm:'⚠ ТРЕВОГА', warning:'ПРЕДУПРЕЖД.',
                maintenance:'ОБСЛУЖИВАНИЕ', patrol:'ПАТРУЛЬ', offline:'ОФФЛАЙН' };
    return l[mode] || (mode || 'НЕИЗВЕСТНО').toUpperCase();
  }

  function _relTime(date) {
    const sec = Math.floor((Date.now() - date.getTime()) / 1000);
    if (sec < 5)   return 'Только что';
    if (sec < 60)  return `${sec} сек. назад`;
    const m = Math.floor(sec / 60);
    if (m < 60)    return `${m} мин. назад`;
    return `${Math.floor(m / 60)} ч. назад`;
  }

  return { init };
})();
