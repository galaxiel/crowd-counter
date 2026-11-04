# Compteur de manifestation v2.6.1

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.6.1

- **Drag & drop a video** — drop a video file anywhere on the window to load
  it. Same rules as the file picker: one file, video extensions only
  (`.mp4`, `.avi`, `.mkv`, `.mov`, `.m4v`, `.webm`), and drops are refused
  while an analysis is running — dropping a file must never silently kill a
  running count.

This release exists mostly as an update target: it is the first version the
**automatic updater** (introduced in 2.6.0) can install. If you run 2.6.0,
a green button offers to update.

## Installation

1. Download `CompteurManifestationV2-v2.6.1-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `10ad351f0bd72f2e0e7333aecfb21cc49144dd0c931fbd40e0d5d355ce1c50ea`
