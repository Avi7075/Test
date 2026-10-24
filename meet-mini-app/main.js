const { app, BrowserWindow, globalShortcut, session, screen, desktopCapturer, ipcMain } = require('electron');
const fs = require('fs');
const path = require('path');

const MEET = process.env.MEET_MINI_URL || 'https://meet.google.com/';
// The call the "Join call" button opens. Change it to join a different call.
const CALL_URL = 'https://meet.google.com/rug-eiuh-gtb';
const TOGGLE_KEY = 'Control+Shift+M';
const LANDSCAPE = 16 / 9;
const PORTRAIT = 9 / 16;
const MIN_SIDE = 36;
const SIZE_FILE = path.join(app.getPath('userData'), 'mini-bounds.json');
const MODE_FILE = path.join(app.getPath('userData'), 'mini-mode.json');
// auto: follow the shape of her video; landscape/portrait: always that shape.
const MODES = ['auto', 'landscape', 'portrait'];

let meetWin = null;
let miniWin = null;
let aspect = LANDSCAPE;
let mode = 'auto';
let aspectTimer = 0;

try {
  const saved = JSON.parse(fs.readFileSync(MODE_FILE, 'utf8'));
  if (MODES.includes(saved)) mode = saved;
} catch {}

const loadBounds = () => {
  try {
    return JSON.parse(fs.readFileSync(SIZE_FILE, 'utf8'));
  } catch {
    const { workArea } = screen.getPrimaryDisplay();
    const width = 160;
    const height = Math.round(width / LANDSCAPE);
    return { width, height, x: workArea.x + workArea.width - width - 16, y: workArea.y + 16 };
  }
};

const saveBounds = (bounds) => {
  try {
    fs.writeFileSync(SIZE_FILE, JSON.stringify(bounds));
  } catch {}
};

// Resize the mini window to `area` pixels at the current aspect ratio,
// keeping it pinned to whichever screen corner it sits nearest.
const fitMini = (area) => {
  if (!miniWin) return;
  const b = miniWin.getBounds();
  let width = Math.round(Math.sqrt(area * aspect));
  let height = Math.round(width / aspect);
  const short = Math.min(width, height);
  if (short < MIN_SIDE) {
    width = Math.round((width * MIN_SIDE) / short);
    height = Math.round((height * MIN_SIDE) / short);
  }
  const wa = screen.getDisplayMatching(b).workArea;
  const right = b.x + b.width / 2 > wa.x + wa.width / 2;
  const bottom = b.y + b.height / 2 > wa.y + wa.height / 2;
  miniWin.setAspectRatio(aspect);
  miniWin.setMinimumSize(
    Math.round(aspect >= 1 ? MIN_SIDE * aspect : MIN_SIDE),
    Math.round(aspect >= 1 ? MIN_SIDE : MIN_SIDE / aspect)
  );
  miniWin.setBounds({
    x: right ? b.x + b.width - width : b.x,
    y: bottom ? b.y + b.height - height : b.y,
    width,
    height,
  });
};

const resizeMini = (factor) => {
  if (!miniWin) return;
  const b = miniWin.getBounds();
  fitMini(b.width * b.height * factor * factor);
};

const setAspect = (next) => {
  if (!miniWin || !next || Math.abs(next - aspect) < 0.02) return;
  aspect = next;
  const b = miniWin.getBounds();
  fitMini(b.width * b.height);
};

// In auto mode, ask the page for her video's shape and follow it.
const syncAspect = async () => {
  if (!miniWin || !meetWin) return;
  if (mode === 'landscape') return setAspect(LANDSCAPE);
  if (mode === 'portrait') return setAspect(PORTRAIT);
  try {
    const ratio = await meetWin.webContents.executeJavaScript('window.__meetMiniAspect ? window.__meetMiniAspect() : 0');
    setAspect(ratio);
  } catch {}
};

const cycleMode = () => {
  mode = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
  try {
    fs.writeFileSync(MODE_FILE, JSON.stringify(mode));
  } catch {}
  syncAspect();
};

const runInMeet = (code) => {
  if (meetWin) meetWin.webContents.executeJavaScript(code, true).catch(() => {});
};

// Mic / camera / screen share, pressed from the mini window.
// Mic and camera fall back to Meet's own shortcuts if the button isn't found.
const control = async (what) => {
  if (!meetWin) return;
  const wc = meetWin.webContents;
  const done = await wc
    .executeJavaScript(`window.__meetMiniControl ? window.__meetMiniControl(${JSON.stringify(what)}) : false`, true)
    .catch(() => false);
  const shortcut = { mic: 'D', cam: 'E' }[what];
  if (!done && shortcut) {
    wc.sendInputEvent({ type: 'keyDown', keyCode: shortcut, modifiers: ['control'] });
    wc.sendInputEvent({ type: 'keyUp', keyCode: shortcut, modifiers: ['control'] });
  }
};

// A floating "Join call" button on every page of the main window.
const joinScript = `(() => {
  const url = ${JSON.stringify(CALL_URL)};
  if (location.href.startsWith(url) || document.getElementById('meet-mini-join')) return;
  const b = document.createElement('button');
  b.id = 'meet-mini-join';
  b.textContent = 'Join call';
  b.title = url;
  Object.assign(b.style, {
    position: 'fixed', right: '20px', bottom: '20px', zIndex: 2147483647,
    padding: '12px 22px', border: '0', borderRadius: '24px', cursor: 'pointer',
    font: '600 15px system-ui, sans-serif', color: '#fff', background: '#1a73e8',
    boxShadow: '0 2px 8px rgba(0,0,0,.3)',
  });
  b.addEventListener('click', () => { location.href = url; });
  document.body.append(b);
})()`;

