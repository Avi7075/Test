# Meet Mini (Windows app)

Google Meet in its own window, plus a **tiny always-on-top 16:9 window that
shows only her video**. You can shrink it far below Chrome's picture-in-picture
limit (down to 64 × 36 px). Her whole picture always shows, never cropped. If
her phone is upright, it's letterboxed inside the 16:9 frame.

## Install

1. Download `MeetMini-Windows.zip` and unzip it anywhere (e.g. your Desktop).
2. Open the `Meet Mini-win32-x64` folder and double-click **Meet Mini.exe**.
   - If Windows SmartScreen says "Windows protected your PC", click
     **More info → Run anyway** (the app isn't code-signed).

## Use

1. In the Meet Mini window, join the call like normal.
   - If Google says *"This browser or app may not be secure"* when you sign in,
     join without signing in: open the meeting link and enter a name. She
     admits you from her phone.
2. Press **Ctrl+Shift+M** (works from any app) to open the mini window.
   Press it again to close it.
3. In the mini window:

| Do this | To |
| --- | --- |
| Drag anywhere on it | Move it |
| Drag its edges | Resize (stays 16:9) |
| `-` / `+` | Shrink / grow |
| `N` | Switch person (if it picked your own camera) |
| `Esc` | Close it |

Its size and position are remembered.

## Tips

- Sound comes from the main Meet Mini window, so leave it open. Minimizing it
  should be fine. If her video freezes while it's minimized, restore it and
  just put it behind your other windows.
- Pin her in Meet so her video is the main one.

## Building from source

Needs Node.js 18+.

```
npm install
npm start              # run it
npm run package:win    # build dist/Meet Mini-win32-x64
```
