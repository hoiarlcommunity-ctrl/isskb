const IncidentPanel = (() => {
  const feedEl     = document.getElementById('incident-feed');
  const countBadge = document.getElementById('incident-count-badge');

  const SEV = {
    critical: { dot: 'dot-critical', cls: 'sev-critical', label: 'КРИТИЧ.' },
    high:     { dot: 'dot-warning',  cls: 'sev-high',     label: 'ВЫСОКИЙ' },
    medium:   { dot: 'dot-patrol',   cls: 'sev-medium',   label: 'СРЕДНИЙ' },
    low:      { dot: 'dot-offline',  cls: 'sev-low',      label: 'НИЗКИЙ'  },
    info:     { dot: 'dot-offline',  cls: 'sev-info',     label: 'ИНФО'    },
  };

  const STATUS_LABELS = {
    open:        'Открыт',
    in_progress: 'В работе',
    closed:      'Закрыт',
  };

  const STATUS_ORDER = { open: 0, in_progress: 1, closed: 2 };

  function init() {
    Store.on('incidents', _render);
    Store.on('incident_new',      inc => { _prependItem(inc); _updateCount(); });
    Store.on('incident_resolved', ()  => _render(Store.get('incidents')));
    Store.on('incident_updated',  upd => {
      const list = Store.get('incidents');
      const idx  = list.findIndex(i => i.id === upd.id);
      if (idx >= 0) {
        list[idx] = { ...list[idx], ...upd };
        Store.set('incidents', list);
      }
    });

    // Status modal handlers
    const modal     = document.getElementById('incident-status-modal');
    const cancelBtn = document.getElementById('ism-cancel');
    const saveBtn   = document.getElementById('ism-save');

    if (cancelBtn) cancelBtn.addEventListener('click', () => modal.classList.remove('visible'));
    if (saveBtn)   saveBtn.addEventListener('click',   _submitStatusChange);

    // Close on backdrop click
    if (modal) {
      modal.addEventListener('click', e => {
        if (e.target === modal) modal.classList.remove('visible');
      });
    }
  }

  // ── Open status-change modal ─────────────────────────────────────────────
  function _openStatusModal(inc) {
    const modal = document.getElementById('incident-status-modal');
    if (!modal) return;
    modal.dataset.incidentId = inc.id;

    const title = modal.querySelector('#ism-title');
    if (title) title.textContent = inc.title;

    // Set current status as selected
    const radios = modal.querySelectorAll('input[name="ism-status"]');
    radios.forEach(r => { r.checked = r.value === inc.status; });

    const commentEl = modal.querySelector('#ism-comment');
    if (commentEl) commentEl.value = '';

    // Load existing comments
    _loadComments(inc.id);

    modal.classList.add('visible');
  }

  async function _loadComments(incidentId) {
    const container = document.getElementById('ism-comments');
    if (!container) return;
    container.innerHTML = '<div class="ism-loading">Загрузка…</div>';
    try {
      const comments = await API.getIncidentComments(incidentId);
      if (!comments.length) {
        container.innerHTML = '<div class="ism-no-comments">Комментариев пока нет</div>';
        return;
      }
      container.innerHTML = comments.map(c => `
        <div class="ism-comment">
          <div class="ism-comment-meta">
            <span class="ism-comment-author">${c.author}</span>
            <span class="ism-comment-time">${_fmtTime(_parseDate(c.created_at))}</span>
            ${c.new_status ? `<span class="ism-comment-status">${STATUS_LABELS[c.new_status] || c.new_status}</span>` : ''}
          </div>
          <div class="ism-comment-text">${_escHtml(c.text)}</div>
        </div>
      `).join('');
    } catch {
      container.innerHTML = '<div class="ism-no-comments">Ошибка загрузки</div>';
    }
  }

  async function _submitStatusChange() {
    const modal     = document.getElementById('incident-status-modal');
    if (!modal) return;
    const incId     = modal.dataset.incidentId;
    const statusEl  = modal.querySelector('input[name="ism-status"]:checked');
    const commentEl = modal.querySelector('#ism-comment');
    if (!statusEl) return;

    const newStatus = statusEl.value;
    const comment   = commentEl ? commentEl.value.trim() : '';

    try {
      const saveBtn = document.getElementById('ism-save');
      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Сохранение…'; }

      await API.updateIncidentStatus(incId, { status: newStatus, comment });

      // Refresh incidents
      const fresh = await API.getIncidents();
      Store.set('incidents', fresh);
      modal.classList.remove('visible');
    } catch(e) {
      Toast?.show?.('Ошибка изменения статуса', 'error');
    } finally {
      const saveBtn = document.getElementById('ism-save');
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Сохранить'; }
    }
  }

  // ── Render list ──────────────────────────────────────────────────────────
  function _render(incidents) {
    feedEl.innerHTML = '';
    if (!incidents.length) {
      feedEl.innerHTML = '<div style="color:var(--txt-muted);font-size:11px;padding:12px var(--panel-pad)">Инцидентов нет</div>';
      countBadge.textContent = '0';
      return;
    }

    const sorted = [...incidents].sort((a, b) => {
      const sevOrder = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
      const ao = STATUS_ORDER[a.status] ?? 5, bo = STATUS_ORDER[b.status] ?? 5;
      if (ao !== bo) return ao - bo;
      return (sevOrder[a.severity] ?? 5) - (sevOrder[b.severity] ?? 5);
    });

    sorted.forEach(inc => feedEl.appendChild(_buildItem(inc)));
    _updateCount();
  }

  function _buildItem(inc) {
    const s  = SEV[inc.severity] || SEV.info;
    const el = document.createElement('div');
    el.className = `inc-item ${s.cls}` + (inc.status === 'closed' ? ' resolved' : '');
    el.dataset.id = inc.id;

    const time = inc.created_at ? _fmtTime(_parseDate(inc.created_at)) : '—';
    const statusLabel = STATUS_LABELS[inc.status] || inc.status;

    const displayName = inc.device_name || inc.title;
    const displaySub  = inc.device_name && inc.title !== inc.device_name ? inc.title : '';
    el.innerHTML = `
      <div class="inc-sev-dot ${s.dot}"></div>
      <div class="inc-body">
        <div class="inc-title">${_escHtml(displayName)}</div>
        <div class="inc-meta">${time}${displaySub ? ' · ' + _escHtml(displaySub) : ''}</div>
      </div>
      <div class="inc-right">
        <div class="inc-status ${inc.status}">${statusLabel}</div>
        <button class="inc-status-btn" title="Изменить статус">⋯</button>
      </div>
    `;

    // Click on body → focus device on map
    const body = el.querySelector('.inc-body');
    if (inc.device_id && body) {
      body.style.cursor = 'pointer';
      body.addEventListener('click', () => {
        Store.set('selectedDeviceId', inc.device_id);
        MapWidget.focusDevice(inc.device_id);
      });
    }

    // Click on ⋯ → open status modal
    const statusBtn = el.querySelector('.inc-status-btn');
    if (statusBtn) {
      statusBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        _openStatusModal(inc);
      });
    }

    return el;
  }

  function _prependItem(inc) {
    const el = _buildItem(inc);
    el.classList.add('anim-fade-in');
    feedEl.insertBefore(el, feedEl.firstChild);
  }

  function _updateCount() {
    const open = Store.get('incidents').filter(i => i.status === 'open' || i.status === 'in_progress').length;
    countBadge.textContent = open;
  }

  function _parseDate(s) {
    if (!s) return new Date(NaN);
    s = s.replace(' ', 'T');
    if (!s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) s += 'Z';
    return new Date(s);
  }

  function _fmtTime(date) {
    if (!date || isNaN(date)) return '—';
    const h  = date.getHours().toString().padStart(2, '0');
    const m  = date.getMinutes().toString().padStart(2, '0');
    const d  = date.getDate().toString().padStart(2, '0');
    const mo = (date.getMonth() + 1).toString().padStart(2, '0');
    return `${d}.${mo} ${h}:${m}`;
  }

  function _escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  return { init };
})();
