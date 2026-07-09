/**
 * Lightweight reactive store (pub/sub pattern).
 * Single source of truth for all dashboard state.
 *
 * IMD note:
 * Some background updates contain only state/position fields and can arrive
 * without extra_state. Do not let such partial packets clear IMD telemetry
 * from the currently selected card. All device merges below preserve and
 * deep-merge extra_state instead of replacing it with an empty object/null.
 */
const Store = (() => {
  const state = {
    devices: [],
    incidents: [],
    zones: [],
    stats: {},
    selectedDeviceId: null,
    filterMode: 'all',
    searchQuery: '',
    lastUpdate: null,
  };

  const listeners = {};

  function on(event, fn) {
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(fn);
    return () => { listeners[event] = listeners[event].filter(f => f !== fn); };
  }

  function emit(event, data) {
    (listeners[event] || []).forEach(fn => {
      try { fn(data); } catch (e) { console.error('[Store listener]', event, e); }
    });
  }

  function _coerceExtra(extra) {
    if (!extra) return {};
    if (typeof extra === 'string') {
      try {
        const parsed = JSON.parse(extra);
        return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
      } catch { return {}; }
    }
    return (typeof extra === 'object' && !Array.isArray(extra)) ? extra : {};
  }

  function _isNonEmptyObject(obj) {
    return obj && typeof obj === 'object' && !Array.isArray(obj) && Object.keys(obj).length > 0;
  }

  function _mergeDevice(oldDev, incoming) {
    if (!oldDev) {
      const first = { ...(incoming || {}) };
      first.extra_state = _coerceExtra(first.extra_state);
      return first;
    }

    const merged = { ...oldDev, ...(incoming || {}) };
    const oldExtra = _coerceExtra(oldDev.extra_state);
    const newExtra = _coerceExtra(incoming?.extra_state);

    // Preserve previous IMD telemetry when the incoming packet is a partial
    // state update or full-list refresh that omitted extra_state.
    merged.extra_state = _isNonEmptyObject(newExtra)
      ? { ...oldExtra, ...newExtra }
      : oldExtra;

    return merged;
  }

  function set(key, value) {
    if (key === 'devices' && Array.isArray(value)) {
      const currentById = new Map((state.devices || []).map(d => [Number(d.id), d]));
      state.devices = value.map(incoming => _mergeDevice(currentById.get(Number(incoming.id)), incoming));
      emit('devices', state.devices);
      emit('change', { key, value: state.devices });
      return;
    }

    state[key] = value;
    emit(key, value);
    emit('change', { key, value });
  }

  function get(key) { return state[key]; }

  // ── Device helpers ──────────────────────────────────────────────────────
  function updateDeviceState(updates) {
    updates.forEach(u0 => {
      const u = { ...(u0 || {}) };
      const id = Number(u.device_id ?? u.id);
      const dev = state.devices.find(d => Number(d.id) === id);
      if (!dev) return;

      // Do not overwrite extra_state with null/empty state_update packets.
      if (!_isNonEmptyObject(_coerceExtra(u.extra_state))) delete u.extra_state;
      Object.assign(dev, _mergeDevice(dev, u));
      emit('device_upserted', dev);
      emit('device_' + dev.id, dev);
    });
    // Existing components may listen to these generic events for counters,
    // but they should not rebuild the full map/list on every IMD packet.
    emit('devices_state_changed', state.devices);
    emit('change', { key: 'devices_state_changed' });
  }

  function updateDevicePosition(updates) {
    updates.forEach(u => {
      const dev = state.devices.find(d => Number(d.id) === Number(u.device_id));
      if (!dev) return;
      if (u.latitude != null)  dev.latitude = u.latitude;
      if (u.longitude != null) dev.longitude = u.longitude;
      emit('device_upserted', dev);
      emit('device_' + dev.id, dev);
    });
    emit('positions', updates);
  }

  function addIncident(inc) {
    state.incidents.unshift(inc);
    emit('incidents', state.incidents);
    emit('incident_new', inc);
  }

  function resolveIncident(data) {
    const inc = state.incidents.find(i => i.id === data.id);
    if (inc) {
      inc.status = data.status;
      inc.resolved_at = data.resolved_at;
    }
    emit('incidents', state.incidents);
    emit('incident_resolved', data);
  }

  function getFilteredDevices() {
    const q = (state.searchQuery || '').toLowerCase();
    return state.devices.filter(d => {
      if (q && !d.name.toLowerCase().includes(q) &&
               !d.category_name?.toLowerCase().includes(q) &&
               !d.zone_name?.toLowerCase().includes(q)) return false;
      const mode = d.operational_mode;
      switch (state.filterMode) {
        case 'alarm':   return mode === 'alarm';
        case 'warning': return mode === 'warning';
        case 'offline': return !d.online_status;
        default:        return true;
      }
    });
  }

  function upsertDevice(device) {
    if (!device || device.id == null) return;
    const idx = state.devices.findIndex(d => Number(d.id) === Number(device.id));
    let merged;
    if (idx >= 0) {
      merged = _mergeDevice(state.devices[idx], device);
      state.devices[idx] = merged;
    } else {
      merged = _mergeDevice(null, device);
      state.devices.push(merged);
    }
    emit('device_upserted', merged);
    emit('device_' + merged.id, merged);
  }

  function mergeDevices(devices) {
    if (!Array.isArray(devices)) return;
    devices.forEach(upsertDevice);
    emit('devices_merged', state.devices);
  }

  return {
    on, emit, set, get,
    upsertDevice, mergeDevices, updateDeviceState, updateDevicePosition,
    addIncident, resolveIncident, getFilteredDevices
  };
})();
