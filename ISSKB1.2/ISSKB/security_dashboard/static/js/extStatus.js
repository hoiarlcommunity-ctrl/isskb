const ExtStatus = (() => {
  let _modal    = null;
  let _errEl    = null;
  let _pingBtn  = null;
  let _pingLbl  = null;
  let _pingIcon = null;
  let _closeBtn = null;
  let _border   = null;
  let _dismissed = false;  // user closed the modal manually

  function init() {
    _modal    = document.getElementById('ext-server-modal');
    _errEl    = document.getElementById('esm-error-text');
    _pingBtn  = document.getElementById('ext-ping-btn');
    _pingLbl  = document.getElementById('ext-ping-label');
    _pingIcon = document.getElementById('ext-ping-icon');
    _closeBtn = document.getElementById('esm-close-btn');
    _border   = document.getElementById('no-conn-border');

    if (_pingBtn)  _pingBtn.addEventListener('click', _manualPing);
    if (_closeBtn) _closeBtn.addEventListener('click', _dismiss);
  }

  function _dismiss() {
    _dismissed = true;
    if (_modal) _modal.classList.remove('visible');
  }

  function setStatus(ok, error) {
    // — Топбар кнопка —
    if (_pingBtn) {
      _pingBtn.classList.remove('ok', 'fail', 'checking');
      _pingBtn.classList.add(ok ? 'ok' : 'fail');
      if (_pingLbl) _pingLbl.textContent = ok ? 'ДАННЫЕ' : 'НЕТ СВЯЗИ';
      if (_pingIcon) _pingIcon.textContent = ok ? '📡' : '⚠';
    }

    if (ok) {
      // Связь восстановлена — убираем всё
      _dismissed = false;
      if (_modal)  _modal.classList.remove('visible');
      if (_border) _border.classList.remove('active');
    } else {
      // Нет связи — обновляем текст ошибки
      if (_errEl) {
        if (error) {
          _errEl.textContent = error;
          _errEl.classList.add('visible');
        } else {
          _errEl.classList.remove('visible');
        }
      }
      // Пульсирующая рамка всегда при потере связи
      if (_border) _border.classList.add('active');
      // Модалка только если пользователь не закрыл её вручную
      if (_modal && !_dismissed) _modal.classList.add('visible');
    }
  }

  async function _manualPing() {
    if (!_pingBtn) return;
    _pingBtn.classList.remove('ok', 'fail');
    _pingBtn.classList.add('checking');
    if (_pingLbl) _pingLbl.textContent = 'ПРОВЕРКА...';
    if (_pingIcon) _pingIcon.textContent = '🔄';

    try {
      const res = await fetch('/api/external/ping').then(r => r.json());
      setStatus(res.ok, res.error);
    } catch {
      setStatus(false, 'Ошибка запроса к серверу приложения');
    } finally {
      _pingBtn.classList.remove('checking');
    }
  }

  return { init, setStatus };
})();
