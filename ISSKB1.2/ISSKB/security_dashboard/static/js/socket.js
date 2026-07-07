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
      case 'device_updated': {
        const devices = Store.get('devices');
        const idx = devices.findIndex(d => d.id === msg.data.id);
        if (idx >= 0) {
          devices[idx] = { ...devices[idx], ...msg.data };
          Store.set('devices', [...devices]);
        }
        break;
      }
      case 'incident_updated':
        Store.emit('incident_updated', msg.data);
        break;
      case 'ext_heartbeat':
        ExtStatus.setStatus(msg.data.ok, msg.data.error);
        break;
      case 'devices_updated':
        API.getDevices().then(devs => Store.set('devices', devs)).catch(() => {});
        break;
    }
  }

  return { connect };
})();
