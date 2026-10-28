/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
(() => {
  const picker = document.querySelector('.platform-picker');
  if (!picker) return;
  const buttons = [...picker.querySelectorAll('[data-platform]')];
  const panels = [...document.querySelectorAll('[data-panel]')];
  const hint = document.getElementById('platform-hint');
  const platform = navigator.platform || '';
  const agent = navigator.userAgent || '';
  const detected = /Android|iPhone|iPad|iPod/i.test(agent) || (/Mac/i.test(platform) && navigator.maxTouchPoints > 1)
    ? 'mobile' : /Win/i.test(platform) ? 'windows' : /Linux/i.test(platform) ? 'linux' : 'macos';
  const hints = {
    macos: 'Выбери процессор своего Mac: Apple Silicon или Intel.',
    windows: 'Выбери архитектуру: x64 для большинства ПК, ARM64 для устройств на ARM.',
    linux: 'Нужны системные зависимости Firefox. Запуск через ./forge.',
    mobile: 'Это отдельные мобильные прототипы, не перенос desktop-интерфейса.',
  };
  function selectPlatform(value) {
    if (!panels.some(panel => panel.dataset.panel === value)) return;
    for (const panel of panels) panel.hidden = panel.dataset.panel !== value;
    for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.platform === value));
    hint.textContent = hints[value];
  }
  for (const button of buttons) button.addEventListener('click', () => selectPlatform(button.dataset.platform));
  picker.hidden = false;
  selectPlatform(detected);
})();
