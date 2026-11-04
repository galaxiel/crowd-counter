# Compteur de manifestation v2.6.2

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.6.2

- **Fixed: the interface froze as soon as an update started.** The download
  progress bar was wired through a receiver-less lambda, so Qt executed it
  in the network thread — touching a widget from there froze the window
  ("not responding" at the first downloaded block). Progress now flows
  through a main-window slot, covered by a regression test that emits from
  a background thread and asserts the execution thread.

This is the intended update target for anyone running 2.6.0 or 2.6.1: the
green button downloads this archive, verifies its SHA-256, replaces the
application and relaunches it.

## Installation

1. Download `CompteurManifestationV2-v2.6.2-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `819ec6e8e9e5cb1843d1b8629135e5caf8fd5ad4704d878f1a90ba3e5f25d488`
