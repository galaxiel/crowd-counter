# Compteur de manifestation 2.10.0

An "About" dialog with a manual update check, and the mouse wheel stops
editing fields it merely flies over.

## Added

- **"À propos" dialog** (button at the end of the toolbar): the software
  version, a **"Vérifier les mises à jour"** button — the same check that
  runs at startup, triggered on demand, with the result announced right in
  the dialog — and a link to the GitHub releases page. The green button
  remains the installation gesture: it only appears when an update EXISTS.
  Honesty note: "no update found" can also mean the network was down — the
  message says so instead of promising.

## Fixed

- **The mouse wheel scrolls the settings panel; it no longer edits the
  fields it flies over.** Qt's native behaviour changed a number or a list
  every time the wheel crossed one while scrolling — a setting corrupted
  without noticing. A field now only reacts to the wheel when it has focus
  (click into it first); otherwise the panel scrolls.

**SHA-256**: 969cab42d501057ad641dee26210650e1e34b843db8726d45c9715c9956689ae
