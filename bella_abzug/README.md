# Bella Abzug – 3D face reconstruction

`bella_abzug.glb` – single-file glTF 2.0 (validated: 0 errors, 0 warnings), < 2 MB, unlit photo-textured materials.

Pipeline (`src/`, run in order):
1. `lm.py` – MediaPipe face landmarks (478 pts) from the reference photo.
2. `seg.py` – MediaPipe multiclass segmentation (hair / face / body skin / clothes / hat).
3. `fit_brim.py` – hat mask + ellipse fit of the brim outline.
4. `build2.py` – geometry in the photo's camera frame: head fitted to the landmarks (face mesh extended
   with a curled skirt and blended into a smooth head shape with a smooth max), hair volume, one seamless
   head–neck–bust surface with a smoothed jaw/neck band, hat (brim/crown) fitted to the brim outline.
5. `bake3.py` – texture baking: photo projection with z-buffer visibility; the photo's own hair/skin
   segmentation decides what fills each area; mirror fill for the far side of the face; synthetic
   straight hair strands where the photo is seen edge-on; seamless polka-dot fabric for hidden areas.
6. `glb2.py` – GLB writer (`KHR_materials_unlit`).

`compare_front.png` – photo (left) vs. model front view (right). `preview.png` – six angles.
`preview_sides.png` – profile and three-quarter close-ups. `before_after.png` – side views of the
previous version (top) vs. this one (bottom).

All scripts run with their built-in defaults; running steps 1–6 reproduces `bella_abzug.glb` byte for byte.