// Screen sharing: Electron has no built-in picker, so show our own.
let pickerResolve = null;

const pickSource = (sources) =>
  new Promise((resolve) => {
    const picker = new BrowserWindow({
      width: 760,
      height: 560,
      parent: meetWin,
      modal: true,
      title: 'Choose what to share',
      autoHideMenuBar: true,
      webPreferences: { preload: path.join(__dirname, 'picker-preload.js') },
    });
    const list = sources.map((s) => ({
      id: s.id,
      name: s.name,
      screen: s.id.startsWith('screen:'),
      thumb: s.thumbnail.toDataURL(),
    }));
    ipcMain.removeHandler('picker:sources');
    ipcMain.handle('picker:sources', () => list);
    pickerResolve = (id) => {
      pickerResolve = null;
      resolve(id);
      if (!picker.isDestroyed()) picker.close();
    };
    picker.on('closed', () => pickerResolve && pickerResolve(null));
    picker.loadFile(path.join(__dirname, 'picker.html'));
  });

ipcMain.on('picker:choose', (_e, id) => pickerResolve && pickerResolve(id));

const createMeetWindow = () => {
  meetWin = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'Meet Mini',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      backgroundThrottling: false,
      partition: 'persist:meet',
    },
  });

  const wc = meetWin.webContents;
  // Look like plain Chrome so Google is less likely to refuse sign-in.
  wc.setUserAgent(wc.getUserAgent().replace(/ Electron\/\S+/, '').replace(/ meet-mini\/\S+/i, ''));

  const miniScript = fs.readFileSync(path.join(__dirname, 'mini.js'), 'utf8');
  wc.on('dom-ready', () => {
    if (wc.getURL().startsWith(MEET)) runInMeet(miniScript);
    runInMeet(joinScript);
  });

  // The page opens the mini window with window.open(); shape it here.
  wc.setWindowOpenHandler(({ frameName, url }) => {
    if (frameName === 'meet-mini' && url === 'about:blank') {
      return {
        action: 'allow',
        overrideBrowserWindowOptions: {
          ...loadBounds(),
          frame: false,
          alwaysOnTop: true,
          skipTaskbar: true,
          maximizable: false,
          fullscreenable: false,
          minWidth: MIN_SIDE,
          minHeight: MIN_SIDE,
          backgroundColor: '#000000',
          title: 'Meet Mini',
        },
      };
    }
    return { action: 'allow' };
  });

  wc.on('did-create-window', (win, { frameName }) => {
    if (frameName !== 'meet-mini') return;
    miniWin = win;
    const b = win.getBounds();
    aspect = b.width / b.height;
    win.setAspectRatio(aspect);
    syncAspect();
    aspectTimer = setInterval(syncAspect, 1000);
    win.setAlwaysOnTop(true, 'screen-saver');
    win.setVisibleOnAllWorkspaces(true);
    win.on('close', () => saveBounds(win.getBounds()));
    win.on('closed', () => {
      clearInterval(aspectTimer);
      if (miniWin === win) miniWin = null;
    });
    // Buttons in the mini window send commands by setting its title.
    win.on('page-title-updated', (event, title) => {
      const m = /^meet-mini:(mic|cam|share):/.exec(title);
      if (!m) return;
      event.preventDefault();
      control(m[1]);
    });
    win.webContents.on('before-input-event', (event, input) => {
      if (input.type !== 'keyDown') return;
      const key = input.key;
      if (key === '+' || key === '=') resizeMini(1.15);
      else if (key === '-' || key === '_') resizeMini(1 / 1.15);
      else if (key === 'n' || key === 'N') runInMeet('window.__meetMiniNext && window.__meetMiniNext()');
      else if (key === 'o' || key === 'O') cycleMode();
      else if (key === 'm' || key === 'M') control('mic');
      else if (key === 'c' || key === 'C') control('cam');
      else if (key === 's' || key === 'S') control('share');
      else if (key === 'Escape') win.close();
      else return;
      event.preventDefault();
    });
  });

  meetWin.on('closed', () => {
    meetWin = null;
  });

  meetWin.loadURL(MEET);
};

app.whenReady().then(() => {
  // Let Meet use the camera and microphone.
  const ses = session.fromPartition('persist:meet');
  const allowed = new Set(['media', 'mediaKeySystem', 'notifications', 'fullscreen', 'clipboard-sanitized-write']);
  ses.setPermissionRequestHandler((_wc, permission, callback) => callback(allowed.has(permission)));
  ses.setPermissionCheckHandler((_wc, permission) => allowed.has(permission));
  ses.setDisplayMediaRequestHandler(async (_request, callback) => {
    try {
      const sources = await desktopCapturer.getSources({
        types: ['screen', 'window'],
        thumbnailSize: { width: 320, height: 180 },
      });
      const id = await pickSource(sources);
      const source = sources.find((s) => s.id === id);
      callback(source ? { video: source } : {});
    } catch {
      callback({});
    }
  });

  createMeetWindow();

  globalShortcut.register(TOGGLE_KEY, () => {
    if (miniWin) miniWin.close();
    else runInMeet('window.__meetMiniOpen && window.__meetMiniOpen()');
  });
});

app.on('will-quit', () => globalShortcut.unregisterAll());
app.on('window-all-closed', () => app.quit());
