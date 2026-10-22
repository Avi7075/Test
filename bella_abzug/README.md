# Bella Abzug – 3D face reconstruction

`bella_abzug.glb` – single-file glTF 2.0 (validated: 0 errors, 0 warnings), < 2 MB, unlit photo-textured materials.

Pipeline (`src/`, run in order):
1. `lm.py` – MediaPipe face landmarks (478 pts) from the reference photo.
2. `seg.py` – MediaPipe multiclass segmentation (hair / face / body skin / clothes / hat).
3. `fit_brim.py` – hat mask + ellipse fit of the brim outline.
4. `build2.py` – geometry in the photo's camera frame: head fitted to the landmarks, hair volume,
   single seamless head–neck–bust surface, hat (brim/crown) fitted to the brim outline.
5. `bake2.py` – texture baking: photo projection with z-buffer visibility and segmentation gating,
   mirror fill for the far side of the face, procedural hair and polka-dot fabric for hidden areas.
6. `glb2.py` – GLB writer (`KHR_materials_unlit`).

`compare_front.png` – photo (left) vs. model front view (right). `preview*.png` – other angles.
