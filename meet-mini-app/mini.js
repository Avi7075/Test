// Injected into the Meet page. Opens a small child window that shows ONLY
// one participant's video, letterboxed inside a 16:9 frame (never cropped).
// Meet enforces Trusted Types, so DOM is built with createElement only.
(() => {
  if (window.__meetMiniOpen) return;

  const state = { win: null, video: null, label: null, bar: null, srcEl: null, stream: null, timer: 0 };

  // ---------- Meet's own mic / camera / share buttons ----------

  const visible = (el) => el.getClientRects().length > 0;
  // Meet's real mic/camera toggles carry data-is-muted; prefer those.
  const meetButton = (re) => {
    const matches = [...document.querySelectorAll('button[aria-label], [role="button"][aria-label]')].filter(
      (b) => re.test(b.getAttribute('aria-label')) && visible(b)
    );
    return matches.find((b) => b.hasAttribute('data-is-muted')) || matches[0];
  };
  const BUTTONS = {
    mic: /microphone/i,
    cam: /camera/i,
    share: /share screen|present now|stop presenting|you are presenting/i,
  };

  // true = on, false = off, null = can't tell.
  const isOn = (what) => {
    const b = meetButton(BUTTONS[what]);
    if (!b) return null;
    const muted = b.getAttribute('data-is-muted');
    if (muted !== null) return what === 'share' ? muted !== 'true' : muted === 'false';
    const label = b.getAttribute('aria-label');
    if (what === 'share') return /stop|you are presenting/i.test(label);
    return /turn off/i.test(label);
  };

  window.__meetMiniControl = (what) => {
    const b = meetButton(BUTTONS[what]);
    if (!b) return false;
    b.click();
    return true;
  };

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

  const setSource = (entry) => {
    state.srcEl = entry ? entry.el : null;
    state.stream = entry ? entry.stream : null;
    if (!state.video) return;
    if (state.video.srcObject !== state.stream) {
      state.video.srcObject = state.stream;
      state.video.play().catch(() => {});
    }
    state.label.style.display = state.stream ? 'none' : 'flex';
  };

  const next = () => {
    const list = candidates();
    if (!list.length) return;
    const i = list.findIndex((c) => c.stream === state.stream);
    setSource(list[(i + 1) % list.length]);
  };

  const updateBar = () => {
    if (!state.bar) return;
    for (const b of state.bar.children) {
      const on = isOn(b.dataset.what);
      b.classList.toggle('off', on === false && b.dataset.what !== 'share');
      b.classList.toggle('on', on === true);
    }
  };

  // Keep following the chosen person if Meet swaps streams around.
  const tick = () => {
    updateBar();
    const el = state.srcEl;
    if (el && el.isConnected && isLive(el.srcObject)) {
      if (el.srcObject !== state.stream) setSource({ el, stream: el.srcObject });
      return;
    }
    if (isLive(state.stream)) return; // element gone but stream still flowing
    const first = candidates()[0];
    if (first) setSource(first);
  };

  const build = (win) => {
    const doc = win.document;
    doc.title = 'Meet Mini';
    const style = doc.createElement('style');
    style.textContent = `
      html, body { margin: 0; height: 100%; background: #000; overflow: hidden; }
      /* The whole window is a handle: drag anywhere to move it. */
      body { -webkit-app-region: drag; font: 11px system-ui, sans-serif; color: #fff; }
      video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }
      .msg { position: absolute; inset: 0; display: flex; align-items: center;
             justify-content: center; text-align: center; opacity: .7; }
      /* Controls show while the mini window is focused (click it once). */
      .bar { position: absolute; left: 0; right: 0; bottom: 4px; display: none;
             justify-content: center; gap: 4px; -webkit-app-region: no-drag; }
      body.focused .bar { display: flex; }
      .bar button { width: clamp(18px, 22vmin, 32px); height: clamp(18px, 22vmin, 32px);
                    padding: 0; border: 0; border-radius: 50%; cursor: pointer;
                    font-size: clamp(9px, 11vmin, 16px); line-height: 1;
                    color: #fff; background: rgba(60,64,67,.85); }
      .bar button.off { background: #d93025; }
      .bar button.share.on { background: #1a73e8; }
    `;
    doc.head.append(style);

    const video = doc.createElement('video');
    video.autoplay = true;
    video.muted = true; // Meet plays audio itself; this is picture only
    video.playsInline = true;

    const label = doc.createElement('div');
    label.className = 'msg';
    label.textContent = 'No video';

    const bar = doc.createElement('div');
    bar.className = 'bar';
    for (const [what, icon, title] of [
      ['mic', '🎤', 'Microphone (M)'],
      ['cam', '📷', 'Camera (C)'],
      ['share', '🖥', 'Share screen (S)'],
    ]) {
      const b = doc.createElement('button');
      b.dataset.what = what;
      b.className = what;
      b.textContent = icon;
      b.title = title;
      // Ask the app (via the window title) to press it, so it counts as a
      // real click — screen sharing refuses to start otherwise.
      b.addEventListener('click', () => {
        doc.title = `meet-mini:${what}:${Date.now()}`;
        setTimeout(updateBar, 500);
      });
      bar.append(b);
    }

    doc.body.append(video, label, bar);
    state.video = video;
    state.label = label;
    state.bar = bar;
    win.addEventListener('focus', () => doc.body.classList.add('focused'));
    win.addEventListener('blur', () => doc.body.classList.remove('focused'));
    updateBar();

    win.addEventListener('pagehide', () => {
      clearInterval(state.timer);
      Object.assign(state, { win: null, video: null, label: null, bar: null });
    });
  };

  window.__meetMiniOpen = () => {
    if (state.win && !state.win.closed) return;
    const win = window.open('about:blank', 'meet-mini');
    if (!win) return;
    state.win = win;
    build(win);
    setSource(candidates()[0] || null);
    clearInterval(state.timer);
    state.timer = setInterval(tick, 1000);
  };

  window.__meetMiniNext = next;

  // Shape of the video being shown (width / height), or 0 if none yet.
  window.__meetMiniAspect = () => {
    const v = state.video;
    return v && v.videoWidth && v.videoHeight ? v.videoWidth / v.videoHeight : 0;
  };
})();
