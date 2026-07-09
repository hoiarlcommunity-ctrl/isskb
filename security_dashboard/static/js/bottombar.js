const Bottombar = (() => {
  const tickerEl  = document.getElementById('bb-ticker');
  const timeEl    = document.getElementById('bb-time-upd');
  let tickerItems = [];

  const SEV_CLASS = {
    critical: 'critical', high: 'high', medium: 'info',
    low: 'info', info: 'info',
  };

  function init() {
    tickerItems = [{ text: 'SENTINEL — загрузка данных...', cls: 'info', resolved: false }];
    _renderTicker();

    Store.on('incidents',         () => _rebuild());
    Store.on('incident_new',      inc => { _prependTickerItem(inc); });
    Store.on('incident_resolved', ()  => _rebuild());
    Store.on('lastUpdate', date => {
      if (!date) return;
      const h = date.getHours().toString().padStart(2, '0');
      const m = date.getMinutes().toString().padStart(2, '0');
      const s = date.getSeconds().toString().padStart(2, '0');
      timeEl.textContent = `Обновлено: ${h}:${m}:${s}`;
    });
  }

  function _rebuild() {
    const incidents = Store.get('incidents') || [];

    if (!incidents.length) {
      tickerItems = [{ text: 'Инцидентов нет — система в штатном режиме', cls: 'info', resolved: false }];
      _renderTicker();
      return;
    }

    const recent = [...incidents]
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 15);

    tickerItems = recent.map(i => ({
      text:     `[${_fmtT(i.created_at)}] ${_sevLabel(i.severity)}: ${i.device_name || i.title}`,
      cls:      SEV_CLASS[i.severity] || 'info',
      resolved: i.status === 'closed' || i.status === 'resolved' || i.status === 'false_alarm',
    }));
    _renderTicker();
  }

  // Оставляем для совместимости с событием incident_new
  function _prependTickerItem(inc) {
    const name = inc.device_name || inc.title;
    tickerItems.unshift({
      text: `[${_fmtT(inc.created_at)}] ${_sevLabel(inc.severity)}: ${name}`,
      cls:  SEV_CLASS[inc.severity] || 'info',
      resolved: false,
    });
    if (tickerItems.length > 15) tickerItems.pop();
    _renderTicker();
  }

  function _renderTicker() {
    const makeSpan = item =>
      `<span class="ticker-item ${item.cls}${item.resolved ? ' resolved' : ''}">${item.text}</span>`;
    // Exact duplicate — translateX(-50%) lands precisely at start of second copy
    const half = tickerItems.map(makeSpan).join('');
    tickerEl.innerHTML = half + half;
    // Restart animation so it begins from 0 after content change
    tickerEl.style.animation = 'none';
    void tickerEl.offsetWidth; // reflow
    tickerEl.style.animation = '';
  }

  function _fmtT(isoStr) {
    if (!isoStr) return '--:--';
    let s = isoStr.replace(' ', 'T');
    if (!s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) s += 'Z';
    const d = new Date(s);
    if (isNaN(d)) return '--:--';
    return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
  }

  function _sevLabel(sev) {
    const l = { critical: '🔴 КРИТ.', high: '🟠 ВЫСОК.', medium: '🔵 СРЕДН.', low: '⚫ НИЗКИЙ', info: 'ℹ ИНФО' };
    return l[sev] || sev;
  }

  return { init };
})();
