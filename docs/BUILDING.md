# Building the executable

How to rebuild the Windows executable from source, and everything about GPU /
CUDA performance. To run the application from source instead, see the
[README](../README.md#installing-and-running-from-source).

## Building the executable

**Build from a clean virtual environment.** This is not advice — it is the
difference between a lean executable and a bloated one.

Ultralytics imports its optional inference backends conditionally. If they are
installed, PyInstaller bundles them: TensorRT (1.5 GB), TensorFlow (1.1 GB),
ONNX Runtime (741 MB), xformers (413 MB) and bitsandbytes (213 MB). **None of
them is used** — this project only ever runs PyTorch. Excluding them from the
spec does not work: PyInstaller crashes while reading one of their hooks. The
reliable approach is to make them unavailable in the first place — a virtual
environment that never had them.

```bash
# 1. clean environment, nothing else in it
python -m venv build-env

# 2. torch CUDA + matching torchvision MUST come from the same index
build-env\Scripts\python -m pip install torch==2.14.1+cu126 torchvision==0.29.1+cu126 ^
    --index-url https://download.pytorch.org/whl/cu126

# 3. the rest — from PyPI, never from the torch index
build-env\Scripts\python -m pip install ultralytics PySide6 pyinstaller pytest

# 3bis. OpenCV HEADLESS, not opencv-python: the application never shows an
# OpenCV window (the UI is PySide6) — the headless build is the right
# package for this. NOTE on weight: measured 2026-10-30, the saving is only
# ~0.5 MB (dist 293.7 -> 293.2 MB), because OpenCV 5.x no longer ships Qt
# DLLs inside its Windows wheel (4.x did; that's where the old "~80 MB"
# estimate came from).
# TRAP: ultralytics declares opencv-python as a dependency, so pip installs
# the FULL build even when the headless one is requested, and both packages
# write into the same site-packages/cv2 folder. Purge BOTH, then install
# the headless build alone — that is the only deterministic way to end up
# with a headless-only cv2:
build-env\Scripts\python -m pip uninstall -y opencv-python opencv-python-headless
build-env\Scripts\python -m pip install opencv-python-headless

# 4. build — note the workpath
build-env\Scripts\python -m PyInstaller --clean --workpath build/v2 crowd-counter.spec
build-env\Scripts\python tools/copier_modeles.py
```

The spec also embeds two things at build time, both loud-fail if missing:
the **application icon** (`resources/crowd-counter.ico` — title bar, taskbar,
Explorer) and the **version resource** shown in the exe's Properties →
Details, **derived from `compteur.VERSION`** on every build — the single
source of truth, so the exe cannot lie about its version and every update
carries its own number automatically.

**torch and torchvision must come from the same index.** A CPU-only
torchvision next to a CUDA torch crashes `torchvision::nms` on CUDA. This is
the single most common packaging mistake here.

Result: `dist/CompteurManifestation/` — ~290 MB without the weights
(`copier_modeles.py` places them in `dist/CompteurManifestation/modeles/`,
the subfolder the application scans and the release zip ships).
(~360–400 MB with them). torch is NOT bundled; it is downloaded into
`%LOCALAPPDATA%\CompteurManifestation\` on first launch. The `--workpath
build/v2` keeps PyInstaller's intermediate `.toc` files in a workpath of their
own — sharing it with other builds mixes stale state in.

### Verify the build before shipping it

```bash
build-env\Scripts\python tools/verifier_lancement_exe.py
```

Launches the executable the way a user would, checks that a window titled
*Compteur de manifestation* appears, that the weights are next to it, and that
the console output does not contain the silent `Config` fallback. A build that
succeeds does not prove that a double-click works — that is exactly what this
tool covers.

> If the folder is locked during a rebuild (`Device or resource busy`), the
> executable from the previous build is still running. Close it first.

## Publishing a release

Publication happens **only on an explicit request** from the operator — the
same rule as the build. `master` is allowed to be ahead of the last release;
that is not an oversight to fix.

This is the order used for v2.5.0 through v2.6.2. Do not reorder it: the
archive is proven to start before it is zipped, and hashed before it is
published. (An earlier draft of this section mandated a FLAT zip — that was
wrong and would have broken the next update; see the rationale below, and
check any procedure against `compteur/mise_a_jour.py` before trusting it.)

```bash
# 1. prove the freshly built executable starts (see the section above)
build-env\Scripts\python tools\verifier_lancement_exe.py

# 2. zip — the archive MUST KEEP the wrapping folder: CompteurManifestation/
#    at the root of the zip, with the .exe, _internal/ and modeles/ inside it.
#    Without the /* (flattening) — the updater refuses a flat archive.
pwsh -NoProfile -Command "Compress-Archive -Path 'dist/CompteurManifestation' -DestinationPath 'dist/CompteurManifestationV2-vX.Y.Z-win64.zip' -Force"

# 3. hash — from git-bash, INSIDE the folder that holds the zip, so the
#    asset records a bare filename instead of a local path (see the trap
#    below)
cd dist && sha256sum CompteurManifestationV2-vX.Y.Z-win64.zip | tee CompteurManifestationV2-vX.Y.Z-win64.zip.sha256

# 4. put the same value as the LAST line of the release notes
#    **SHA-256**: <hash>

# 5. publish — this also creates the tag vX.Y.Z
gh release create vX.Y.Z \
  CompteurManifestationV2-vX.Y.Z-win64.zip \
  CompteurManifestationV2-vX.Y.Z-win64.zip.sha256 \
  --notes-file release-notes-vX.Y.Z.md

# 6. verify BOTH assets are actually on the page (a silent upload is not a
#    success), and that the digest matches the notes
gh release view vX.Y.Z --json assets --jq '.assets[] | "\(.name)\t\(.digest)"'
```

**Why the zip must KEEP the `CompteurManifestation/` folder.**
`compteur/mise_a_jour.py::preparer_staging` extracts the archive into a
staging directory, then looks for the application at
`staging/<folder-name>/CompteurManifestation.exe` — it derives the expected
subfolder from the running installation's own name. A flat archive (exe at
the root of the zip) is therefore **refused** with « archive inattendue »:
the update fails safely, nothing is installed. The wrapping folder is not a
cosmetic choice; it is what the updater checks for. (Verified against the
v2.6.2 release asset before writing this paragraph.)

**Why the `.zip.sha256` asset is not optional.** `lire_derniere_version` looks
for the asset to know what to verify; without it `sha256` comes back `None` and
the updater falls back to the degraded path (open the release page). Nothing
fails loudly — the application simply stops checking the download against the
published hash, while the README tells users it does. Publishing the zip alone
is therefore a silent regression, not a smaller release.

**Trap: the hash line must name the file, not a local path.** Running
`sha256sum` from a scratch directory produces
`<hash>  */tmp/release-v262/CompteurManifestationV2-v2.6.2-win64.zip`. The
application only reads the first field so it still works, but the asset is then
useless to anyone doing `sha256sum -c` on their own download. Run it from
`dist/`, as in step 3, so the line reads
`<hash> *CompteurManifestationV2-vX.Y.Z-win64.zip` (the `*` is coreutils'
"binary mode" marker, expected and harmless — `sha256sum -c` accepts it).

## Performance and GPU

**torch must be installed as the CUDA version.** On this machine:

```
torch 2.14.1+cu126
torchvision 0.29.1+cu126
```

That is what `installer.py` does when it detects an NVIDIA card.

### How much it changes

Measured on this machine, on the reference video:

| Device | Throughput | 4-minute video |
|---|---|---|
| CUDA (RTX 4070 SUPER) | ~27 img/s | ~9 min |
| CPU | ~7 img/s | ~35 min |

A CPU torch works, but the counter becomes unusable live, and long scenes
will take hours. That is why the first launch downloads the CUDA wheel
(~2.4 GB): `torch_cuda.dll` alone weighs 1 GB, `cublasLt` 500 MB, cuDNN over
1 GB.

### Choosing where the compute happens

The *Calcul sur* setting, in the *Périphérique de calcul* panel:

| Choice | Effect |
|---|---|
| **Automatic** (default) | CUDA if the machine has one, CPU otherwise |
| **NVIDIA GPU (CUDA)** | The GPU is required. Without a card, the analysis **falls back to CPU with a message** — crashing in the field costs more than a slow run you can at least watch |
| **CPU only** | The processor is required even with a GPU present. This is the remedy when the GPU crashes on a particular scene |

This choice does **not** change the count: the same scene is analysed the same
way in both cases.

The *Calcul : CUDA — NVIDIA GeForce RTX 4070 SUPER* or *Calcul : CPU
uniquement* indicator is displayed **permanently** in the status bar, under
the counter. It updates as soon as a setting changes, and it reports what is
actually being used — not what was requested.

Under PyInstaller, `nvidia-smi` only queries the driver: it ignores
`CUDA_VISIBLE_DEVICES`, which is a Linux convention. To verify the CPU branch
on a machine that does have a card, the installer exposes `--sans-gpu`.

### AMD is not supported

A deliberate choice: **a single executable, built with CUDA**. A CPU-only
torch wheel weighs ~200 MB against ~3 GB for CUDA; shipping both would double
the size of the `dist/` folder for a use case that is not ours (an AMD card in
2026 is rare on the demonstration-camera market this targets). The program
therefore runs on AMD in CPU mode, at ~7 img/s — usable for a short video, not
for a whole demonstration.

### If the GPU is not being used

The application reports it in the status bar and in the console, and analyses
anyway on the CPU, very slowly.

Under PyInstaller, two traps were handled explicitly (see
`crowd-counter.spec` and `hooks-v2/hook-torchvision.py`):

- torchvision's NMS extension is called `_C.stable` since 0.29 and is not a
  Python module: without a dedicated hook, inference stops on `Couldn't load
  custom C++ ops`;
- CUDA DLLs are loaded by `torch.ops.load_library()`, never by an `import`:
  PyInstaller does not find them on its own.
