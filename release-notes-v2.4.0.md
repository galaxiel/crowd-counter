# Compteur de manifestation v2.4.0

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.4.0

- **Models renamed so the name says what they detect.** The convention is
  `target-weight[-precision]`:
  - `tetes-medium.pt` — **the default**: head detector, 25.9 M parameters;
  - `tetes-nano.pt` — head detector, 3.0 M parameters: the light, fast one;
  - `tetes-medium-1280.pt` — head detector trained at 1280 px.
  A `tetes-…` model detects one thing — heads — which is what this software
  counts.
- **A misleading name is gone.** The file previously shipped as
  `yolov8n-head.pt` was **not** a "nano" model: its own metadata shows an
  M-sized network (25.9 M parameters, the same class as `tetes-medium.pt`).
  Choosing it expecting a light model gave a heavy one. It is now
  `tetes-medium-1280.pt`, named for what it is.
- **A naming legend ships inside `modeles/`** (`LISEZ-MOI.txt`), so the
  convention is explained next to the files.
- Generic 80-class models (COCO: person, car, bicycle…) are named
  `personnes-et-objets-…` when you use them: the name says they detect 80
  object types, people among them — not heads.

## Installation

1. Download `CompteurManifestationV2-v2.4.0-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestationV2.exe`.
4. **First launch needs internet** — it downloads and installs PyTorch
   (~2.4 GB CUDA, ~200 MB CPU) into `%LOCALAPPDATA%\CompteurManifestation\`.
   Later launches are offline and fast.

## Upgrading from an earlier 2.x

Your own models are untouched: a file you put in
`%LOCALAPPDATA%\CompteurManifestation\modeles` keeps working under its own
name. Only the **shipped** models changed name. A saved profile that pointed
at the old default (`medium.pt`) points at a name that no longer exists —
pick `tetes-medium.pt` again in the settings (the list proposes it).

## Verify the download

sha256: `SHA256_A_COMPLETER`

## Known limitations

- **Windows only**, version 10 or later. NVIDIA GPU required for fast analysis
  (CUDA); a machine without a card falls back to CPU, which works but is slow.
- The counting line is **drawn by hand** (two clicks) — on a fixed camera above
  the scene, as intended.
- Occlusion is not resolved: people fully hidden behind others are not counted.
- The counter is an **estimate, not a measurement** — there is no annotated
  benchmark, only manual counts on test videos.
