# Compteur de manifestation 3.3.0

Ground-truth and annotation release: the operator can now place the reference
count by clicking a head as it crosses the line — no frame number to copy by
hand — and a separate tool annotates training boxes. In the app, a new option
reports crossings that were set aside because no departure side was known. The
counting algorithm itself is unchanged (IoU matching untouched).

## Added

- **"Warn about uncounted fast crossings" option** (Settings → Tracker, on by
  default). It announces crossings set aside because the departure side of the
  line was unknown — a lower bound of uncertainty, never added to the total.
  The engine always measures them; the option only decides whether the sentence
  is shown. The caveat travels to the single source (`rapport.indicateurs_fiabilite`):
  recap, copied summary and exported JSON; the raw figure is still exported with
  the option off. Measured on segment 3600–4500, direction −1: 1280 → 36 counted
  + 8 flagged; 640 → 32 + 6.
- **Click annotator** (`tools/annotateur.py`, separate dev tool, not in the app).
  The operator clicks a head at the moment it is ON the green line; the current
  frame is recorded with no number to note by hand. Slow playback
  (0.25×/0.5×/1×), step-by-step, seek, undo/delete, automatic resume of an
  existing session. Line and frame number drawn by the same bricks as the bench.
  Output in the bench format (`verite_terrain/segment_<start>-<end>_operateur.txt`),
  read back by `lire_annotations` then compared against the engine by `comparer`.
  13 TDD tests.
- **Box annotator** (`tools/annotateur_boites.py`, separate from the previous
  tool). TRAINING data, not validation — drag a box on a head at the moment it
  is visible (no line); "Propose" lets the ONNX model place its boxes to confirm
  or correct; YOLO dataset export (`entrainement/`: raw images + normalized
  labels + `data.yaml`); resume of existing labels. 15 TDD tests.

## Documented

- **Ground-truth bench run on 12/11** over segment 3600–4500, partial annotation
  (foreground, to be revised by the operator): 14/15 matched at both 640 and
  1280, same miss (frame 4290). The bench does not settle 32 vs 36 (the gap is in
  the dense, un-annotated crowd); automatic resolution 1280 kept. Operator count
  on 13/11: **45** over the segment (total, no frame numbers); 36 + 8 = 44 at
  1280 vs 32 + 6 = 38 at 640 confirms auto-1280, and the announced caveat is the
  right order of magnitude. Frame-by-frame comparison awaits the frame numbers.

## Upgrade notes

- Regular update path applies (green button, or « À propos » → check for updates).
  No configuration change; all profiles and settings are kept. The new option is
  on by default; turn it off in Settings → Tracker if you prefer a silent recap.
- The two annotators are development tools shipped in the source tree, not in the
  executable — they need the dev interpreter (`tools/annotateur.py` and
  `tools/annotateur_boites.py`).
- Test suite: 783 passed, 1 skipped (dev-only ONNX↔torch parity, needs an exported
  graph).

**SHA-256**: PENDING