# Compteur de manifestation 2.7.0

Shipped detection profiles — field-validated settings now come with the
software.

## Added

- **Settings profiles shipped with the application.** Two profiles validated
  on real demonstration footage are copied into every installation
  (`config/profils/`) and selectable in Settings → Profiles:
  - **manif-vue-laterale-haute** — side view from ~3–4 m, banners partially
    hiding heads: `tetes-medium-1280`, confidence threshold 0.15, 1
    confirmation frame, direction −1;
  - **manif-vue-plongeante** — overhead view (bridge/overpass), people
    crossing top-to-bottom with fast-moving heads: `tetes-medium-1280`,
    confidence threshold 0.05, 1 confirmation frame, match threshold 0.15,
    1 hysteresis frame, direction −1.
- The counting line is still drawn by hand on each video — profiles carry
  every other setting.
- `tools/copier_modeles.py` (the post-build step) now also copies
  `config/profils/*.json` into the installation.
- Personal variants of a shipped profile should be saved under a different
  name: on update, the shipped profile is replaced by the one from the
  archive (the updater only restores an old profile whose name is not
  already present).

**SHA-256**: f6356b6988e7f792943ec5620bca5cc79ce34cfcb94d3cf2335ce92e6c50b03e
