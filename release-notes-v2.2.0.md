# Compteur de manifestation v2.2.0

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.2.0

- **Faster analysis.** The detector now processes images in batches (4 at a time) instead of one by one. Measured on the reference 3000-frame video: **~45 s with batching versus ~115 s without**, with the same count (verified frame by frame). The counting itself is strictly frame-by-frame and unchanged — only the detection calls are grouped.
- **Progress bar.** A bar under the video shows how far the analysis has gone: frames done / total, with percentage. If the video container does not declare its frame count, the bar shows a busy indicator instead of a false percentage.
- **Lighter preview rendering.** The annotated view no longer pays full-frame conversions on every displayed frame; the preview refreshes at ~15 fps while the analysis itself keeps running at full speed.
- **Count flash fixed on fast scenes.** The red flash around the video now also triggers when a count happens between two displayed frames — previously it could be missed entirely.
- Repository housekeeping (visible on GitHub, not in the app): the abandoned v1 build (4.3 GB executable) was removed, and the README was split into [`docs/BUILDING.md`](docs/BUILDING.md) and [`docs/USAGE.md`](docs/USAGE.md).

## Installation

1. Download `CompteurManifestationV2-v2.2.0-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/` and the `.pt` files).
3. Run `CompteurManifestationV2.exe`.
4. **First launch needs internet** — it downloads and installs PyTorch (~2.4 GB CUDA, ~200 MB CPU) into `%LOCALAPPDATA%\CompteurManifestation\`. Later launches are offline and fast.

## Verify the download

sha256: `ee5129257c6ca28a4629ff55ba0f41c6febcd462bf5573e5b9b8a11fb6140831`

## Known limitations

- **Windows only**, version 10 or later. NVIDIA GPU required for fast analysis (CUDA); a machine without a card falls back to CPU, which works but is slow.
- The counting line is **drawn by hand** (two clicks) — on a fixed camera above the scene, as intended.
- Occlusion is not resolved: people fully hidden behind others are not counted.
- The counter is an **estimate, not a measurement** — there is no annotated benchmark, only manual counts on test videos.
