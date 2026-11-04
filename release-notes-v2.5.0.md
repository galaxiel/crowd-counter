# Compteur de manifestation v2.5.0

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.5.0

- **Four interface themes.** Dark (default), Light, **Navy blue**, and
  "Follow system" (the Windows theme, tracked live). Pick from the selector
  at the end of the button bar; the choice is remembered across launches
  (`config/local_theme.json`). Dark stays the default on purpose: the big
  counter is meant to be read outdoors, in full daylight.
- **Refreshed interface.** Settings groups are proper cards, "Lancer" is now
  a visually dominant primary button, input fields follow the theme (they
  used to render as native light widgets on the dark theme), tooltips and
  scrollbars are themed too. Same layout, same click behavior.
- **Model loading runs in the background** — the window no longer freezes
  while the weights load.
- **Throughput and remaining time** shown under the progress bar, and
  **Esc** stops the analysis.
- The model is **validated before a video is accepted**; applied detection
  profiles give visible feedback; the last video folder is remembered;
  launching an analysis is protected against double-start; a
  `tracks_presents_*` diagnostic report lists observed trajectories.
- **Ground-truth bench** (`tools/verite_terrain.py`): extracts a segment as
  a slow-motion video with burned-in frame numbers, then compares
  hand-annotated crossings against engine events automatically. Operator
  tooling — not part of the app UI.
- **Continuous integration**: the test suite runs on every push (GitHub
  Actions, Ubuntu, torch CPU, Qt offscreen). 629 tests, 0 failures.

## Installation

1. Download `CompteurManifestationV2-v2.5.0-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `fe410efd6870e3e439114949af63777e3cb712a754cab8fb1bcf1b31930d3d90`
