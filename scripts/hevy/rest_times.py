"""Rest-timer policy for pushed Hevy routines.

Athlete's rule (2026-08-11): every exercise in a pushed routine carries a rest timer.

    primary lift            → 1:15  (75s), 1:00 in a light week
    secondary / accessory   → 1:00  (60s)
    core / abs              → 0:30  (30s)

Light weeks (2026-10-29): the warm-up week (W1) and the deload. The primaries run well under
their top there, so they drop to the accessory timer.

Resolution order per exercise, most explicit first:

1. an explicit ``rest_seconds`` on the exercise entry (a deliberate one-off — a heavy single
   that genuinely needs longer),
2. its ``tier`` (``primary`` / ``secondary`` / ``accessory`` / ``core``), which the block JSON
   carries so intent is auditable rather than inferred, read against the light-week table when
   the week is light,
3. a name classifier, so an exercise added by hand without a tier still gets a sane timer
   instead of silently pushing with none.

Step 3 is the safety net, not the mechanism. Name matching is exactly the failure mode rule
`exercise-name-mapping` warns about, so new movements should get a ``tier`` in the JSON —
`classify` only stops an omission from reaching the app as a missing timer.
"""
from __future__ import annotations

import re

REST_SECONDS: dict[str, int] = {
    "primary": 75,
    "secondary": 60,
    "accessory": 60,
    "core": 30,
}

# Only the tiers that change in a light week; everything else keeps REST_SECONDS.
LIGHT_WEEK_REST_SECONDS: dict[str, int] = {
    "primary": 60,
}

DEFAULT_TIER = "accessory"

# The Big 5 (CLAUDE.md) under every name the plan/JSON has used for them. Pull-up and dip are
# primaries here, not accessories — that is the whole point of the Big-5 system.
_PRIMARY_NAMES = {
    "low-bar squat", "low bar squat", "squat", "back squat",
    "comp bench", "competition bench", "power bench press", "bench press", "bench",
    "sumo deadlift", "deadlift", "conventional deadlift",
    "weighted pull-up", "weighted pullup", "wpu", "pull up (weighted)",
    "weighted dip", "wdip", "triceps dip (weighted)",
}

# Anti-movement core work. Kept as a name set *plus* a keyword pass below, because core
# movements get renamed more often than they get replaced.
_CORE_NAMES = {
    "side plank", "pallof press", "dead bug", "bird dog", "plank",
    "hanging leg raise", "cable crunch", "ab wheel rollout", "hollow hold",
    "russian twist", "sit-up", "crunch",
}

_CORE_KEYWORDS = re.compile(
    r"\b(plank|pallof|dead ?bug|bird ?dog|crunch|leg raise|ab wheel|hollow|"
    r"russian twist|sit-?up|abs?)\b",
    re.I,
)


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def classify(name: str) -> str:
    """Best-effort tier for an exercise name. Fallback only — prefer an explicit tier."""
    norm = _normalize(name)
    if norm in _CORE_NAMES or _CORE_KEYWORDS.search(norm):
        return "core"
    if norm in _PRIMARY_NAMES:
        return "primary"
    return DEFAULT_TIER


def tier_for(exercise: dict) -> str:
    """The tier an exercise entry resolves to, explicit value winning over the classifier."""
    tier = _normalize(exercise.get("tier") or "")
    if tier in REST_SECONDS:
        return tier
    return classify(exercise.get("name", ""))


def is_light_week(week: int, phase: dict | None = None) -> bool:
    """The warm-up week (W1) or a deload. An explicit ``"light"`` on the block's
    ``week_phases`` entry wins, for a block whose first week isn't a warm-up."""
    phase = phase or {}
    if "light" in phase:
        return bool(phase["light"])
    return week == 1 or "deload" in _normalize(phase.get("label", ""))


def rest_seconds_for(exercise: dict, light_week: bool = False) -> int:
    """Rest timer in seconds for one exercise entry of a block prescription."""
    explicit = exercise.get("rest_seconds")
    if explicit is not None:
        return int(explicit)
    tier = tier_for(exercise)
    if light_week and tier in LIGHT_WEEK_REST_SECONDS:
        return LIGHT_WEEK_REST_SECONDS[tier]
    return REST_SECONDS[tier]


def fmt_rest(seconds: int) -> str:
    """75 → '1:15'. For dry-run output, so the timers are eyeballable before they're pushed."""
    return f"{seconds // 60}:{seconds % 60:02d}"
