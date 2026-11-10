# Compteur de manifestation 3.2.0

Accuracy and honesty release: the screen and the counting engine can no longer
disagree, a broken read is no longer announced as "Done", and the result survives
the window. Plus a field-oriented interface refresh. The counting algorithm itself
is unchanged (IoU matching untouched).

## Added

- **Settings accordion.** The six settings cards become a single-open accordion
  (`QToolBox`), profiles first, help unfoldable section by section. The panel still
  only produces a config — it decides nothing.
- **Model badge before "Lancer".** A clickable pill shows whether the selected
  model is found or missing, and jumps to the Model field in settings. Replaces the
  old `.pt` status text.
- **"Copy result" / "Save…" buttons** at the end of an analysis: the result no
  longer lives only in RAM (clipboard, JSON + CSV export).
- **"Line locked" indicator** on the video during a session, and an explicit pause
  status: "Paused — line and direction locked".
- **ONNX shape validation at load time.** Static-batch graphs, multi-class outputs
  and non-RGB channels are refused with a readable export message — at load, not
  on the first tick.

## Fixed

- **Direction flipped while paused had no effect on the engine** (a silent wrong
  count: 315 vs ~1 on the reference footage). Line and direction are now locked
  from the moment a session opens and re-applied to the engine on every rebuild.
- **Settings applied live mid-analysis** (a non-reproducible total). The settings
  panel is frozen for the whole session, pause included — "applies to next run".
- **An unreadable frame was announced "Done".** End-of-file and decode errors are
  now distinguished; an interrupted read shows an "analysis incomplete" banner.
- **"Seconds" was the video duration, not compute time.** The "slower than
  real-time" warning can finally trigger; the consistency warnings from the engine
  are now shown in the recap.
- **Update install thread never stopped** (Qt crash when retrying after a cancel).
  The thread now quits on failure/cancel/success; a single update button is reused.
- **"Restart" never re-enabled.** It now activates after the first analysis.
- **Stale `.pt` advice and glob.** Advice and model list are `.onnx`; dropping a
  `.pt` no longer leads to a silent failure.
- Hardening: profile-name sanitisation, zip-slip filter (separator-aware),
  `nettoyer_anciennes` limited to the exact backup name (a neighbour `*.ancienne`
  survives), NaN guard on fps, readable disk-space error checked before download,
  file journal.

## Changed

- **Contextual primary button:** "Lancer" at rest, "Pause"/"Resume" during a
  session, "Restart" at the end; "Lancer" is greyed out while paused.
- The three themes' QSS now covers the new widgets (badge, lock, accordion tabs,
  recap buttons).

## Upgrade notes

- Regular update path applies (green button, or « À propos » → check for updates).
  No configuration change; all profiles and settings are kept.
- 3.2.0 hardens the updater, but the updater that runs during an update is the one
  **already installed**. The normal happy-path update from 3.1.0 is unaffected. If
  a previous 3.1.0 update attempt was **cancelled or failed**, restart the app
  before retrying (3.1.0 could crash on retry); when in doubt, install 3.2.0
  manually once — every later update is fixed.
- Full French write-up of the refactor: `docs/refonte-v3.2.0.md`. Test suite:
  734 passed, 1 skipped (dev-only ONNX↔torch parity, needs an exported graph).

**SHA-256**: ae9e42630bbfce7b714a3367371afc4c210ddc863655b9015d5b2af4f247ba40