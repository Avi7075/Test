// Meet Mini PiP
// Opens a Document Picture-in-Picture window that contains ONLY one
// participant's video, cropped to fill the window, so it stays useful
// even when the window is tiny.
//
// Runs in the page's MAIN world so it can use documentPictureInPicture and
// read <video>.srcObject directly. Meet enforces Trusted Types, so all DOM is
// built with createElement (never innerHTML).
(() => {
  if (window.__meetMiniPip) return;
  window.__meetMiniPip = true;

  const STORE_KEY = 'meetMiniPip.settings';
  const DEFAULTS = { width: 140, height: 0, zoom: 1, panX: 0, panY: 0, fit: 'cover' };

  const loadSettings = () => {
    try {
      return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(STORE_KEY) || '{}') };
    } catch {
      return { ...DEFAULTS };
    }
  };
  const saveSettings = () => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(settings));
    } catch {}
  };

  const settings = loadSettings();
  const state = { win: null, video: null, label: null, srcEl: null, stream: null, timer: 0 };

  // ---------- finding participant videos ----------

  // Meet mirrors your own self-view horizontally; use that to rank it last.
  const isMirrored = (el) => {
    for (let n = el, i = 0; n && i < 4; n = n.parentElement, i++) {
      const t = getComputedStyle(n).transform;
      if (t && t.startsWith('matrix(') && parseFloat(t.slice(7)) < 0) return true;
    }
    return false;
  };

  const isLive = (stream) => {
    const track = stream && stream.getVideoTracks()[0];
    return !!track && track.readyState === 'live';
  };

  // One entry per distinct stream: remote people first, then by on-page size.
  const candidates = () => {
    const byStream = new Map();
    for (const el of document.querySelectorAll('video')) {
      const stream = el.srcObject;
      if (!(stream instanceof MediaStream) || !isLive(stream) || !el.videoWidth) continue;
      const r = el.getBoundingClientRect();
      const entry = { el, stream, area: r.width * r.height, self: isMirrored(el) };
      const prev = byStream.get(stream.id);
      if (!prev || entry.area > prev.area) byStream.set(stream.id, entry);
    }
    return [...byStream.values()].sort((a, b) => a.self - b.self || b.area - a.area);
  };

  // ---------- PiP rendering ----------

  const applyView = () => {
    const v = state.video;
    if (!v) return;
    v.style.objectFit = settings.fit;
    v.style.transform = `translate(${settings.panX}%, ${settings.panY}%) scale(${settings.zoom})`;
  };

  const setSource = (entry) => {
    state.srcEl = entry ? entry.el : null;
    state.stream = entry ? entry.stream : null;
    if (!state.video) return;
    state.video.srcObject = state.stream;
    state.video.play().catch(() => {});
    state.label.style.display = state.stream ? 'none' : 'flex';
  };

  const nextPerson = () => {
    const list = candidates();
    if (!list.length) return setSource(null);
    const i = list.findIndex((c) => c.stream === state.stream);
    setSource(list[(i + 1) % list.length]);
  };

  // Keep following the chosen person if Meet swaps streams around.
  const tick = () => {
    if (!state.win) return;
    const el = state.srcEl;
    if (el && el.isConnected && isLive(el.srcObject)) {
      if (el.srcObject !== state.stream) setSource({ el, stream: el.srcObject });
      return;
    }
    if (isLive(state.stream)) return; // element gone but stream still flowing
    setSource(candidates()[0] || null);
  };

  const buildWindow = (win) => {
    const doc = win.document;
    const style = doc.createElement('style');
    style.textContent = `
      html, body { margin: 0; height: 100%; background: #000; overflow: hidden; }
      body { font: 11px system-ui, sans-serif; color: #fff; user-select: none; }
      video { position: absolute; inset: 0; width: 100%; height: 100%;
              transform-origin: center; cursor: grab; }
      .msg { position: absolute; inset: 0; display: flex; align-items: center;
             justify-content: center; text-align: center; padding: 6px; opacity: .8; }
      .bar { position: absolute; top: 2px; right: 2px; display: flex; gap: 2px;
             opacity: 0; transition: opacity .15s; }
      body:hover .bar { opacity: 1; }
      .bar button { border: 0; border-radius: 4px; padding: 1px 5px; font: inherit;
                    color: #fff; background: rgba(0,0,0,.55); cursor: pointer; }
    `;
    doc.head.append(style);

    const video = doc.createElement('video');
    video.autoplay = true;
    video.muted = true; // Meet plays audio separately; this is picture only
    video.playsInline = true;

    const label = doc.createElement('div');
    label.className = 'msg';
    label.textContent = 'Waiting for video…';

    const bar = doc.createElement('div');
    bar.className = 'bar';
    const btn = (text, title, fn) => {
      const b = doc.createElement('button');
      b.textContent = text;
      b.title = title;
      b.addEventListener('click', (e) => {
        e.stopPropagation();
        fn();
      });
      bar.append(b);
    };
    btn('⇄', 'Next person (N)', nextPerson);
    btn('▣', 'Crop / fit (F)', toggleFit);
    btn('↺', 'Reset zoom (0)', resetView);

    doc.body.append(video, label, bar);
    state.video = video;
    state.label = label;

    // Scroll to zoom, drag to pan: crop in on a face from a portrait phone feed.
    doc.addEventListener(
      'wheel',
      (e) => {
        e.preventDefault();
        settings.zoom = Math.min(5, Math.max(1, settings.zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
        applyView();
        saveSettings();
      },
      { passive: false }
    );
    let drag = null;
    video.addEventListener('pointerdown', (e) => {
      drag = { x: e.clientX, y: e.clientY, panX: settings.panX, panY: settings.panY };
      video.setPointerCapture(e.pointerId);
    });
    video.addEventListener('pointermove', (e) => {
      if (!drag) return;
      settings.panX = drag.panX + ((e.clientX - drag.x) / win.innerWidth) * 100;
      settings.panY = drag.panY + ((e.clientY - drag.y) / win.innerHeight) * 100;
      applyView();
    });
    video.addEventListener('pointerup', () => {
      drag = null;
      saveSettings();
    });
    video.addEventListener('dblclick', toggleFit);
    doc.addEventListener('keydown', (e) => {
      const k = e.key.toLowerCase();
      if (k === 'n') nextPerson();
      else if (k === 'f') toggleFit();
      else if (k === '0') resetView();
    });

    win.addEventListener('pagehide', () => {
      settings.width = win.innerWidth;
      settings.height = win.innerHeight;
      saveSettings();
      clearInterval(state.timer);
      Object.assign(state, { win: null, video: null, label: null, srcEl: null, stream: null });
      updateLauncher();
    });

    applyView();
  };

  function toggleFit() {
    settings.fit = settings.fit === 'cover' ? 'contain' : 'cover';
    applyView();
    saveSettings();
  }

  function resetView() {
    Object.assign(settings, { zoom: 1, panX: 0, panY: 0 });
    applyView();
    saveSettings();
  }

  const open = async () => {
    if (!('documentPictureInPicture' in window)) {
      alert('Meet Mini PiP needs Chrome or Edge 116+ (Document Picture-in-Picture).');
      return;
    }
    const first = candidates()[0] || null;
    // First run: match the person's aspect ratio (portrait for a phone).
    let { width, height } = settings;
    if (!height) {
      const ratio = first ? first.el.videoHeight / first.el.videoWidth : 16 / 9;
      height = Math.round(width * ratio);
    }
    const win = await documentPictureInPicture.requestWindow({ width, height });
    state.win = win;
    buildWindow(win);
    setSource(first);
    state.timer = setInterval(tick, 1000);
    updateLauncher();
  };

  const toggle = () => (state.win ? state.win.close() : open().catch((e) => console.warn('[Meet Mini PiP]', e)));

  // ---------- launcher in the Meet page ----------

  const launcher = document.createElement('button');
  launcher.title = 'Meet Mini PiP (Alt+Shift+P)';
  Object.assign(launcher.style, {
    position: 'fixed', left: '12px', bottom: '88px', zIndex: 2147483647,
    padding: '6px 10px', border: '0', borderRadius: '16px', cursor: 'pointer',
    font: '500 12px system-ui, sans-serif', color: '#fff', background: 'rgba(60,64,67,.85)',
  });
  launcher.addEventListener('click', toggle);
  function updateLauncher() {
    launcher.textContent = state.win ? '✕ Close mini PiP' : '◳ Mini PiP';
  }
  updateLauncher();
  document.body.append(launcher);

  // Keyboard press counts as the user gesture PiP requires.
  document.addEventListener('keydown', (e) => {
    if (e.altKey && e.shiftKey && e.code === 'KeyP') {
      e.preventDefault();
      toggle();
    }
  });
})();
