// Injected into the Meet page. Opens a small child window that shows ONLY
// one participant's video, letterboxed inside a 16:9 frame (never cropped).
// Meet enforces Trusted Types, so DOM is built with createElement only.
(() => {
  if (window.__meetMiniOpen) return;

  const state = { win: null, video: null, label: null, srcEl: null, stream: null, timer: 0 };

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

  // Keep following the chosen person if Meet swaps streams around.
  const tick = () => {
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
    `;
    doc.head.append(style);

    const video = doc.createElement('video');
    video.autoplay = true;
    video.muted = true; // Meet plays audio itself; this is picture only
    video.playsInline = true;

    const label = doc.createElement('div');
    label.className = 'msg';
    label.textContent = 'No video';

    doc.body.append(video, label);
    state.video = video;
    state.label = label;

    win.addEventListener('pagehide', () => {
      clearInterval(state.timer);
      Object.assign(state, { win: null, video: null, label: null });
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
})();
