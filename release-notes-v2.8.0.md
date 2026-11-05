# Compteur de manifestation 2.8.0

Line tracing: readability, faithful detection zone, magnetic snapping.

## Added

- **Magnetic line tracing**: a line drawn within 3° of horizontal or
  vertical snaps exactly straight (second point re-anchored). A freely
  drawn diagonal is left untouched.
- **Visible drop-down arrows**: every list (profiles, models, theme…)
  now shows a drawn arrow — the custom styling used to hide Qt's native
  one, so nothing indicated the list could open.
- **Marine blue is the default theme** for new installations (it is a
  dark theme itself: outdoor readability is preserved).

## Fixed

- **On a tilted line, the detection zone now matches the drawing.** The
  detection crop is an axis-aligned bounding rectangle: on a tilted line
  its corners extended past the real band, and the displayed veil stayed
  straight. Detections outside the oblique band are now discarded AND the
  veil follows the tilt — display and counting describe exactly the same
  zone. No behavior change for a horizontal or vertical line (rectangle
  equals band there), so previous counts are unaffected.

## Changed

- **Bigger counting line** (operator request): direction arrow twice as
  long and thick, placement crosses doubled, thicker line stroke.

**SHA-256**: e4962d693f8a9a99f399dc534c26e65af6a81d45a1918c2759296a171b5809c6
