# Compteur de manifestation v2.6.4

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.6.4

- **Fixed: the update exchange could never succeed.** The swap script built
  a doubled path for the new version (nonexistent, silent failure, rollback
  without relaunch) — found by the first real end-to-end update test, where
  the application ended up running from the staging folder. From this
  version on, automatic updates genuinely work.
  ⚠️ **Install this 2.6.4 manually one last time** (updates FROM any
  version ≤ 2.6.3 hit the same safe rollback); every later release will
  then update itself automatically.
- **Your last-used settings survive relaunch** — threshold, model,
  confirmation… (the drawn line never persists: it belongs to each video).
  Any unreadable state falls back to defaults.
- **The end-of-analysis recap now shows the settings that produced the
  total** (model, threshold, confirmation, analysis size) — each trial is
  traceable to its configuration.
- **The update swap script writes a journal**
  (`%LOCALAPPDATA%\CompteurManifestation\journal-mise-a-jour.log`): every
  step and any error are recorded — a failed exchange is no longer silent.
- **Explicit taskbar identity** (AppUserModelID): Windows no longer shows a
  stale cached icon for the exe after rebuilds.

## Installation

1. Download `CompteurManifestationV2-v2.6.4-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `afa4d46092574d89c49290eca486a0022bae8ee6fc095915f4205b6284a8adf7`
