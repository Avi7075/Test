# Meet Mini (Windows app)

Google Meet in its own window, plus a **tiny always-on-top 16:9 window that
shows only her video**. You can shrink it far below Chrome's picture-in-picture
limit (down to 64 × 36 px). Her whole picture always shows, never cropped. If
her phone is upright, it's letterboxed inside the 16:9 frame.

## Install

1. Download **MeetMini.exe**. It's a single file, so there's nothing to unzip.
2. Double-click it.
   - If Windows SmartScreen says "Windows protected your PC", click
     **More info → Run anyway** (the app isn't code-signed).
   - The first launch takes a few seconds while it unpacks itself.

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
npm run build:exe      # build dist/MeetMini.exe (portable, single file)
```
