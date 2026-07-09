const API = (() => {
  const BASE = '';

  async function request(path, opts = {}) {
    const res = await fetch(BASE + path, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
    if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
    return res.json();
  }

  async function upload(path, formData) {
    const res = await fetch(BASE + path, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(`Upload ${path} → ${res.status}`);
    return res.json();
  }

  return {
    getDevices:    ()      => request('/api/devices'),
    getDevice:     (id)    => request(`/api/devices/${id}`),
    patchDevice:   (id, body) => request(`/api/devices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
    uploadDeviceIcon: (id, file) => {
      const fd = new FormData();
      fd.append('file', file);
      return upload(`/api/devices/${id}/icon`, fd);
    },

    getIncidents:       (params) => {
      const qs = new URLSearchParams(params || {}).toString();
      return request('/api/incidents' + (qs ? '?' + qs : ''));
    },
    patchIncident:      (id, body) => request(`/api/incidents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
    updateIncidentStatus: (id, body) => request(`/api/incidents/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
    getIncidentComments: (id) => request(`/api/incidents/${id}/comments`),
    addIncidentComment:  (id, body) => request(`/api/incidents/${id}/comments`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

    getZones:    ()      => request('/api/zones'),
    getStats:    ()      => request('/api/zones/stats'),

    getLogo:     ()      => request('/api/config/logo'),
    uploadLogo:  (file)  => {
      const fd = new FormData();
      fd.append('file', file);
      return upload('/api/config/logo', fd);
    },
  };
})();
