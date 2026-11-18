# Compteur de manifestation 3.4.0

Ground-truth tooling gains video selection and segment-by-segment annotation,
and the bench can now compare the engine on any video. In the app, the settings
bar is reorganised on two rows and the mouse wheel no longer changes fields
without focus. The counting engine (IoU matching) is unchanged.

## Added

- **Click annotator — video picker and segments** (`tools/annotateur.py`):
  an **Open a video…** button, a **Whole video** checkbox, **start/end** fields,
  and a **Next segment ▶** button (900-frame step by default, the validated
  reference segment length). Starts on the first segment. The output file
  follows the video: the reference keeps `segment_…_operateur.txt` (existing
  annotations stay linked); another video is prefixed with its name.
- **Box annotator — video picker** (`tools/annotateur_boites.py`): same button
  and same "whole video / segment" controls; the training dataset of another
  video goes to `entrainement/<video_name>/` so two videos' frames are never
  mixed.
- **Bench — chosen video** (`tools/verite_terrain.py`): `--video` option on
  `comparer` and `extraire` (default: the reference). The annotator prints the
  `comparer` command with `--video` when it is not the reference.
- **Double-click launchers**: `Ouvrir-annotateur-clic.bat` and
  `Ouvrir-annotateur-boites.bat` (no console), to open the tools like an app.

## Changed

- **Application bar on two rows**: the model badge, the "Thème" selector and
  "À propos" move to a **second row**, together with the "☕ Buy me a coffee"
  button. The first row keeps only the action buttons.

## Fixed

- **Mouse wheel over fields**: the filter only covered the settings panel; the
  "Thème" list in the header still changed on scroll. The wheel is now
  neutralised on **all** fields without focus (panel and header); outside the
  panel it scrolls nothing.

## Notes

- The annotation tools now open even without a reference video (black screen +
  prompt to "Open a video…"): `D:\Bureau\manif_test.mp4` may be absent on the
  machine.
