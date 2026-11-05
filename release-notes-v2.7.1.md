# Compteur de manifestation 2.7.1

Fix: the automatic update left the application with a wrong working
directory.

## Fixed

- **After an automatic update, the application restarted with the WRONG
  working directory** (the parent folder instead of its own installation
  folder): the settings-profile list was empty, "Load this profile" found
  nothing, and the memory files (`config/local_*.json`) were written into
  the parent folder. Found by the first real end-to-end auto-update test
  (2.6.6 → 2.7.0, which otherwise succeeded).
- Two fixes: the update-swap script now relaunches the application **from
  its own folder**, and the frozen application re-anchors its working
  directory to its exe's folder at startup — whichever way it is launched.
- Profiles and settings themselves were never lost; they are all in this
  release as well (`manif-vue-laterale-haute`, `manif-vue-plongeante`).

**SHA-256**: 769757203a44dad2c743f08e663f82445be53b519ddbeecc64ffe70f9be6983f
