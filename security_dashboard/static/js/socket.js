const Socket = (() => {
  let ws = null;
  let pingInterval = null;
  let reconnectTimer = null;
  const RECONNECT_MS = 3000;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => {
      document.getElementById('ws-indicator').classList.add('connected');
      document.getElementById('ws-label').textContent = 'В СЕТИ';
      clearTimeout(reconnectTimer);
      pingInterval = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('ping'); }, 25000);
    };

    ws.onmessage = ({ data }) => {
      let msg;
      try { msg = JSON.parse(data); } catch { return; }
      if (msg.type === 'pong') return;

      Store.set('lastUpdate', new Date());
      handleMessage(msg);
    };

    ws.onclose = () => {
      document.getElementById('ws-indicator').classList.remove('connected');
      document.getElementById('ws-label').textContent = 'ОТКЛЮЧЁН';
      clearInterval(pingInterval);
      reconnectTimer = setTimeout(connect, RECONNECT_MS);
    };

    ws.onerror = () => ws.close();
  }

  function _mergeDevice(device) {
    if (!device || device.id == null) return;
    if (typeof Store.upsertDevice === 'function') {
      Store.upsertDevice(device);
      return;
    }
    // Fallback для старого store.js
    const devices = Store.get('devices') || [];
    const idx = devices.findIndex(d => Number(d.id) === Number(device.id));
    if (idx >= 0) devices[idx] = { ...devices[idx], ...device };
    else devices.push(device);
    Store.set('devices', [...devices]);
  }

  let _reloadDevicesTimer = null;
  function _scheduleDevicesReload(delayMs = 5000) {
    // Reload only for real structural changes (new/deleted devices), not for
    // every telemetry update. Frequent /api/devices reloads were the reason
    // IMD cards/markers blinked and ПОКАЗАТЕЛИ disappeared.
    if (_reloadDevicesTimer) return;
    _reloadDevicesTimer = setTimeout(() => {
      _reloadDevicesTimer = null;
      API.getDevices()
        .then(devs => {
          if (typeof Store.mergeDevices === 'function') Store.mergeDevices(devs);
          else Store.set('devices', devs);
        })
        .catch(() => {});
    }, delayMs);
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case 'state_update':
        Store.updateDeviceState(msg.data);
        break;
      case 'position_update':
        Store.updateDevicePosition(msg.data);
        break;
      case 'metrics_update':
        Store.emit('metrics_update', msg.data);
        break;
      case 'incident_new':
        Store.addIncident(msg.data);
        break;
      case 'incident_resolved':
        Store.resolveIncident(msg.data);
        break;
      case 'device_updated':
        _mergeDevice(msg.data);
        break;
      case 'incident_updated':
        Store.emit('incident_updated', msg.data);
        break;
      case 'ext_heartbeat':
        ExtStatus.setStatus(msg.data.ok, msg.data.error);
        break;
      case 'devices_updated':
        if (msg.data && msg.data.device) {
          _mergeDevice(msg.data.device);
        } else if (msg.data && Number(msg.data.created || 0) > 0) {
          // New devices need one delayed list refresh. Pure updates do not.
          _scheduleDevicesReload(5000);
        }
        break;
    }
  }

  return { connect };
})();
