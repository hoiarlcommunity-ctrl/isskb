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
      const dev = Store.get('devices').find(d => d.id === id);
      if (!dev) { _showEmpty(); return; }
      _renderDevice(dev);
      try {
        const full = await API.getDevice(id);
        if (Store.get('selectedDeviceId') === id) {
          _renderMetrics(full.metrics || {}, full.extra_state);
        }
      } catch(e) { /* silent */ }
    });

    Store.on('metrics_update', (batch) => {
      const selId = Store.get('selectedDeviceId');
      if (!selId) return;
      const entry = batch.find(b => b.device_id === selId);
      if (!entry) return;
      entry.metrics.forEach(m => {
        const row = document.querySelector(`.metric-row[data-key="${m.key}"]`);
        if (row) {
          const valEl = row.querySelector('.m-val');
          if (valEl) {
            valEl.textContent = _fmtValue(m.value, m.key);
            valEl.classList.add('anim-fade-in');
            setTimeout(() => valEl.classList.remove('anim-fade-in'), 300);
          }
        }
      });
    });

    Store.on('change', ({ key }) => {
      if (key !== 'devices') return;
      const id = Store.get('selectedDeviceId');
      if (!id) return;
      const dev = Store.get('devices').find(d => d.id === id);
      if (dev) _renderLiveState(dev);
    });
  }

  function _showEmpty() {
    detailPanel.classList.add('hidden');
    noSelection.classList.remove('hidden');
  }

  function _renderDevice(dev) {
    noSelection.classList.add('hidden');
    detailPanel.classList.remove('hidden');
    detailPanel.classList.add('anim-slide-in');
    setTimeout(() => detailPanel.classList.remove('anim-slide-in'), 250);

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
      const d = new Date(dev.last_heartbeat + (dev.last_heartbeat.endsWith('Z') ? '' : 'Z'));
      refs.lastSeen.textContent = _relTime(d);
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

  function _renderMetrics(metricsObj, extraState) {
    const LABELS = {
      fps: 'Частота кадров', bitrate: 'Битрейт', temperature: 'Температура',
      sensitivity: 'Чувствительность', battery_voltage: 'Напряжение батареи',
      door_events_1h: 'Проходов за час', readers_online: 'Считывателей онлайн',
      speed: 'Скорость', gps_accuracy: 'Точность GPS',
      smoke_density: 'Плотность дыма', humidity: 'Влажность',
      beam_status: 'Луч', alignement: 'Юстировка',
      channels_active: 'Активных каналов', cpu_load: 'Нагрузка CPU',
      storage_used: 'Занято хранилище',
    };

    refs.metrics.innerHTML = '';

    // Standard time-series metrics
    Object.entries(metricsObj).forEach(([key, arr]) => {
      if (!arr || !arr.length) return;
      const latest = arr[0];
      const row = document.createElement('div');
      row.className = 'metric-row';
      row.dataset.key = key;
      row.innerHTML = `
        <span class="m-key">${LABELS[key] || key}</span>
        <span><span class="m-val">${_fmtValue(latest.value, key)}</span><span class="m-unit"> ${latest.unit || ''}</span></span>
      `;
      refs.metrics.appendChild(row);
    });

    // Extra state JSONB fields (from external API sync)
    if (extraState && typeof extraState === 'object' && !Array.isArray(extraState)) {
      Object.entries(extraState).forEach(([key, val]) => {
        const row = document.createElement('div');
        row.className = 'metric-row';
        row.dataset.key = `es_${key}`;
        const displayVal = typeof val === 'object' ? JSON.stringify(val) : String(val);
        row.innerHTML = `
          <span class="m-key" style="color:var(--txt-secondary)">${LABELS[key] || key}</span>
          <span class="m-val" style="font-size:11px;font-family:monospace">${displayVal}</span>
        `;
        refs.metrics.appendChild(row);
      });
    }

    if (!refs.metrics.children.length) {
      refs.metrics.innerHTML = '<div style="color:var(--txt-muted);font-size:11px;padding:4px 0">Нет данных</div>';
    }
  }

  function _fmtValue(v, key) {
    if (v == null) return '—';
    if (key === 'beam_status') return v >= 1 ? 'OK' : 'РАЗРЫВ';
    if (Number.isInteger(v)) return v;
    return parseFloat(parseFloat(v).toFixed(2));
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
