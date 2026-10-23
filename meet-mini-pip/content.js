// Meet Mini PiP
// Puts ONLY one participant's video into Chrome's native Picture-in-Picture
// window. Native PiP keeps the window locked to the video's own aspect ratio,
// so the person is never cropped and never boxed in, at any window size.
//
// Runs in the page's MAIN world so it can read <video>.srcObject directly.
// Meet enforces Trusted Types, so DOM is built with createElement only.
(() => {
  if (window.__meetMiniPip) return;
  window.__meetMiniPip = true;

  const state = { srcEl: null, stream: null, timer: 0 };

  // Our own video element: it carries the chosen person's stream into PiP.
  const pipVideo = document.createElement('video');
  pipVideo.muted = true; // Meet plays audio separately; this is picture only
  pipVideo.playsInline = true;
  Object.assign(pipVideo.style, {
    position: 'fixed', left: '-10px', top: '-10px', width: '1px', height: '1px', opacity: '0',
  });
  document.body.append(pipVideo);

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
      if (el === pipVideo) continue;
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
    if (pipVideo.srcObject !== state.stream) {
      pipVideo.srcObject = state.stream;
      pipVideo.play().catch(() => {});
    }
  };

  const nextPerson = () => {
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

  // ---------- open / close ----------

  const isOpen = () => document.pictureInPictureElement === pipVideo;

  const open = async () => {
    const first = candidates()[0];
    if (!first) {
      alert('Meet Mini PiP: no participant video found yet.');
      return;
    }
    setSource(first);
    if (pipVideo.readyState < 1) {
      await new Promise((r) => pipVideo.addEventListener('loadedmetadata', r, { once: true }));
    }
    await pipVideo.requestPictureInPicture();
    clearInterval(state.timer);
    state.timer = setInterval(tick, 1000);
    // Shows a "next" button in the PiP window to switch person.
    try {
      navigator.mediaSession.setActionHandler('nexttrack', nextPerson);
    } catch {}
  };

  const toggle = () => {
    if (isOpen()) document.exitPictureInPicture();
    else open().catch((e) => console.warn('[Meet Mini PiP]', e));
  };

  pipVideo.addEventListener('enterpictureinpicture', updateLauncher);
  pipVideo.addEventListener('leavepictureinpicture', () => {
    clearInterval(state.timer);
    try {
      navigator.mediaSession.setActionHandler('nexttrack', null);
    } catch {}
    updateLauncher();
  });

  // ---------- launcher in the Meet page ----------

  const launcher = document.createElement('button');
  launcher.title = 'Meet Mini PiP (Alt+Shift+P) · next person: Alt+Shift+N';
  Object.assign(launcher.style, {
    position: 'fixed', left: '12px', bottom: '88px', zIndex: 2147483647,
    padding: '6px 10px', border: '0', borderRadius: '16px', cursor: 'pointer',
    font: '500 12px system-ui, sans-serif', color: '#fff', background: 'rgba(60,64,67,.85)',
  });
  launcher.addEventListener('click', toggle);
  function updateLauncher() {
    launcher.textContent = isOpen() ? '✕ Close mini PiP' : '◳ Mini PiP';
  }
  updateLauncher();
  document.body.append(launcher);

  // Keyboard press counts as the user gesture PiP requires.
  document.addEventListener('keydown', (e) => {
    if (!e.altKey || !e.shiftKey) return;
    if (e.code === 'KeyP') {
      e.preventDefault();
      toggle();
    } else if (e.code === 'KeyN') {
      e.preventDefault();
      nextPerson();
    }
  });
})();
