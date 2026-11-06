# Compteur de manifestation 3.0.0

**The major version the project's own versioning rule exists for: the way the
software is installed has changed.** The engine is now ONNX Runtime — no
PyTorch, no ultralytics, no 2.4 GB download on first launch, and no NVIDIA-only
restriction.

## What v3 means for you

- **Nothing to download on first launch.** The archive contains everything.
- **Any GPU works**: the GPU layer is Windows' DirectML — NVIDIA, AMD and
  Intel cards are all accelerated. v2 required an NVIDIA card.
- **Same counting.** Proven, not promised: every one of 2 896 detections on
  the reference footage has an exact twin in the new engine, and full-video
  counts match the old engine within ±1 person on all four field videos.
- **Slightly slower on an NVIDIA card** (~88 % of v2's throughput, measured
  51 img/s on an RTX 4070) — imperceptible in use: a 5-minute video still
  counts in under 2 minutes.

The full engineering story — why torch weighs 2.4 GB, both engine paths, the
two measurement-found traps (RGB conversion, non-reimplementable NMS), the
decision rule — is in
[`docs/design/v3-onnx-proposition.md`](docs/design/v3-onnx-proposition.md).

## Added

- `compteur/erreurs.py`: the data-folder helper and installer exceptions that
  survive the removal of the download machinery.

## Removed

- The PyTorch download machinery (`compteur/telechargement.py`, 1 545 lines),
  the first-launch installation screen (`interface/demarrage.py`), `uv.exe`
  and the venv rebuild in `main.py`: double-clicking the exe now simply opens
  the window.
- `.pt` model files are no longer executable in the app — models ship as
  `.onnx` graphs (exportable from the `.pt` sources kept on the development
  machine for future fine-tuning).

## From the 2.x line (unchanged)

Profiles shipped with the app, "Sens" and "Recommencer" buttons, magnetic
line tracing, honest detection zone on tilted lines, mouse-wheel scrolling,
the "À propos" dialog with manual update check.

**SHA-256**: bda18ffdd45a94d8223f634cd1b86c098079d917089c1009238cdf62de649b35
