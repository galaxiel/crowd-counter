# Compteur de manifestation 3.1.0

Display quality release: annotations no longer freeze on screen.

## Added

- **On-screen annotations follow people through brief tracking losses.**
  When someone moves fast or passes behind a flag, the tracker can lose
  them for one to three frames. The green counted box and the track dot
  used to FREEZE at the last known position — a box painted on empty road.
  They now keep sliding along the last known direction, and beyond three
  frames they fade out instead of lying (they reappear on the head when
  the tracker re-catches the person).

- The counting engine is untouched: `Track.absent` (frames since the last
  detection) is exposed as read-only information, and the extrapolated
  positions live only in the display layer. Proven identical counting:
  every crossing event lands on the same frame as the previous release on
  the reference footage.

## Upgrade notes

- Regular update path applies (green button or « À propos » → check for
  updates). No configuration change; all profiles and settings are kept.

**SHA-256**: 21abbcca9cd5ac6e92ec458394e1cffece0bd4b337c2796695be6afd937a39d3
