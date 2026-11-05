# Using the software

Day-to-day use of the application. To download or install it first, see the
[README](../README.md).

1. **Load the video** — *Charger la vidéo* button, or **drag a video file
   anywhere onto the window** (one file; `.mp4`, `.avi`, `.mkv`, `.mov`,
   `.m4v`, `.webm`). Drops are ignored while an analysis is running — dropping
   a file must never kill a count in progress. The application remembers the
   folder you last opened a video from.
2. **Draw the line** — *Tracer la ligne* button, then two clicks on the image,
   at the top and bottom of the line you care about. Drawing is "armed": a
   stray click outside that gesture is ignored. The detection band follows the
   line wherever you put it. **Magnetic snapping**: if your second click lands
   within 5° of the horizontal or the vertical, the line snaps exactly
   straight — a hand-drawn line that "almost" straight would otherwise make
   the detection zone drift away from the drawing.
3. **Set the direction** — the *Sens : …* button in the bottom bar, one click
   flips the counted direction; its label says exactly what is counted
   ("Droite → gauche" on a vertical line, "Haut → bas" on a horizontal one)
   and the green arrow follows. **If the count stays at zero after a few
   seconds, this is almost always why** — the software shows a reminder
   rather than failing silently.
4. **Adjust the sensitivity** — the parameter that matters most is *Frames de
   confirmation*: 1 counts immediately (sensitive to false positives), 5 only
   validates a person seen over several consecutive frames. Every parameter has
   a tooltip explaining what it does and which value suits this scene; the
   panel's *Afficher l'aide* button shows them all at once. The model
   (*Modèle (fichier .pt)*) is a parameter too — the README explains what the
   shipped `tetes-*.pt` files detect and where to drop new ones.
5. **Run** — the counter updates continuously, the line flashes on every
   crossing. The band and the line cannot be moved once the run starts. The
   progress bar under the video shows the frames done, the current rate and
   the estimated time remaining; **Esc** stops the analysis at any time.
6. **Read the summary** — when the analysis stops, a section appears between
   the status bar and the settings: total, duration, average rate, peak rate,
   a curve of people per minute, and **the settings that produced this total**
   (model, threshold, confirmation, analysis size) — so every trial stays
   traceable to its configuration.
7. **Run it again** — the *Recommencer* button (appears after a first run)
   rewinds the video, resets the counter and starts over — no need to reload
   the video, and the model stays loaded, so it starts immediately.

## Settings that stick

- **Your last-used settings come back at the next launch** — threshold, model,
  confirmation, and the rest. One exception: the drawn line. It belongs to
  each video and is never restored — reloading it on another scene would draw
  an invisible line in the wrong place.
- **Named profiles** save a setup you want to reuse: *Réglages → Profils*,
  type a name, *Enregistrer ce profil*; *Charger ce profil* brings it back.
  Profiles live in `config/profils/` next to the executable. Two
  field-validated profiles ship with the software (*manif-vue-laterale-haute*,
  *manif-vue-plongeante*); a shipped profile is replaced by the one in the
  update archive, so save a personal variant under a **different name** to
  keep it. *Valeurs par défaut* restores the factory settings (the drawn line
  is kept).
- These preferences live in small files next to the executable
  (`config/local_*.json`) — a per-machine preference, never part of the
  project.

## Themes

The interface comes in **four themes**: **navy blue** (the default), **dark**,
**light**, and **follow the system** (reads the Windows theme and follows
it live when it changes). Pick one from the selector at the end of the button
bar; the choice is remembered. Navy blue stays the default on purpose — it is
a dark theme itself, and the counter is designed to be read outdoors, in full
daylight.

## Automatic updates

At startup, the packaged application checks whether a newer release exists. If
one does, a **green button** appears in the button bar; one click:

1. downloads the archive — an interrupted download resumes where it stopped;
2. verifies it against the **SHA-256 published with the release**. If no
   checksum was published, the button only opens the download page:
   installing without verification is refused by design;
3. closes the application, swaps the folder and relaunches the new version.

Settings, named profiles and models you added in `modeles/` are kept. The
previous version stays in a `*.ancienne` folder until the new one has started
successfully — if anything goes wrong, the working installation is still
there. The swap is journaled in
`%LOCALAPPDATA%\CompteurManifestation\journal-mise-a-jour.log`. Available in
the packaged executable only.

## The end-of-analysis summary

The summary reports only what was measured:

- **Total** — people counted in the chosen direction.
- **Average rate** — total over the analysed duration.
- **Peak rate** — the busiest 60 s window, with when it happened. On analyses
  shorter than a minute the window shrinks, and the figure is reported as
  `12 pers / 40 s` rather than extrapolated to a rate that was never measured.

There is **no automatic error rate**. There is no ground truth without manual
annotation, and the software does not invent one. The honest way to know how
far a total is from the truth is to count a segment by hand and compare — the
project ships a command-line tool for exactly that
(`tools/verite_terrain.py`: it extracts a segment as a slow-motion video with
the frame number burned in; you note one frame number per crossing, and it
compares your count against the engine's, tolerance included).

## Reading the green boxes

When a person is counted, their box turns **green** and is **filled**, hiding
the counted head. The green box **follows the person** as they walk away,
and disappears the moment they leave the detection band on the far side of the
line — a clean exit, no lingering frame.

This is not decoration — **it is the only way to see a mistake without ground
truth.** Nobody can recount a demonstration by hand, and the counter will never
say "I missed one": the total is just a number, and a wrong number looks exactly
like a right one. But a person walking across the line *without* their box
turning green is a visible miss. Twenty seconds of watching tells you whether
the count can be trusted, and nothing else on screen tells you that.

So when you check a result, don't only read the total. Watch the line for a
while and count the green boxes yourself. If a head crosses and stays amber, you
have found a miss — and you know roughly how far off the number is.
