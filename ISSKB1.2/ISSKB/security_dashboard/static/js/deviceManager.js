/**
 * deviceManager.js — Оверлей управления устройствами, категориями и зонами.
 * Используется только пользователями с ролью admin.
 */
const DeviceManager = (() => {

  // ── State ─────────────────────────────────────────────────────────────────
  let _tab        = 'devices';
  let _devices    = [];
  let _categories = [];
  let _zones      = [];
  let _editId     = null;
  let _editType   = null; // 'device'|'category'|'zone'

  // ── Open / Close ──────────────────────────────────────────────────────────
  function open() {
    const ov = document.getElementById('dm-overlay');
    ov.classList.add('visible');
    _switchTab(_tab);
  }

  function close() {
    document.getElementById('dm-overlay').classList.remove('visible');
    _closeForm();
  }

  // ── Tab switching ─────────────────────────────────────────────────────────
  function _switchTab(name) {
    _tab = name;
    document.querySelectorAll('.dm-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === name)
    );
    document.querySelectorAll('.dm-section').forEach(s =>
      s.classList.toggle('active', s.id === `dm-${name}`)
    );
    _closeForm();
    if (name === 'devices')    _loadDevices();
    if (name === 'categories') _loadCategories();
    if (name === 'zones')      _loadZones();
  }

  // ── Utility ───────────────────────────────────────────────────────────────
  function _esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : ''; }
  function _q(id)  { return document.getElementById(id); }

  function _toast(msg, type = 'info') {
    if (typeof Toast !== 'undefined') {
      Toast.show({ icon: type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ', title: '', msg, type, duration: 3500 });
    }
  }

  async function _api(url, opts = {}) {
    const r = await fetch(url, { credentials: 'same-origin', ...opts });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
    return d;
  }

  // ── Form pane ─────────────────────────────────────────────────────────────
  function _closeForm() {
    _editId   = null;
    _editType = null;
    const pane = _q('dm-form-pane');
    if (pane) pane.classList.add('hidden');
  }

  function _showForm(title, html, onSave) {
    const pane = _q('dm-form-pane');
    _q('dm-form-title').textContent = title;
    _q('dm-form-body').innerHTML = html;
    pane.classList.remove('hidden');
    // Footer buttons
    _q('dm-form-save').onclick  = onSave;
    _q('dm-form-cancel').onclick = _closeForm;
  }

  // ── DEVICES ───────────────────────────────────────────────────────────────

  async function _loadDevices() {
    try {
      _devices    = await _api('/api/devices');
      _categories = await _api('/api/categories');
      _zones      = await _api('/api/zones');
      // Populate category filter
      const sel = _q('dm-dev-cat-filter');
      if (sel) {
        sel.innerHTML = '<option value="">Все категории</option>' +
          _categories.map(c => `<option value="${c.id}">${_esc(c.name)}</option>`).join('');
      }
      _renderDevices();
    } catch (e) { _toast('Ошибка загрузки устройств: ' + e.message, 'error'); }
  }

  function _renderDevices() {
    const q   = (_q('dm-dev-search')?.value || '').toLowerCase();
    const cid = _q('dm-dev-cat-filter')?.value || '';
    const catMap = Object.fromEntries(_categories.map(c => [c.id, c]));
    const zoneMap = Object.fromEntries(_zones.map(z => [z.id, z]));

    const filtered = _devices.filter(d => {
      const matchQ = !q || d.name.toLowerCase().includes(q) || (d.serial_number || '').toLowerCase().includes(q);
      const matchC = !cid || String(d.category_id) === cid;
      return matchQ && matchC;
    });

    const tbody = _q('dm-dev-tbody');
    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding:32px;text-align:center;color:var(--txt-muted)">Устройства не найдены</td></tr>`;
      return;
    }
    tbody.innerHTML = filtered.map(d => {
      const cat  = catMap[d.category_id];
      const zone = d.zone_id ? zoneMap[d.zone_id] : null;
      const icon = d.icon_path
        ? `<img src="${d.icon_path}" class="dm-icon-thumb" alt="" />`
        : `<span>${cat?.icon || '📦'}</span>`;
      return `
        <tr data-id="${d.id}">
          <td class="td-id">${d.id}</td>
          <td class="td-icon">${icon}</td>
          <td>
            <div style="font-weight:600">${_esc(d.name)}</div>
            <div style="font-size:10px;color:var(--txt-muted)">${_esc(d.serial_number) || ''}</div>
          </td>
          <td style="font-size:11px">${_esc(cat?.name) || '—'}${d.is_mobile ? ' <span class="mobile-tag">MOBILE</span>' : ''}</td>
          <td style="font-size:11px;color:var(--txt-muted)">${zone ? _esc(zone.name) : '—'}</td>
          <td class="td-act">
            <button class="btn btn-ghost btn-sm btn-icon" data-action="edit" title="Редактировать">✏</button>
            <button class="btn btn-danger btn-sm btn-icon" data-action="del" title="Удалить">🗑</button>
          </td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.closest('tr').dataset.id);
        const d  = _devices.find(x => x.id === id);
        if (!d) return;
        btn.dataset.action === 'edit' ? _openDeviceForm(d) : _confirmDelete('device', id, d.name);
      });
    });
  }

  function _buildCatOptions(selected) {
    return _categories.map(c =>
      `<option value="${c.id}" ${c.id == selected ? 'selected' : ''}>${_esc(c.name)}</option>`
    ).join('');
  }

  function _buildZoneOptions(selected) {
    return `<option value="">— Без зоны —</option>` +
      _zones.map(z =>
        `<option value="${z.id}" ${z.id == selected ? 'selected' : ''}>${_esc(z.name)}</option>`
      ).join('');
  }

  function _buildRangesHtml(ranges) {
    const rows = (ranges || []).map((r, i) => `
      <div class="range-row" data-ri="${i}">
        <input type="text"   class="rr-label"   value="${_esc(r.label || 'Зона')}" placeholder="Название" />
        <input type="number" class="rr-radius"  value="${r.radius_m || 500}" placeholder="м" />
        <input type="color"  class="rr-color"   value="${r.color || '#3b82f6'}" />
        <button class="range-del" title="Удалить">✕</button>
      </div>`).join('');
    return `
      <div class="ranges-builder" id="ranges-builder">
        ${rows}
        <button class="ranges-add-btn" id="ranges-add">+ Добавить зону</button>
      </div>`;
  }

  function _collectRanges() {
    const rows = document.querySelectorAll('#ranges-builder .range-row');
    return Array.from(rows).map(row => ({
      label:    row.querySelector('.rr-label').value.trim() || 'Зона',
      radius_m: parseInt(row.querySelector('.rr-radius').value) || 500,
      color:    row.querySelector('.rr-color').value,
      opacity:  0.2,
    }));
  }

  function _openDeviceForm(d) {
    _editId   = d?.id || null;
    _editType = 'device';

    const html = `
      <div class="form-group">
        <label class="form-label required">Название</label>
        <input class="form-control" id="df-name" value="${_esc(d?.name)}" placeholder="Имя устройства" />
      </div>
      <div class="form-group">
        <label class="form-label required">Категория</label>
        <select class="form-control" id="df-cat">${_buildCatOptions(d?.category_id)}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Зона</label>
        <select class="form-control" id="df-zone">${_buildZoneOptions(d?.zone_id)}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Серийный номер</label>
        <input class="form-control" id="df-serial" value="${_esc(d?.serial_number)}" placeholder="SN-XXXXX" />
      </div>
      <div class="form-group">
        <label class="form-label">Модель</label>
        <input class="form-control" id="df-model" value="${_esc(d?.model)}" placeholder="Модель" />
      </div>
      <div class="form-group">
        <label class="form-label">IP-адрес</label>
        <input class="form-control" id="df-ip" value="${_esc(d?.ip_address)}" placeholder="192.168.1.1" />
      </div>
      <div class="form-group">
        <label class="form-label">Прошивка</label>
        <input class="form-control" id="df-fw" value="${_esc(d?.firmware_version)}" placeholder="v1.0.0" />
      </div>
      <div class="form-group">
        <label class="form-label">Ответственный</label>
        <input class="form-control" id="df-responsible" value="${_esc(d?.responsible_person)}" placeholder="Фамилия И.О." />
      </div>
      <div class="form-group">
        <label class="form-label">Дата установки</label>
        <input class="form-control" type="date" id="df-date" value="${d?.installation_date?.split('T')[0] || ''}" />
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin:4px 0">
        <input type="checkbox" id="df-mobile" ${d?.is_mobile ? 'checked' : ''} style="accent-color:var(--accent-br)" />
        <label for="df-mobile" style="font-size:12px;color:var(--txt-secondary);cursor:pointer">Мобильное устройство</label>
      </div>
      <div class="form-group">
        <label class="form-label">Место установки</label>
        <input class="form-control" id="df-location" value="${_esc(d?.location)}" placeholder="Корпус 3, комната 214" />
      </div>
      <div class="form-group">
        <label class="form-label">Широта / Долгота (ручная)</label>
        <div style="display:flex;gap:8px">
          <input class="form-control" type="number" step="0.000001" id="df-lat" value="${d?.latitude || ''}" placeholder="55.7512" />
          <input class="form-control" type="number" step="0.000001" id="df-lon" value="${d?.longitude || ''}" placeholder="37.6184" />
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Описание / Назначение</label>
        <textarea class="form-control" id="df-desc" rows="2">${_esc(d?.description)}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Примечания оператора</label>
        <textarea class="form-control" id="df-notes" rows="2">${_esc(d?.notes)}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Зоны обнаружения / подавления</label>
        ${_buildRangesHtml(d?.detection_ranges)}
      </div>
      ${d ? `
      <div class="form-group">
        <label class="form-label">Иконка устройства</label>
        <div class="icon-upload-row">
          <div class="icon-preview" id="df-icon-preview">
            ${d.icon_path ? `<img src="${d.icon_path}" />` : (_categories.find(c=>c.id===d.category_id)?.icon || '📦')}
          </div>
          <div class="icon-upload-info">
            <label class="btn btn-secondary btn-sm" style="cursor:pointer">
              Загрузить иконку
              <input type="file" id="df-icon-file" accept=".png,.jpg,.jpeg,.svg,.webp" style="display:none" />
            </label>
            <div class="icon-upload-hint">PNG, JPG, SVG, WEBP</div>
          </div>
        </div>
      </div>` : ''}
      <div id="df-error" style="font-size:11px;color:var(--s-critical);display:none;margin-top:4px"></div>
    `;

    _showForm(_editId ? `Редактировать устройство #${_editId}` : 'Новое устройство', html, _saveDevice);

    // Ranges events
    _q('ranges-builder').addEventListener('click', e => {
      if (e.target.classList.contains('range-del')) e.target.closest('.range-row').remove();
    });
    _q('ranges-add').addEventListener('click', () => {
      const row = document.createElement('div');
      row.className = 'range-row';
      row.innerHTML = `
        <input type="text"   class="rr-label"  value="Зона" placeholder="Название" />
        <input type="number" class="rr-radius" value="500"  placeholder="м" />
        <input type="color"  class="rr-color"  value="#3b82f6" />
        <button class="range-del" title="Удалить">✕</button>`;
      _q('ranges-add').before(row);
    });

    // Icon upload
    if (d) {
      const fi = _q('df-icon-file');
      fi?.addEventListener('change', async () => {
        if (!fi.files[0]) return;
        const fd = new FormData();
        fd.append('file', fi.files[0]);
        try {
          const r = await fetch(`/api/admin/devices/${_editId}/icon`, {
            method: 'POST', body: fd, credentials: 'same-origin',
          });
          const dd = await r.json();
          if (dd.icon_path) {
            _q('df-icon-preview').innerHTML = `<img src="${dd.icon_path}?t=${Date.now()}" />`;
            _toast('Иконка загружена', 'success');
          }
        } catch { _toast('Ошибка загрузки иконки', 'error'); }
        fi.value = '';
      });
    }
  }

  async function _saveDevice() {
    const errEl = _q('df-error');
    errEl.style.display = 'none';
    const name = (_q('df-name')?.value || '').trim();
    if (!name) { errEl.textContent = 'Введите название'; errEl.style.display=''; return; }

    const body = {
      name,
      category_id:        parseInt(_q('df-cat').value),
      zone_id:            _q('df-zone').value ? parseInt(_q('df-zone').value) : null,
      serial_number:      _q('df-serial').value.trim() || null,
      model:              _q('df-model').value.trim() || null,
      ip_address:         _q('df-ip').value.trim() || null,
      firmware_version:   _q('df-fw').value.trim() || null,
      responsible_person: _q('df-responsible').value.trim() || null,
      installation_date:  _q('df-date').value || null,
      is_mobile:          _q('df-mobile').checked,
      description:        _q('df-desc').value.trim() || null,
      notes:              _q('df-notes')?.value.trim() || null,
      location:           _q('df-location')?.value.trim() || null,
      latitude:           _q('df-lat')?.value ? parseFloat(_q('df-lat').value) : null,
      longitude:          _q('df-lon')?.value ? parseFloat(_q('df-lon').value) : null,
      detection_ranges:   _collectRanges(),
    };

    const btn = _q('dm-form-save');
    btn.disabled = true; btn.textContent = 'Сохраняем...';
    try {
      if (_editId) {
        await _api(`/api/admin/devices/${_editId}`, {
          method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        });
      } else {
        await _api('/api/admin/devices', {
          method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        });
      }
      _toast(_editId ? 'Устройство обновлено' : 'Устройство создано', 'success');
      _closeForm();
      await _loadDevices();
      // Trigger full data refresh in main app
      if (typeof API !== 'undefined') {
        API.getDevices().then(d => Store.set('devices', d)).catch(() => {});
      }
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = '';
    } finally {
      btn.disabled = false; btn.textContent = 'Сохранить';
    }
  }

  // ── CATEGORIES ────────────────────────────────────────────────────────────

  async function _loadCategories() {
    try {
      _categories = await _api('/api/categories');
      _renderCategories();
    } catch (e) { _toast('Ошибка: ' + e.message, 'error'); }
  }

  function _renderCategories() {
    const q = (_q('dm-cat-search')?.value || '').toLowerCase();
    const filtered = _categories.filter(c =>
      !q || c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q)
    );
    const tbody = _q('dm-cat-tbody');
    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding:32px;text-align:center;color:var(--txt-muted)">Категории не найдены</td></tr>`;
      return;
    }
    tbody.innerHTML = filtered.map(c => `
      <tr data-id="${c.id}">
        <td class="td-id">${c.id}</td>
        <td class="td-icon">
          ${c.icon_path ? `<img src="${c.icon_path}" class="dm-icon-thumb" />` : `<span style="font-size:20px">${c.icon || '📦'}</span>`}
        </td>
        <td><strong>${_esc(c.name)}</strong><div style="font-size:10px;color:var(--txt-muted)">${_esc(c.code)}</div></td>
        <td><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:${_esc(c.color)};vertical-align:middle;margin-right:6px"></span>${_esc(c.color)}</td>
        <td style="font-size:11px;color:var(--txt-muted)">${c.tab_id ? `Вкладка ${c.tab_id}` : '<span style="color:var(--s-warning)">Не привязана</span>'}</td>
        <td class="td-act">
          <button class="btn btn-ghost btn-sm btn-icon" data-action="edit" title="Редактировать">✏</button>
          <button class="btn btn-danger btn-sm btn-icon" data-action="del" title="Удалить">🗑</button>
        </td>
      </tr>`).join('');

    tbody.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.closest('tr').dataset.id);
        const c  = _categories.find(x => x.id === id);
        if (!c) return;
        btn.dataset.action === 'edit' ? _openCategoryForm(c) : _confirmDelete('category', id, c.name);
      });
    });
  }

  function _openCategoryForm(c) {
    _editId   = c?.id || null;
    _editType = 'category';
    const html = `
      <div class="form-group">
        <label class="form-label required">Код (уникальный)</label>
        <input class="form-control" id="cf-code" value="${_esc(c?.code)}" placeholder="cat_xxx" ${c ? 'disabled' : ''} />
      </div>
      <div class="form-group">
        <label class="form-label required">Название</label>
        <input class="form-control" id="cf-name" value="${_esc(c?.name)}" placeholder="Название категории" />
      </div>
      <div class="form-group">
        <label class="form-label">Иконка (эмодзи)</label>
        <input class="form-control" id="cf-icon" value="${_esc(c?.icon)}" placeholder="📦" maxlength="4" style="font-size:18px" />
      </div>
      <div class="form-group">
        <label class="form-label">Цвет маркера</label>
        <div class="color-row">
          <input type="color" id="cf-color-picker" value="${c?.color || '#3b82f6'}" />
          <input class="form-control" id="cf-color" value="${c?.color || '#3b82f6'}" placeholder="#3b82f6" />
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Вкладка подсистемы (tab_id 1–9)</label>
        <input class="form-control" type="number" id="cf-tab" value="${c?.tab_id || ''}" placeholder="5" min="1" max="9" />
      </div>
      ${c ? `
      <div class="form-group">
        <label class="form-label">Иконка-изображение</label>
        <div class="icon-upload-row">
          <div class="icon-preview">
            ${c.icon_path ? `<img src="${c.icon_path}" />` : (c.icon || '📦')}
          </div>
          <div class="icon-upload-info">
            <label class="btn btn-secondary btn-sm" style="cursor:pointer">
              Загрузить
              <input type="file" id="cf-icon-file" accept=".png,.jpg,.jpeg,.svg,.webp" style="display:none" />
            </label>
            <div class="icon-upload-hint">PNG, JPG, SVG, WEBP</div>
          </div>
        </div>
      </div>` : ''}
      <div id="cf-error" style="font-size:11px;color:var(--s-critical);display:none;margin-top:4px"></div>
    `;
    _showForm(_editId ? `Редактировать категорию #${_editId}` : 'Новая категория', html, _saveCategory);

    // Sync color picker ↔ text
    const picker = _q('cf-color-picker');
    const text   = _q('cf-color');
    picker?.addEventListener('input', () => { text.value = picker.value; });
    text?.addEventListener('input',   () => { if (/^#[0-9a-f]{6}$/i.test(text.value)) picker.value = text.value; });

    // Icon upload
    const fi = _q('cf-icon-file');
    fi?.addEventListener('change', async () => {
      if (!fi.files[0] || !_editId) return;
      const fd = new FormData();
      fd.append('file', fi.files[0]);
      try {
        const r = await fetch(`/api/admin/categories/${_editId}/icon`, {
          method: 'POST', body: fd, credentials: 'same-origin',
        });
        const dd = await r.json();
        if (dd.icon_path) _toast('Иконка категории загружена', 'success');
      } catch { _toast('Ошибка загрузки иконки', 'error'); }
      fi.value = '';
    });
  }

  async function _saveCategory() {
    const errEl = _q('cf-error');
    errEl.style.display = 'none';
    const name  = (_q('cf-name')?.value || '').trim();
    const code  = (_q('cf-code')?.value || '').trim();
    const tabRaw = _q('cf-tab')?.value;

    if (!name) { errEl.textContent = 'Введите название'; errEl.style.display=''; return; }
    if (!_editId && !code) { errEl.textContent = 'Введите код'; errEl.style.display=''; return; }

    const body = {
      name,
      icon:   _q('cf-icon').value.trim() || '📦',
      color:  _q('cf-color').value.trim() || '#3b82f6',
      tab_id: tabRaw ? parseInt(tabRaw) : null,
    };
    if (!_editId) body.code = code;

    const btn = _q('dm-form-save');
    btn.disabled = true; btn.textContent = 'Сохраняем...';
    try {
      if (_editId) {
        await _api(`/api/admin/categories/${_editId}`, {
          method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        });
      } else {
        await _api('/api/admin/categories', {
          method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        });
      }
      _toast(_editId ? 'Категория обновлена' : 'Категория создана', 'success');
      _closeForm();
      await _loadCategories();
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = '';
    } finally {
      btn.disabled = false; btn.textContent = 'Сохранить';
    }
  }

  // ── ZONES ─────────────────────────────────────────────────────────────────

  async function _loadZones() {
    try {
      _zones = await _api('/api/zones');
      _renderZones();
    } catch (e) { _toast('Ошибка: ' + e.message, 'error'); }
  }

  function _renderZones() {
    const q = (_q('dm-zone-search')?.value || '').toLowerCase();
    const filtered = _zones.filter(z =>
      !q || z.name.toLowerCase().includes(q) || (z.code || '').toLowerCase().includes(q)
    );
    const tbody = _q('dm-zone-tbody');
    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding:32px;text-align:center;color:var(--txt-muted)">Зоны не найдены</td></tr>`;
      return;
    }
    tbody.innerHTML = filtered.map(z => `
      <tr data-id="${z.id}">
        <td class="td-id">${z.id}</td>
        <td><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:${_esc(z.color)};margin-right:6px;vertical-align:middle"></span><strong>${_esc(z.name)}</strong></td>
        <td style="font-size:11px;color:var(--txt-muted)">${_esc(z.code)}</td>
        <td style="font-size:11px">${z.lat_center ? `${z.lat_center}, ${z.lon_center}` : '—'}</td>
        <td style="font-size:11px">${z.radius_m ? z.radius_m + ' м' : '—'}</td>
        <td class="td-act">
          <button class="btn btn-ghost btn-sm btn-icon" data-action="edit" title="Редактировать">✏</button>
          <button class="btn btn-danger btn-sm btn-icon" data-action="del" title="Удалить">🗑</button>
        </td>
      </tr>`).join('');

    tbody.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const id = parseInt(btn.closest('tr').dataset.id);
        const z  = _zones.find(x => x.id === id);
        if (!z) return;
        btn.dataset.action === 'edit' ? _openZoneForm(z) : _confirmDelete('zone', id, z.name);
      });
    });
  }

  function _openZoneForm(z) {
    _editId   = z?.id || null;
    _editType = 'zone';
    const html = `
      <div class="form-group">
        <label class="form-label required">Название</label>
        <input class="form-control" id="zf-name" value="${_esc(z?.name)}" placeholder="Название зоны" />
      </div>
      <div class="form-group">
        <label class="form-label required">Код</label>
        <input class="form-control" id="zf-code" value="${_esc(z?.code)}" placeholder="zone_xxx" ${z ? 'disabled' : ''} />
      </div>
      <div class="form-group">
        <label class="form-label">Цвет</label>
        <div class="color-row">
          <input type="color" id="zf-color-picker" value="${z?.color || '#3b82f6'}" />
          <input class="form-control" id="zf-color" value="${z?.color || '#3b82f6'}" placeholder="#3b82f6" />
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Широта центра</label>
        <input class="form-control" type="number" step="0.000001" id="zf-lat" value="${z?.lat_center || ''}" placeholder="55.751244" />
      </div>
      <div class="form-group">
        <label class="form-label">Долгота центра</label>
        <input class="form-control" type="number" step="0.000001" id="zf-lon" value="${z?.lon_center || ''}" placeholder="37.618423" />
      </div>
      <div class="form-group">
        <label class="form-label">Радиус (м)</label>
        <input class="form-control" type="number" id="zf-radius" value="${z?.radius_m || 200}" placeholder="200" min="1" />
      </div>
      <div class="form-group">
        <label class="form-label">Описание</label>
        <textarea class="form-control" id="zf-desc" rows="2">${_esc(z?.description)}</textarea>
      </div>
      <div id="zf-error" style="font-size:11px;color:var(--s-critical);display:none;margin-top:4px"></div>
    `;
    _showForm(_editId ? `Редактировать зону #${_editId}` : 'Новая зона', html, _saveZone);

    const picker = _q('zf-color-picker');
    const text   = _q('zf-color');
    picker?.addEventListener('input', () => { text.value = picker.value; });
    text?.addEventListener('input',   () => { if (/^#[0-9a-f]{6}$/i.test(text.value)) picker.value = text.value; });
  }

  async function _saveZone() {
    const errEl = _q('zf-error');
    errEl.style.display = 'none';
    const name = (_q('zf-name')?.value || '').trim();
    const code = (_q('zf-code')?.value || '').trim();
    if (!name) { errEl.textContent = 'Введите название'; errEl.style.display=''; return; }
    if (!_editId && !code) { errEl.textContent = 'Введите код'; errEl.style.display=''; return; }

    const body = {
      name,
      color:       _q('zf-color').value.trim() || '#3b82f6',
      lat_center:  _q('zf-lat').value  ? parseFloat(_q('zf-lat').value)    : null,
      lon_center:  _q('zf-lon').value  ? parseFloat(_q('zf-lon').value)    : null,
      radius_m:    _q('zf-radius').value ? parseInt(_q('zf-radius').value) : 200,
      description: _q('zf-desc').value.trim() || null,
    };
    if (!_editId) body.code = code;

    const btn = _q('dm-form-save');
    btn.disabled = true; btn.textContent = 'Сохраняем...';
    try {
      if (_editId) {
        await _api(`/api/admin/zones/${_editId}`, {
          method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        });
      } else {
        await _api('/api/admin/zones', {
          method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
        });
      }
      _toast(_editId ? 'Зона обновлена' : 'Зона создана', 'success');
      _closeForm();
      await _loadZones();
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = '';
    } finally {
      btn.disabled = false; btn.textContent = 'Сохранить';
    }
  }

  // ── Delete confirm ────────────────────────────────────────────────────────

  function _confirmDelete(type, id, name) {
    const card = _q('dm-confirm-card');
    _q('dm-confirm-del-name').textContent = name;
    _q('dm-confirm').classList.add('visible');
    _q('dm-confirm-ok').onclick = async () => {
      _q('dm-confirm').classList.remove('visible');
      try {
        const urlMap = { device: 'devices', category: 'categories', zone: 'zones' };
        await _api(`/api/admin/${urlMap[type]}/${id}`, { method: 'DELETE' });
        _toast('Удалено', 'success');
        if (type === 'device')    { _closeForm(); await _loadDevices(); }
        if (type === 'category')  { _closeForm(); await _loadCategories(); }
        if (type === 'zone')      { _closeForm(); await _loadZones(); }
        if (type === 'device' && typeof API !== 'undefined') {
          API.getDevices().then(d => Store.set('devices', d)).catch(() => {});
        }
      } catch (e) { _toast(e.message, 'error'); }
    };
    _q('dm-confirm-cancel').onclick = () => _q('dm-confirm').classList.remove('visible');
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  function init() {
    // Tab buttons
    document.querySelectorAll('.dm-tab[data-tab]').forEach(btn => {
      btn.addEventListener('click', () => _switchTab(btn.dataset.tab));
    });

    // Close panel
    _q('dm-close')?.addEventListener('click', close);
    _q('dm-form-close-btn')?.addEventListener('click', _closeForm);

    // Open btn from topbar
    _q('topbar-mgr-btn')?.addEventListener('click', open);

    // Overlay backdrop click
    _q('dm-overlay')?.addEventListener('click', e => { if (e.target.id === 'dm-overlay') close(); });

    // Section-level search/filter events (delegated)
    document.addEventListener('input', e => {
      if (e.target.id === 'dm-dev-search')     _renderDevices();
      if (e.target.id === 'dm-dev-cat-filter') _renderDevices();
      if (e.target.id === 'dm-cat-search')     _renderCategories();
      if (e.target.id === 'dm-zone-search')    _renderZones();
    });

    // Add buttons (delegated via id)
    document.addEventListener('click', e => {
      if (e.target.id === 'dm-dev-add')  _openDeviceForm(null);
      if (e.target.id === 'dm-cat-add')  _openCategoryForm(null);
      if (e.target.id === 'dm-zone-add') _openZoneForm(null);
    });
  }

  return { init, open, close };
})();
