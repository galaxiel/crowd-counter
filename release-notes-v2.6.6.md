# Compteur de manifestation v2.6.6

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.6.6

Both changes fix things that looked broken from the outside:

- **Automatic updates never finished.** The small script that swaps the
  installation waited for the application to close using a pipe
  (`tasklist | find`) that **freezes** in that console-less context: the
  script stayed alive forever, the new version was never put in place, and
  nothing relaunched the app. The wait is now a single PowerShell command
  with no pipe, which returns as soon as the application is gone.

  ⚠️ **Because of this, versions up to 2.6.5 cannot update themselves** — the
  script they generate is the frozen one. **Install this 2.6.6 by hand one
  last time** (download the archive, extract it, replace your folder); from
  then on, the green button does the whole job by itself.

- **The taskbar icon showed a Qt default drawing** (a small white/green
  window) instead of the logo, while the executable, the window icon and
  the icon Explorer shows were all correct. Qt registers its window class
  with its own default icon, which the Windows shell was using for the
  button. The class icon is now explicitly set to the logo before the
  window appears.

## Installation

1. Download `CompteurManifestation-v2.6.6-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `97d774624d7b5c685d61a75c7201cb18e5809428e23e9c4c3c3a9ff1a0eb8b75`
