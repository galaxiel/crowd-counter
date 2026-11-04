# Compteur de manifestation v2.6.0

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.6.0

- **Automatic updates.** At startup, the application checks for the latest
  published release. If a newer version exists, a green button appears in
  the button bar — no forced dialog. One click: the archive is downloaded
  (with resume on interruption), verified against the **SHA-256 published
  alongside it**, then the application closes, replaces itself and relaunches.
  - Settings, named profiles and models you dropped in `modeles/` are kept.
  - The previous version is kept as a `*.ancienne` backup folder until the
    new one has started successfully — if anything goes wrong, the working
    installation is still there.
  - Without a published checksum, the update falls back to opening this
    download page (level 1) — installing without verification is refused
    by design.
  - Available in the packaged executable only.
- This is the **first release that later versions can install
  automatically**; releases from now on ship a `.zip.sha256` asset.

## Installation

1. Download `CompteurManifestationV2-v2.6.0-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `f7113a3bd755d2651e41cb3a803a12adca2b8c19eea6d0792250ba9896dff496`
