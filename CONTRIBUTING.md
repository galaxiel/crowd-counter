# Contributing to crowd-counter

Thanks for considering a contribution. This document is short on purpose:
the project has a few non-negotiable working rules, and everything else is
negotiable.

## What this project is

A desktop application (Python 3.11 + PySide6) that counts people crossing a
line in demonstration footage. The engine is ONNX Runtime (v3): no PyTorch,
no ultralytics at runtime — models ship as `.onnx` graphs, and the
preprocessing/NMS are vendored in `compteur/detecteur.py`.

## Before you propose anything

1. **Read `AGENTS.md`** — it is written for any contributor (human or agent):
   interpreter, test workflow, traps that were paid for in real bugs.
2. **Read `ROADMAP.md`** — rejected ideas stay rejected; each item says what
   measurement would reopen it.
3. **The one rule that outranks everything: measure before you claim.** A
   number arrives with its scope (frames, settings, hardware). Counting
   claims go through the ground-truth tool (`tools/verite_terrain.py`).

## Hard rules of the codebase

- `compteur/` (the engine) must never import a GUI library — enforced by
  `tests/test_isolation_ui.py`.
- The default configuration (`config/default.json`) and the `Config`
  dataclass must stay in sync — enforced by a dedicated test.
- Every settings description in the panel (`AIDE` in
  `interface/panneau_reglages.py`) must be ≤ 5 lines and cite the measured
  figure that backs its advice — enforced by tests.
- Tests use fake sessions/detectors; no test downloads anything or runs
  real inference (the parity test is marked `slow` and self-skips without
  the graph).
- No OS-specific paths in tests (Linux CI would break) — use `tmp_path` and
  compare through `pathlib.Path`.

## Running the tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -q -m "not slow"   # fast gate, ~10 s
python -m pytest tests/ -q                 # full suite, ~13 s
```

On Linux, `requirements.txt` installs plain `onnxruntime` (CPU) via a
platform marker; the tests never run inference, so this is enough.

## Pull requests

- One intent per PR. If a bug fix drags a refactor with it, split them.
- CI runs the fast gate on every push; it must be green before review.
- If you change the detection path, prove parity against the current
  engine before proposing it (see
  `docs/design/v3-onnx-proposition.md` for the method used when the v3
  engine was adopted — parity frame by frame, then full-video counts).

## Releasing

Releases are cut by the maintainer on explicit request, following
`docs/BUILDING.md` § Publishing. A release always ships the zip **and** its
`.zip.sha256` (the built-in updater verifies it).
