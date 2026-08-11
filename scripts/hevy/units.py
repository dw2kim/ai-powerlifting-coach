"""lb ↔ kg conversion that round-trips cleanly through the Hevy app.

Hevy stores every set in **kg** and converts on display. Two things about that broke a push:

1. **Hevy's factor is 2.20462**, not the exact 2.2046226218 this repo uses for reading.
   Evidence from the athlete's own log (`data/logs/sessions/`): a 70 lb weighted pull-up he
   entered himself is stored as `31.75150366049478`, which is `70 / 2.20462` to the last digit.
2. **The block JSON was storing kg rounded to 1 decimal.** 70 lb became `31.8`, and 31.8 kg
   converts back to **70.107 lb** — which is why a pushed routine read "70.11 lb" in the app
   while the Google Sheet said "70".

So: keep full precision, and use *Hevy's* factor. A whole-pound prescription then comes back
out of the app as a whole pound, matching the Sheet exactly.

`normalize_kg` is the defensive half — it re-snaps a load that was already stored lossily
(or hand-edited) onto a real plate increment before it goes over the wire, so a stale 1-decimal
kg value can never resurface as a two-decimal pound in the app.
"""
from __future__ import annotations

# Hevy's own display factor. Do NOT "correct" this to 2.2046226218 — see module docstring.
# The point is to agree with the app, not with NIST.
HEVY_LB_PER_KG = 2.20462

# Real-world loading granularity. Barbell/dumbbell/stack loads land on halves at worst
# (he logs 42.5, 47.5, 52.5), and the kg-rounding noise being repaired here is ≤0.11 lb —
# comfortably inside a 0.5 lb snap, so this fixes the noise without ever moving a real load.
LB_INCREMENT = 0.5


def lb_to_kg(lb: float) -> float:
    """Pounds → the exact kg Hevy would store for that many pounds."""
    return lb / HEVY_LB_PER_KG


def kg_to_lb(kg: float) -> float:
    """Kilograms → the pounds Hevy would display."""
    return kg * HEVY_LB_PER_KG


def snap_lb(lb: float, increment: float = LB_INCREMENT) -> float:
    """Snap a pound value onto a real loading increment, dropping conversion noise."""
    snapped = round(lb / increment) * increment
    return round(snapped, 2)


def normalize_kg(kg: float | None, increment: float = LB_INCREMENT) -> float | None:
    """Round-trip a stored kg value so it displays as a clean pound number in Hevy.

    `None` (a bodyweight/timed set with no load) passes through untouched — it is not the
    same thing as 0 and must not become one.
    """
    if kg is None:
        return None
    if kg == 0:
        return 0.0
    return lb_to_kg(snap_lb(kg_to_lb(kg), increment))


def fmt_lb(kg: float | None) -> str:
    """Display helper: kg → the pound string the athlete should see in the app/Sheet."""
    if kg is None:
        return "—"
    lb = snap_lb(kg_to_lb(kg))
    return f"{lb:g}"
