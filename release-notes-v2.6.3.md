# Compteur de manifestation v2.6.3

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.6.3

- **Application icon.** The cyan crowd mark now shows in the title bar, the
  taskbar, the first-launch installer screen, and on the `.exe` itself in
  Explorer.
- **Version properties on the `.exe`.** Right-click → Properties → Details
  now reports the version, derived from the source of truth at build time —
  so every update automatically carries its own version number.

This release is the first real end-to-end exercise of the **automatic
updater**: running 2.6.2 shows a green "update" button (the updater code
shipped in 2.6.2 is the fixed one), downloads this archive, verifies its
SHA-256, replaces the application and relaunches it.

## Installation

1. Download `CompteurManifestationV2-v2.6.3-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `20b7f43b10d5f9ec7e5381f1e424071b74b4d684e771d67b24d94cbc9f06cfe3`
