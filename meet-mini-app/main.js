const { app, BrowserWindow, globalShortcut, session, screen } = require('electron');
const fs = require('fs');
const path = require('path');

const MEET = process.env.MEET_MINI_URL || 'https://meet.google.com/';
const TOGGLE_KEY = 'Control+Shift+M';
const ASPECT = 16 / 9;
const MIN_WIDTH = 64;
const SIZE_FILE = path.join(app.getPath('userData'), 'mini-bounds.json');

let meetWin = null;
let miniWin = null;

const loadBounds = () => {
  try {
    return JSON.parse(fs.readFileSync(SIZE_FILE, 'utf8'));
  } catch {
    const { workArea } = screen.getPrimaryDisplay();
    const width = 160;
    const height = Math.round(width / ASPECT);
    return { width, height, x: workArea.x + workArea.width - width - 16, y: workArea.y + 16 };
  }
};

const saveBounds = (bounds) => {
  try {
    fs.writeFileSync(SIZE_FILE, JSON.stringify(bounds));
  } catch {}
};

// Grow/shrink the mini window around its centre, keeping 16:9.
const resizeMini = (factor) => {
  if (!miniWin) return;
  const b = miniWin.getBounds();
  const width = Math.max(MIN_WIDTH, Math.round(b.width * factor));
  const height = Math.round(width / ASPECT);
  miniWin.setBounds({
    x: Math.round(b.x + (b.width - width) / 2),
    y: Math.round(b.y + (b.height - height) / 2),
    width,
    height,
  });
};

const runInMeet = (code) => {
  if (meetWin) meetWin.webContents.executeJavaScript(code, true).catch(() => {});
};

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
          minWidth: MIN_WIDTH,
          minHeight: Math.round(MIN_WIDTH / ASPECT),
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
    win.setAspectRatio(ASPECT);
    win.setAlwaysOnTop(true, 'screen-saver');
    win.setVisibleOnAllWorkspaces(true);
    win.on('close', () => saveBounds(win.getBounds()));
    win.on('closed', () => {
      if (miniWin === win) miniWin = null;
    });
    win.webContents.on('before-input-event', (event, input) => {
      if (input.type !== 'keyDown') return;
      const key = input.key;
      if (key === '+' || key === '=') resizeMini(1.15);
      else if (key === '-' || key === '_') resizeMini(1 / 1.15);
      else if (key === 'n' || key === 'N') runInMeet('window.__meetMiniNext && window.__meetMiniNext()');
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

  createMeetWindow();

  globalShortcut.register(TOGGLE_KEY, () => {
    if (miniWin) miniWin.close();
    else runInMeet('window.__meetMiniOpen && window.__meetMiniOpen()');
  });
});

app.on('will-quit', () => globalShortcut.unregisterAll());
app.on('window-all-closed', () => app.quit());
