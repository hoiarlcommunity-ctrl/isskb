/**
 * Lightweight reactive store (pub/sub pattern).
 * Single source of truth for all dashboard state.
 */
const Store = (() => {
  const state = {
    devices: [],          // full device list with positions + states
    incidents: [],        // incident list
    zones: [],
    stats: {},
    selectedDeviceId: null,
    filterMode: 'all',    // 'all' | 'alarm' | 'warning' | 'offline'
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
    (listeners[event] || []).forEach(fn => fn(data));
  }

  function set(key, value) {
    state[key] = value;
    emit(key, value);
    emit('change', { key, value });
  }

  function get(key) { return state[key]; }

  // ── Device helpers ──────────────────────────────────────────────────────
  function updateDeviceState(updates) {
    updates.forEach(u => {
      const dev = state.devices.find(d => d.id === u.device_id);
      if (!dev) return;
      Object.assign(dev, u);
    });
    emit('devices', state.devices);
    emit('change', { key: 'devices' });
  }

  function updateDevicePosition(updates) {
    updates.forEach(u => {
      const dev = state.devices.find(d => d.id === u.device_id);
      if (!dev) return;
      dev.latitude  = u.latitude;
      dev.longitude = u.longitude;
    });
    emit('positions', updates);
    emit('change', { key: 'devices' });
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
    const q = state.searchQuery.toLowerCase();
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

  return { on, emit, set, get, updateDeviceState, updateDevicePosition,
           addIncident, resolveIncident, getFilteredDevices };
})();
