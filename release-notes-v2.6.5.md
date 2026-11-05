# Compteur de manifestation v2.6.5

**Windows only · NVIDIA GPU recommended** — downloads PyTorch (~2.4 GB CUDA) on first launch, then works offline.

## What's new in 2.6.5

- **A welcome hint in the video area.** Before any video is loaded, the big
  black frame used to say nothing at all. It now invites you to drop a video
  there, or to click *Charger la vidéo* — naming both ways to load a video,
  including drag & drop, which no button advertises. The hint disappears as
  soon as the first frame is displayed.

That is the whole change. One naming detail for the download page: the
archive drops the legacy `V2` from its file name (same application, same
folder, same executable as always — the updater accepts any archive name).

**If you are running 2.6.4**, this is the first release the built-in updater
installs fully on its own: the green button downloads (resumable), verifies
the SHA-256, swaps the folder and relaunches — settings, profiles and models
kept, the previous version parked as a `*.ancienne` backup, and a journal
written to `%LOCALAPPDATA%\CompteurManifestation\journal-mise-a-jour.log`.

## Installation

1. Download `CompteurManifestation-v2.6.5-win64.zip`.
2. Extract the whole folder somewhere (keep the `.exe` next to `_internal/`
   and the `modeles/` folder).
3. Run `CompteurManifestation.exe`.

First launch downloads PyTorch CUDA (~2.4 GB) once; after that the software
works fully offline.

**SHA-256**: `b77e8858733c9cb5ea31b8c4a862caab006ad290423120d5eec65afd196ee2cc`
