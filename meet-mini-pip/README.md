# Meet Mini PiP

A tiny Chrome/Edge extension that pops **one** Google Meet participant into an
always-on-top Picture-in-Picture window that holds *only their video*, with
no Meet tiles, names or toolbar.

The window is locked to the video's own shape (16:9 for a landscape feed).
Their whole frame always shows, never cropped and with no black bars. Drag
the window as small as you like and it keeps that shape.

Meet's own PiP squeezes the call layout into the window, so the person you
want ends up a tiny tile inside an already small window. This extension fixes
that.

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

To switch to a different person (for example, if it picked your own
self-view), click the **⏭ next** button in the PiP window or press
**Alt+Shift+N** in the Meet tab.

## Notes

- Keep the Meet tab open and the other person **pinned** in Meet. Meet can stop
  sending video for people whose tile isn't shown.
- The PiP window shows the picture only. Audio still comes from the Meet tab
  as usual.
- Chrome sets a minimum size for PiP windows, so there's a floor you can't go
  below.
- The window takes the shape of the video she sends. If her phone is held
  upright, the window is upright too. Turning her phone sideways gives 16:9.
- If Meet changes its page structure, the auto-pick may choose the wrong feed.
  Use ⏭ / Alt+Shift+N to cycle.
