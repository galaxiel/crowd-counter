# Compteur de manifestation 2.9.0

The interface catches up with field use: direction and restart become
one-click actions, line tracing gets magnetic snapping, and every settings
description was audited against the measurements.

## Added

- **"Sens : …" button in the bottom bar** — flip the counted direction with
  one click; the label states exactly what is counted and the green arrow
  pivots. The setting leaves the settings panel (profiles still carry it).
- **"Recommencer" button** — reruns the analysis from the start without
  reloading the video (it rewinds, resets the counter, keeps the model).
  Offered only after a first run.
- **Magnetic line tracing at 5°** — a line drawn within 5° of horizontal or
  vertical snaps exactly straight (tried at 3°, widened on operator request).

## Fixed

- **On a tilted line, the detection zone now matches the drawing** — the
  detection crop is an axis-aligned rectangle; its corners used to extend
  past the real band and the displayed veil stayed straight. Detections
  outside the oblique band are discarded and the veil follows the tilt. No
  change for a horizontal or vertical line.
- **Settings descriptions audited — 6 of 11 were wrong or stale**, including
  `seuil_confiance` (logic stated backwards), `fenetre_lissage` (described a
  bug fixed long ago) and `resolution_analyse` (contradicted its own
  figures). Every entry now cites the measurement that supports its advice.

## Changed

- **Band thickness**: help rewritten from measurement (5 px counts 37, 30 px
  32, 100 px 24 on the reference segment), 5-step increment, range 5–100.
- Bigger counting line: direction arrow doubled, placement crosses doubled,
  thicker stroke.

**SHA-256**: 0e4ef86edd7a8581eb6fc46b7aac59e818fe3ce60251b82b75c69ea6d00ed9cc
