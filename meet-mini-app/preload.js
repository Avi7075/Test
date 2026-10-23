// Make Meet believe its window is always visible, so it keeps sending her
// video while the big Meet window is minimized or behind other windows.
const { webFrame } = require('electron');

webFrame.executeJavaScript(`
  Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
  Object.defineProperty(document, 'hidden', { get: () => false });
  document.addEventListener('visibilitychange', (e) => e.stopImmediatePropagation(), true);
`);
