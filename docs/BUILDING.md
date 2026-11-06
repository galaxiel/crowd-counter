# Building the executable

How to rebuild the Windows executable from source, and everything about GPU /
CUDA performance. To run the application from source instead, see the
[README](../README.md#installing-and-running-from-source).

## Building the executable

**v3 — the build is now trivial.** The engine is ONNX Runtime: no torch, no
ultralytics, no `uv.exe`, no first-launch download. Any clean Python 3.11
environment works — the only GPU layer is DirectML, which ships inside the
`onnxruntime-directml` package.

```bash
# 1. clean environment (or simply use requirements-dev.txt on the dev box)
python -m venv build-env
build-env\Scripts\python -m pip install -r requirements-dev.txt

# 2. build — note the workpath
build-env\Scripts\python -m PyInstaller --clean --workpath build/v2 crowd-counter.spec
build-env\Scripts\python tools/copier_modeles.py
```

`copier_modeles.py` copies the shipped `.onnx` graphs (`tetes-medium`,
`tetes-nano`, `tetes-medium-1280`) into the dist. The `.pt` source weights
are NOT shipped and NOT executable in v3 — they live on the development
machine only, for re-export and fine-tuning.

The old v2 sequence (torch CUDA wheels from a dedicated index, ultralytics,
`uv.exe`, the opencv purge dance) is gone with the torch engine; its history
lives in git and in `docs/design/v3-onnx-proposition.md`.

The spec also embeds two things at build time, both loud-fail if missing:
the **application icon** (`resources/crowd-counter.ico` — title bar, taskbar,
Explorer) and the **version resource** shown in the exe's Properties →
Details, **derived from `compteur.VERSION`** on every build — the single
source of truth, so the exe cannot lie about its version and every update
carries its own number automatically.

Result: `dist/CompteurManifestation/` — ~340 MB with the ONNX graphs
(`copier_modeles.py` places them in `dist/CompteurManifestation/modeles/`,
the subfolder the application scans and the release zip ships). Nothing is
downloaded at first launch. The `--workpath build/v2` keeps PyInstaller's
intermediate `.toc` files in a workpath of their own — sharing it with other
builds mixes stale state in.

`copier_modeles.py` also copies the shipped settings profiles
(`config/profils/*.json` from the repository) into
`dist/CompteurManifestation/config/profils/` — the folder the settings panel
lists. A shipped profile makes its field-validated defaults available on
every fresh install; the updater only restores an old profile when the name
is not already present in the new install, so a user who tweaks a shipped
profile should save their variant under a different name to keep it across
updates.

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

This is the order used for v2.5.0 through v2.6.4. Do not reorder it: the
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
pwsh -NoProfile -Command "Compress-Archive -Path 'dist/CompteurManifestation' -DestinationPath 'dist/CompteurManifestation-vX.Y.Z-win64.zip' -Force"

# 3. hash — from git-bash, INSIDE the folder that holds the zip, so the
#    asset records a bare filename instead of a local path (see the trap
#    below)
cd dist && sha256sum CompteurManifestation-vX.Y.Z-win64.zip | tee CompteurManifestation-vX.Y.Z-win64.zip.sha256

# 4. put the same value as the LAST line of the release notes
#    **SHA-256**: <hash>

# 5. publish — this also creates the tag vX.Y.Z
gh release create vX.Y.Z \
  CompteurManifestation-vX.Y.Z-win64.zip \
  CompteurManifestation-vX.Y.Z-win64.zip.sha256 \
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

**Naming: what carries the version, and what must not.** The archive is
named `CompteurManifestation-vX.Y.Z-win64.zip`. The old
`CompteurManifestationV2-` prefix was a leftover from the abandoned v1
(releases up to v2.6.4 carry it; newer ones drop it) — the rename is safe
because `chercher_release` accepts **any** `*.zip` asset name, as long as the
checksum asset ends in `.zip.sha256`.

The folder **inside** the archive stays `CompteurManifestation/` and the
executable stays `CompteurManifestation.exe`, **without any version** — and
they must stay that way. `preparer_staging` extracts the archive and looks
for `<staging>/<installed-folder-name>/CompteurManifestation.exe`, and the
swap script moves and relaunches those exact names. A versioned folder or exe
would make every future update fail with « archive inattendue » — and since
the updater that runs during an update is the one **already installed**, an
old installation could never be taught a different convention
(chicken-and-egg). Fixed names also keep shortcuts, taskbar pins and external
scripts working across updates. The version belongs in: the zip name, the
release tag, the window title, and the exe's Properties → Details
(`FileVersion`, generated from `compteur.VERSION` at build time).

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
`<hash> *CompteurManifestation-vX.Y.Z-win64.zip` (the `*` is coreutils'
"binary mode" marker, expected and harmless — `sha256sum -c` accepts it).

## Performance and GPU

The engine is ONNX Runtime. On Windows the GPU layer is **DirectML**, which
drives NVIDIA, AMD and Intel cards alike — the software no longer requires
an NVIDIA card. Measured on this machine (RTX 4070 SUPER, 1080p video
analysed at 1280):

| Path | Throughput |
|---|---|
| torch CUDA (v2, historical) | ~58 img/s |
| **ONNX Runtime DirectML (v3)** | **~51 img/s** |
| ONNX Runtime CPU (fallback) | works, much slower |

The full comparison — parity proof, both paths, the decision rule — lives in
[`docs/design/v3-onnx-proposition.md`](design/v3-onnx-proposition.md).

## How much it changes

Measured on the reference video (v2 numbers, kept for the record):

| Device | Throughput | 4-minute video |
|---|---|---|
| torch CUDA (RTX 4070 SUPER) | ~27 img/s | ~9 min |
| CPU torch | ~7 img/s | ~35 min |

In v3 the same GPU through DirectML measured ~51 img/s on the plongée video
(see the proposition document). A CPU-only machine runs, just slower — and
it runs at all, which the v2 CUDA-only wheel did not allow on AMD/Intel.

### Choosing where the compute happens

The *Calcul sur* setting, in the *Périphérique de calcul* panel:

| Choice | Effect |
|---|---|
| **Automatic** (default) | GPU (DirectML) if the machine has one, CPU otherwise |
| **GPU required** (réglage « cuda », historique) | A GPU is required. Without one, the analysis **falls back to CPU with a message** — crashing in the field costs more than a slow run you can at least watch |
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

### AMD and Intel are supported in v3

The v2 constraint ("a single executable, built with CUDA — AMD not
supported") is gone with the torch engine: DirectML drives NVIDIA, AMD and
Intel cards alike, and the CPU fallback covers the rest.

The v2 PyInstaller traps around `hooks-v2/hook-torchvision.py` (torchvision's
`_C.stable` extension, CUDA DLLs loaded by `torch.ops.load_library()`) died
with the torch engine; the hooks stay in the repository as belt-and-braces
excludes.

## If the GPU is not being used

The application reports it in the status bar and in the console, and analyses
anyway on the CPU, very slowly.

Under PyInstaller, two traps were handled explicitly (see
`crowd-counter.spec` and `hooks-v2/hook-torchvision.py`):

- torchvision's NMS extension is called `_C.stable` since 0.29 and is not a
  Python module: without a dedicated hook, inference stops on `Couldn't load
  custom C++ ops`;
- CUDA DLLs are loaded by `torch.ops.load_library()`, never by an `import`:
  PyInstaller does not find them on its own.
