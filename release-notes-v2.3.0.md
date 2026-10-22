# Compteur de manifestation v2.3.0

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.3.0

- **Models live in a `modeles/` folder.** The weights now ship inside
  `modeles/`, next to the executable, and the software scans that folder.
  Drop any `.pt` (or `.onnx`) there and it appears in the *Modèle* list.
- **"Parcourir…" button** — pick a model file from anywhere on the computer,
  wherever it is stored, without moving it.
- **The list refreshes itself.** A file added to `modeles/` shows up the next
  time you open the list — no restart needed.
- **A personal folder that survives updates:**
  `%LOCALAPPDATA%\CompteurManifestation\modeles`. The folder next to the
  executable is replaced when you extract a new version; this one is not.
- **Fixed:** a model listed from `modeles/` could fail to load
  ("modèle introuvable") because loading only looked next to the executable.
  Listing and loading now scan the same folders, in the same order — a model
  that is offered is a model that loads.

## Installation

1. Download `CompteurManifestationV2-v2.3.0-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestationV2.exe`.
4. **First launch needs internet** — it downloads and installs PyTorch
   (~2.4 GB CUDA, ~200 MB CPU) into `%LOCALAPPDATA%\CompteurManifestation\`.
   Later launches are offline and fast.

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
