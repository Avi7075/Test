# Meet Mini PiP

A tiny Chrome/Edge extension that pops **one** Google Meet participant into an
always-on-top Picture-in-Picture window that holds *only their video*, with
no Meet tiles, names or toolbar. The video is cropped to fill the whole window,
so you can make the window really small and still see them clearly.

Meet's own PiP squeezes the call layout into the window. When the other person
is on a phone (a portrait feed), the shrunk window leaves their tile as a thin
strip. This extension fixes that.

## Install (about 1 minute)

1. Download this `meet-mini-pip` folder.
2. Open `chrome://extensions` (or `edge://extensions`).
3. Turn on **Developer mode** (top right).
4. Click **Load unpacked** and pick the `meet-mini-pip` folder.

Needs Chrome/Edge 116 or newer.

## Use

1. Join the call on meet.google.com.
2. Click the **◳ Mini PiP** button (bottom-left of the Meet page) or press
   **Alt+Shift+P**.
3. Resize the PiP window as small as you like. Its size is remembered.

In the PiP window:

| Action | What it does |
| --- | --- |
| Scroll | Zoom in (crop to their face) |
| Drag | Pan the crop |
| Double-click / `F` / ▣ | Toggle crop-to-fill vs. show whole frame |
| `N` / ⇄ | Switch to the next person (if it picked your self-view) |
| `0` / ↺ | Reset zoom & pan |

The first time, the window opens at the person's own aspect ratio (tall for a
phone), 140px wide.

## Notes

- Keep the Meet tab open and the other person **pinned** in Meet. Meet can stop
  sending video for people whose tile isn't shown.
- The PiP window shows the picture only. Audio still comes from the Meet tab
  as usual.
- Chrome sets a minimum size for PiP windows, so there's a floor you can't go
  below. Because the video fills every pixel, the small size still works.
- If Meet changes its page structure, the auto-pick may choose the wrong feed.
  Press `N` to cycle.
