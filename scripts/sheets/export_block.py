"""Render a block JSON spec to a Google Sheet for review, as two colour-coded tabs.

The athlete reviews the next-block *draft* in a Sheet during the W5 deload, marks it up,
and iterates until happy — then it's finalized into the real block. This script takes the
structured block JSON (`brain/next-block-draft.json` by default) and writes TWO tabs,
named after the block (e.g. "Block 4 Overview" / "Block 4 Plan"):

  - **<Block N> Overview** — goal, peak targets (heaviest programmed set per Big-5 lift),
    the load change vs the current block (Δ column shaded green/red), and the accessory /
    structural changes. Section headers are shaded so the blocks read at a glance.
  - **<Block N> Plan** — the weekly plan (W1…Wn), every day's exercises with the set scheme,
    load (lb, rounded to real plate loads), RPE, and notes. Each week's header is shaded by
    training phase (calibration → peak → deload) with a colour key up top; primary lifts are
    bold. Top vs backoff is in the notes.

Auth: a Google **service account**. Same env-from-.env pattern as the Hevy/Telegram helpers.

  GOOGLE_SA_JSON           the service-account key — EITHER a path to the key file
                           (local, e.g. ~/.gcp/key.json) OR the key's JSON content itself
                           (CI: a GitHub secret has no path). A value starting with '{'
                           is read as inline JSON.

And ONE destination:

  SHEETS_SPREADSHEET_ID    (preferred) id of a spreadsheet you pre-made and shared with the
                           SA as Editor. The SA rewrites the two block tabs each run. Works on
                           personal Gmail — a service account has no Drive quota, so it can't
                           *create* files, only edit one it's been shared.
  SHEETS_DRIVE_FOLDER_ID   (Shared Drive / Workspace only) folder to create a new Sheet in.

CLI:
  python -m scripts.sheets.export_block [block.json] [--dry-run]

`--dry-run` prints both tabs' grids to stdout and skips all Google calls — no credentials needed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from ..hevy.block_report import DEFAULT_BW, KG_TO_LBS, REPO_ROOT, e1rm

DRAFT_JSON = REPO_ROOT / "brain" / "next-block-draft.json"
CURRENT_BLOCK = REPO_ROOT / "brain" / "current-block.json"

# gspread needs both scopes: spreadsheets to write cells, drive to open/create.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Big-5 primaries for the peak-target summary, by the JSON prescription `name`.
PRIMARY_PEAKS = [
    ("Squat", "Low-bar Squat", False),
    ("Bench", "Comp Bench", False),
    ("Sumo", "Sumo Deadlift", False),
    ("Weighted Pull-up", "Weighted Pull-up", True),
    ("Weighted Dip", "Weighted Dip", True),
]
PRIMARY_NAMES = {name for _, name, _ in PRIMARY_PEAKS}

NCOL = 6  # widest row in either tab (Day / Exercise / Notes / Sets×Reps / Load / RPE)

# --- Colour palette (RGB, 0..1) --------------------------------------------------------
def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


_TITLE_BG = _hex("2c3e50")       # dark slate — tab title banner (white text)
_SECTION_BG = (0.87, 0.89, 0.93)  # pale slate — overview section headers
_POS_GREEN = (0.71, 0.88, 0.72)   # Δ improvement
_NEG_RED = (0.96, 0.78, 0.76)     # Δ regression

# Plan-tab bands — matched to the Block 3 sheet so the two read the same.
_WEEK_BG = _hex("1a237e")        # week header band (white text)
_COLHDR_BG = _hex("34495e")      # column-header row (white text)
_DAYBAND_BG = _hex("455a64")     # per-day band (white text)

_WK_PHASE = {1: "CALIBRATION", 2: "BUILD", 3: "PUSH", 4: "OVERREACH", 5: "DELOAD"}
_WK_SUB = {
    1: "Open easy — first working loads of the block.",
    2: "Loads climb. Find working weights.",
    3: "Heavier top sets. Doubles appear.",
    4: "Peak doubles/singles. Manage fatigue.",
    5: "Back off. Recover into the next block.",
}

# Lift-family tint for the Type + Exercise cells (Block-3 palette). Detected by name so a
# rotated-in secondary (Spoto, 3-1-0 Tempo, etc.) inherits its family's colour automatically.
_FAMILY_BG = {
    "Squat": _hex("e8f5e9"),   # light green
    "Bench": _hex("fff3e0"),   # light amber
    "Sumo": _hex("e3f2fd"),    # light blue
    "Pullup": _hex("f3e5f5"),  # light purple
    "Dip": _hex("e0f7fa"),     # light cyan
    "Acc": _hex("f5f5f5"),     # light grey
}


def _family(name: str) -> str:
    """Map an exercise name to its Big-5 family (or 'Acc'). Order matters."""
    n = name.lower()
    if "squat" in n:
        return "Squat"
    if "dip" in n:
        return "Dip"
    if "pull-up" in n or "pullup" in n:
        return "Pullup"
    if "sumo" in n or "deadlift" in n or "rdl" in n:
        return "Sumo"
    if any(k in n for k in ("bench", "spoto", "cgb", "close grip", "larsen")):
        return "Bench"
    return "Acc"


# --- Note shortening (Plan tab) --------------------------------------------------------
# The Sets/Reps/RPE/Load columns already carry the numbers, so the note keeps only the
# qualitative cue: "Top set @7. 435×4." → "Top set". Cap cues ("@8 CAP") are preserved.
_LOADREP_RE = re.compile(r"(?:BW\+)?(\d+)\s*[×x]\s*\d+")
_RPE_RE = re.compile(r"@\d+(?:\.\d+)?(?:\s*[-–]\s*@?\d+(?:\.\d+)?)?")
_CAP_RE = re.compile(r"@(\d+(?:\.\d+)?\s*(?:CAP|cap|Cap))")
_SETS_RE = re.compile(r"\s*[—-]?\s*\d+\s+sets\b\.?")


def _short_note(note: str | None) -> str:
    if not note:
        return ""
    s = note

    def _drop_loadrep(m: re.Match) -> str:
        # Drop weight×rep tokens (435×4, BW+65×4) but keep rep schemes like "3×12".
        return "" if ("BW" in m.group(0) or int(m.group(1)) >= 40) else m.group(0)

    s = _LOADREP_RE.sub(_drop_loadrep, s)
    # Protect "@X CAP" cues, strip the remaining bare RPE targets, then restore the caps.
    s = _CAP_RE.sub(lambda m: "\x00" + m.group(1), s)
    s = _RPE_RE.sub("", s)
    s = s.replace("\x00", "@")
    s = _SETS_RE.sub("", s)          # "— 4 sets" / "4 sets" (the Sets column shows it)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*\.\s*(?=\.)", "", s)   # collapse ". ." → "."
    s = re.sub(r"\s+([.,;])", r"\1", s)
    s = re.sub(r"[—-]\s*(?=[.,]|$)", "", s)
    return s.strip(" .,–—")


def _round5(lbs: float) -> int:
    """Snap to the nearest 5 lb — real barbell/dumbbell loads, not kg-conversion noise."""
    return int(round(lbs / 5.0) * 5)


def _is_bw_lift(name: str) -> bool:
    n = name.lower()
    return "pull-up" in n or "pullup" in n or "dip" in n


def _fmt_load(weight_kg: float | None, is_bw: bool) -> str:
    if weight_kg is None:
        return "—"
    lbs = _round5(weight_kg * KG_TO_LBS)
    return f"BW+{lbs}" if is_bw else f"{lbs}"


def _fmt_rpe(rpe) -> str:
    return f"@{rpe:g}" if rpe is not None else ""


def _summarize_sets(sets: list[dict], is_bw: bool) -> tuple[str, str, str]:
    """Collapse a prescription's sets into (scheme, load, rpe) display strings."""
    working = [s for s in sets if s.get("type") != "warmup"]
    if not working:
        return ("—", "—", "")

    def _reps(s) -> str:
        return "AMRAP" if s.get("reps") in (0, None) else str(s.get("reps"))

    keys = {(s.get("weight_kg"), s.get("reps"), s.get("rpe")) for s in working}
    if len(keys) == 1:
        s = working[0]
        scheme = _reps(s) if _reps(s) == "AMRAP" else f"{len(working)}×{_reps(s)}"
        return (scheme, _fmt_load(s.get("weight_kg"), is_bw), _fmt_rpe(s.get("rpe")))
    schemes, loads, rpes = [], [], []
    for s in working:
        r = _reps(s)
        schemes.append(r if r == "AMRAP" else f"1×{r}")
        loads.append(_fmt_load(s.get("weight_kg"), is_bw))
        rpes.append(_fmt_rpe(s.get("rpe")))
    return ("\n".join(schemes), "\n".join(loads), "\n".join(rpes))


def _peak(block: dict, name: str) -> tuple[float, object] | None:
    """Heaviest programmed working set for a lift across the whole block → (weight_kg, reps)."""
    best = None
    for p in block.get("prescriptions", []):
        for ex in p.get("exercises", []):
            if ex.get("name") != name:
                continue
            for s in ex.get("sets", []):
                if s.get("type") == "warmup":
                    continue
                w = s.get("weight_kg")
                if w is None:
                    continue
                if best is None or w > best[0]:
                    best = (w, s.get("reps"))
    return best


# --- Formatting helpers ----------------------------------------------------------------

def _col_letter(n: int) -> str:
    """1-based column index → spreadsheet letter (1→A, 27→AA)."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _a1(r1: int, c1: int, r2: int, c2: int) -> str:
    return f"{_col_letter(c1)}{r1}:{_col_letter(c2)}{r2}"


def _cell_fmt(bg: tuple | None = None, bold: bool = False, white: bool = False) -> dict:
    """A gspread CellFormat dict for background + text styling."""
    fmt: dict = {}
    if bg:
        fmt["backgroundColor"] = {"red": bg[0], "green": bg[1], "blue": bg[2]}
    text: dict = {}
    if bold:
        text["bold"] = True
    if white:
        text["foregroundColor"] = {"red": 1.0, "green": 1.0, "blue": 1.0}
    if text:
        fmt["textFormat"] = text
    return fmt


def _block_label(block: dict) -> str:
    """'2026-Q3-B04' → 'Block 4'. Falls back to the raw block id."""
    bid = block.get("block_id", "")
    m = re.search(r"B0*(\d+)$", bid)
    return f"Block {int(m.group(1))}" if m else (bid or "Block")


# --- Grid builders (each returns (rows, formats)) --------------------------------------

def build_overview(block: dict, prior: dict | None, final: bool = False) -> tuple[list[list[str]], list[dict], dict]:
    rows: list[list[str]] = []
    fmts: list[dict] = []
    label = _block_label(block)
    bid = block.get("block_id", "block")
    summary = block.get("summary") or {}
    prior_id = (prior or {}).get("block_id") if prior else None
    compare = bool(prior) and prior_id and prior_id != bid

    def _row() -> int:
        return len(rows) + 1  # 1-based index of the row about to be appended

    title = f"{label} — FINAL" if final else f"{label} — DRAFT (PROVISIONAL)"
    subtitle = (f"Active block · start {block.get('start_date') or 'TBD'}" if final
                else "Review & iterate during W5, then finalize")
    r = _row(); rows.append([title, subtitle])
    fmts.append({"range": _a1(r, 1, r, NCOL), "format": _cell_fmt(bg=_TITLE_BG, bold=True, white=True)})

    if summary.get("goal"):
        r = _row(); rows.append(["Goal", summary["goal"]])
        fmts.append({"range": _a1(r, 1, r, 1), "format": _cell_fmt(bold=True)})
    r = _row(); rows.append(["Structure",
                             f"{block.get('weeks', 5)}-week block · start {block.get('start_date') or 'TBD'}"])
    fmts.append({"range": _a1(r, 1, r, 1), "format": _cell_fmt(bold=True)})
    rows.append([])

    r = _row(); rows.append(["PEAK TARGETS (heaviest programmed)", "load × reps",
                             f"Δ vs {prior_id}" if compare else ""])
    fmts.append({"range": _a1(r, 1, r, 3), "format": _cell_fmt(bg=_SECTION_BG, bold=True)})
    for lbl, name, is_bw in PRIMARY_PEAKS:
        pk = _peak(block, name)
        if not pk:
            continue
        delta, dval = "", None
        if compare:
            pp = _peak(prior, name)
            if pp:
                dval = _round5(pk[0] * KG_TO_LBS) - _round5(pp[0] * KG_TO_LBS)
                delta = f"{'+' if dval >= 0 else ''}{dval} lb"
        r = _row(); rows.append([lbl, f"{_fmt_load(pk[0], is_bw)} × {pk[1]}", delta])
        if dval:
            fmts.append({"range": _a1(r, 3, r, 3),
                         "format": _cell_fmt(bg=_POS_GREEN if dval > 0 else _NEG_RED, bold=True)})
    rows.append([])

    if summary.get("changes"):
        r = _row(); rows.append([f"CHANGES vs {prior_id or 'prior block'}"])
        fmts.append({"range": _a1(r, 1, r, NCOL), "format": _cell_fmt(bg=_SECTION_BG, bold=True)})
        rows.extend([["• " + c] for c in summary["changes"]])
        rows.append([])
    if summary.get("accessory_changes"):
        r = _row(); rows.append(["ACCESSORY CHANGES (rotations + 1–2 new)"])
        fmts.append({"range": _a1(r, 1, r, NCOL), "format": _cell_fmt(bg=_SECTION_BG, bold=True)})
        rows.extend([["• " + c] for c in summary["accessory_changes"]])
        rows.append([])
    if not summary:
        rows.append(["(Goal, block-vs-block changes, and accessory changes are written here "
                     "when the design skill generates the real draft. This preview is rendered "
                     "straight from the block JSON.)"])
    # Fixed widths so the long goal/changes text (col A/B) can't balloon and hide the
    # load×reps and Δ columns. The text overflows rightward across the empty cells instead.
    layout = {"col_px": [300, 120, 130, 90, 90, 90], "freeze": (1, 0)}
    return rows, fmts, layout


def _plan_cells(ex: dict) -> tuple[str, str, str, str]:
    """(sets, reps, rpe, load) display strings for one exercise's working sets."""
    working = [s for s in ex.get("sets", []) if s.get("type") != "warmup"]
    if not working:
        return ("", "", "", "")
    is_bw = _is_bw_lift(ex.get("name", ""))

    def _reps(s):
        return "AMRAP" if s.get("reps") in (0, None) else s.get("reps")

    reps = [_reps(s) for s in working]
    if all(r == "AMRAP" for r in reps):
        sets_s, reps_s = "1", "AMRAP"
    elif len({str(r) for r in reps}) == 1:
        sets_s, reps_s = str(len(working)), str(reps[0])
    else:
        sets_s, reps_s = str(len(working)), "/".join(str(r) for r in reps)

    rpes = [s.get("rpe") for s in working if s.get("rpe") is not None]
    if not rpes:
        rpe_s = ""
    elif len(set(rpes)) == 1:
        rpe_s = _fmt_rpe(rpes[0])
    else:
        rpe_s = f"@{min(rpes):g}-{max(rpes):g}"

    if ex.get("display_load"):       # explicit override, e.g. a "485-495" target range
        return (sets_s, reps_s, rpe_s, str(ex["display_load"]))
    weights = [s.get("weight_kg") for s in working if s.get("weight_kg") is not None]
    if not weights:
        load_s = ""
    else:
        lbs = sorted({_round5(w * KG_TO_LBS) for w in weights})
        if lbs == [0]:
            load_s = "BW"          # bodyweight movement (dip, pull-up, hanging leg raise)
        elif len(lbs) == 1:
            load_s = f"BW+{lbs[0]}" if is_bw else f"{lbs[0]}"
        else:
            load_s = (f"BW+{lbs[0]}-{lbs[-1]}" if is_bw else f"{lbs[0]}-{lbs[-1]}")
    return (sets_s, reps_s, rpe_s, load_s)


def _e1rm_cell(ex: dict) -> str:
    """Projected 1RM (Epley, same as block_report) for the heaviest working set — primary
    and secondary lifts only. Blank for accessories and for AMRAP sets (unknown reps)."""
    name = ex.get("name", "")
    if _family(name) == "Acc":
        return ""
    working = [s for s in ex.get("sets", []) if s.get("type") != "warmup"]
    if not working:
        return ""
    top = max(working, key=lambda s: (s.get("weight_kg") or 0))
    reps, w = top.get("reps"), top.get("weight_kg")
    if reps in (0, None) or w is None:
        return ""
    lbs = _round5(w * KG_TO_LBS)
    total = (DEFAULT_BW + lbs) if _is_bw_lift(name) else lbs   # BW lifts add bodyweight
    return str(int(round(e1rm(total, reps))))


def _role_suffix(note: str | None) -> str:
    """Distinguish the top set / backoff / AMRAP entries of the same lift, Block-3 style.

    Matched on whole words: a plain `"top" in note` also fires on **"stop"**, which mislabelled
    every accessory whose cue said "stop above the pinch" / "stop on any painful arc" as a
    top set on the athlete's Sheet.
    """
    nl = (note or "").lower()
    if re.search(r"\bamrap\b", nl):
        return " (AMRAP)"
    if re.search(r"\bback-?off\b", nl):
        return " (backoff)"
    if re.search(r"\btop\b", nl):
        return " (top set)"
    return ""


def _keyed(exs: list) -> dict:
    """(name, occurrence-within-day) -> exercise, so a lift's top/backoff stay distinct."""
    seen: dict[str, int] = {}
    out: dict[tuple, dict] = {}
    for ex in exs:
        nm = ex.get("name", "")
        occ = seen.get(nm, 0)
        seen[nm] = occ + 1
        out[(nm, occ)] = ex
    return out


def build_plan(block: dict, final: bool = False) -> tuple[list[list[str]], list[dict], dict]:
    """Horizontal weekly plan — weeks run across the columns (matches the Block-3 sheet):
    3 fixed left columns (Day · Type · Exercise), then one block of Sets/Reps/RPE/Load/Notes
    per week. Whole exercise rows are tinted by lift family; each training day gets a band.
    The left three columns are frozen so the exercise names stay put when scrolling weeks."""
    rows: list[list[str]] = []
    fmts: list[dict] = []
    banner_rows: list[int] = []       # rows that should overflow (not wrap) their long text
    label = _block_label(block)
    weeks = block.get("weeks", 0)
    order = list(range(1, weeks + 1))

    NLEFT = 3                         # Day · Type · Exercise
    WK_HDRS = ["Sets", "Reps", "RPE", "Load", "e1RM", "Notes"]
    WK_W = len(WK_HDRS)
    SPACER = 1                        # blank column between week blocks
    total = NLEFT + weeks * WK_W + max(weeks - 1, 0) * SPACER

    def wk_start(w: int) -> int:      # 1-based first column of week w's block
        return NLEFT + (w - 1) * (WK_W + SPACER) + 1

    # Fixed column widths (px) — no auto-resize, so long banner/goal text can't balloon a column.
    # Also collect the collapsible per-week column groups and the between-week divider columns.
    col_px = [46, 66, 205]            # Day · Type · Exercise
    group_cols: list[tuple[int, int]] = []   # (start0, end0) per week — native collapse group
    divider_cols: list[int] = []             # 0-based Notes col of each non-final week
    for w in order:
        col_px += [46, 48, 54, 74, 58, 210]  # Sets · Reps · RPE · Load · e1RM · Notes
        s0 = wk_start(w) - 1
        group_cols.append((s0, s0 + WK_W))
        if w != order[-1]:
            col_px.append(26)                # spacer between weeks
            divider_cols.append(s0 + WK_W - 1)

    # Week start dates from the block start (each training week is a calendar week).
    try:
        start_dt = datetime.strptime(block.get("start_date", ""), "%Y-%m-%d")
    except (ValueError, TypeError):
        start_dt = None

    def wk_date(w: int) -> str:
        if not start_dt:
            return ""
        d = start_dt + timedelta(days=7 * (w - 1))
        return f"{d:%a %b} {d.day}"    # e.g. "Mon Jul 6"

    def blank_row() -> list[str]:
        return [""] * total

    def _row() -> int:
        return len(rows) + 1

    # Title banner
    r = _row(); banner_rows.append(r); row = blank_row()
    row[0] = f"{label} — Weekly Plan" if final else f"{label} — Weekly Plan (PROVISIONAL)"
    rows.append(row)
    fmts.append({"range": _a1(r, 1, r, total), "format": _cell_fmt(bg=_TITLE_BG, bold=True, white=True)})

    # Week header band (phase + start date) + one-line phase subtitle
    r = _row(); banner_rows.append(r); row = blank_row()
    for w in order:
        date = wk_date(w)
        head = f"WEEK {w} — {_WK_PHASE.get(w, '')}".strip()
        row[wk_start(w) - 1] = f"{head}  ·  {date}" if date else head
    rows.append(row)
    for w in order:
        c0 = wk_start(w)
        fmts.append({"range": _a1(r, c0, r, c0 + WK_W - 1),
                     "format": _cell_fmt(bg=_WEEK_BG, bold=True, white=True)})
    r = _row(); banner_rows.append(r); row = blank_row()
    for w in order:
        row[wk_start(w) - 1] = _WK_SUB.get(w, "")
    rows.append(row)

    # Column-header row
    r = _row(); row = blank_row()
    row[0], row[1], row[2] = "Day", "Type", "Exercise"
    for w in order:
        c0 = wk_start(w) - 1
        for j, h in enumerate(WK_HDRS):
            row[c0 + j] = h
    rows.append(row)
    fmts.append({"range": _a1(r, 1, r, total), "format": _cell_fmt(bg=_COLHDR_BG, bold=True, white=True)})

    day_order = [d.get("label") for d in block.get("days", [])]
    day_focus = {d.get("label"): d.get("focus", "") for d in block.get("days", [])}
    by_wd: dict[tuple, list] = {}
    for p in block.get("prescriptions", []):
        by_wd.setdefault((p.get("week"), p.get("day")), []).extend(p.get("exercises", []))

    for day in day_order:
        weeks_exs = [(w, by_wd.get((w, day), [])) for w in order]
        _, canon_exs = max(weeks_exs, key=lambda t: len(t[1]))  # fullest week sets the row order
        if not canon_exs:
            continue
        canon_order = list(_keyed(canon_exs).keys())
        per_week = {w: _keyed(exs) for w, exs in weeks_exs}

        # Day band — full-width coloured row; "Dn · focus" overflows across the frozen cols.
        r = _row(); banner_rows.append(r); row = blank_row()
        row[0] = f"{day} · {day_focus.get(day, '')}".rstrip(" ·")
        rows.append(row)
        fmts.append({"range": _a1(r, 1, r, total), "format": _cell_fmt(bg=_DAYBAND_BG, bold=True, white=True)})

        for key in canon_order:
            name = key[0]
            fam = _family(name)
            ref = next((per_week[w][key] for w in order if key in per_week.get(w, {})), None)
            r = _row(); row = blank_row()
            row[1] = fam
            row[2] = f"{name}{_role_suffix((ref or {}).get('notes'))}"
            for w in order:
                ex = per_week.get(w, {}).get(key)
                if not ex:
                    continue
                sets_s, reps_s, rpe_s, load_s = _plan_cells(ex)
                c0 = wk_start(w) - 1
                (row[c0], row[c0 + 1], row[c0 + 2], row[c0 + 3], row[c0 + 4], row[c0 + 5]) = (
                    sets_s, reps_s, rpe_s, load_s, _e1rm_cell(ex), _short_note(ex.get("notes")))
            rows.append(row)
            # Tint the whole row by family so it reads as one exercise across all the weeks.
            fmts.append({"range": _a1(r, 1, r, total), "format": _cell_fmt(bg=_FAMILY_BG[fam])})
            if name in PRIMARY_NAMES:  # keep the primary lift's name bold
                fmts.append({"range": _a1(r, 3, r, 3),
                             "format": _cell_fmt(bg=_FAMILY_BG[fam], bold=True)})
        rows.append(blank_row())

    layout = {"col_px": col_px, "freeze": (4, 3), "wrap_all": True, "overflow_rows": banner_rows,
              "divider_cols": divider_cols, "group_cols": group_cols}
    return rows, fmts, layout


def _print_dry_run(grid: list[list[str]]) -> None:
    for row in grid:
        print(" | ".join(str(c).replace("\n", " / ") for c in row))


BLOCK_ARCHIVE = REPO_ROOT / "data" / "block-archive"


def _load_prior(block: dict) -> dict | None:
    """The block to diff against for block-vs-block deltas. Normally the current block; but
    once this block *is* the current block (finalized), fall back to the newest archived
    block JSON so the Δ column still reads against the real prior block."""
    bid = block.get("block_id")
    if CURRENT_BLOCK.is_file():
        prior = json.loads(CURRENT_BLOCK.read_text())
        if prior.get("block_id") != bid:
            return prior
    if BLOCK_ARCHIVE.is_dir():
        cands = []
        for p in BLOCK_ARCHIVE.glob("*.json"):
            try:
                c = json.loads(p.read_text())
            except Exception:  # noqa: BLE001
                continue
            if c.get("block_id") and c.get("block_id") != bid:
                cands.append(c)
        if cands:
            return max(cands, key=lambda c: c["block_id"])  # newest by block id
    return None


def _client():
    """Authorize gspread from the service-account key. Imported lazily so --dry-run works
    without the Google libraries installed."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit("Missing Google deps. Install with: pip install gspread google-auth") from exc
    raw = os.environ.get("GOOGLE_SA_JSON")
    if not raw:
        raise SystemExit(
            "GOOGLE_SA_JSON not set — set it to the service-account key file path "
            "(local) or the key JSON itself (CI secret)."
        )
    if raw.lstrip().startswith("{"):
        creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    else:
        if not Path(raw).is_file():
            raise SystemExit(f"GOOGLE_SA_JSON points at a missing file: {raw}")
        creds = Credentials.from_service_account_file(raw, scopes=SCOPES)
    return gspread.authorize(creds)


def export(block: dict, title: str, dry_run: bool = False, final: bool = False) -> str | None:
    prior = _load_prior(block)
    label = _block_label(block)
    ov_title, pl_title = f"{label} Overview", f"{label} Plan"
    ov_rows, ov_fmts, ov_layout = build_overview(block, prior, final=final)
    pl_rows, pl_fmts, pl_layout = build_plan(block, final=final)

    if dry_run:
        print(f"═════ TAB: {ov_title} ═════")
        _print_dry_run(ov_rows)
        print(f"\n═════ TAB: {pl_title} ═════")
        _print_dry_run(pl_rows)
        return None

    from dotenv import load_dotenv
    load_dotenv()

    gc = _client()
    sheet_id = os.environ.get("SHEETS_SPREADSHEET_ID")
    folder_id = os.environ.get("SHEETS_DRIVE_FOLDER_ID")

    if sheet_id:
        sh = gc.open_by_key(sheet_id)
    elif folder_id:
        sh = gc.create(title, folder_id=folder_id)
        share_email = os.environ.get("GOOGLE_SHARE_EMAIL")
        if share_email:
            sh.share(share_email, perm_type="user", role="writer")
    else:
        raise SystemExit(
            "Set SHEETS_SPREADSHEET_ID (a spreadsheet you pre-made and shared with the "
            "service account) — or SHEETS_DRIVE_FOLDER_ID for a Shared Drive."
        )

    _write_tab(sh, ov_title, ov_rows, ov_fmts, ov_layout)
    _write_tab(sh, pl_title, pl_rows, pl_fmts, pl_layout)
    _cleanup_tabs(sh, keep={ov_title, pl_title})
    try:  # Overview first, Plan second — cosmetic.
        sh.reorder_worksheets([sh.worksheet(ov_title), sh.worksheet(pl_title)])
    except Exception:  # noqa: BLE001
        pass
    print(f"Sheet updated: {sh.url}")
    return sh.url


# Old single/per-week tabs a prior render may have left behind (never touches athlete tabs).
_STALE_TAB = re.compile(r"^(Draft|Overview|W\d+|Sheet\d+)$")


def _write_tab(sh, title: str, grid: list[list[str]], fmts: list[dict], layout: dict | None = None) -> None:
    """Write one grid into a named tab, apply cell formats, then apply the layout
    (fixed column widths, frozen panes, wrap/overflow)."""
    import gspread

    need_rows = max(len(grid) + 5, 20)
    need_cols = max((max((len(r) for r in grid), default=1)), NCOL)
    try:
        ws = sh.worksheet(title)
        ws.clear()
        # Grow the sheet to fit — the horizontal Plan tab is far wider than the old layout,
        # and ws.update would fail if the grid exceeds the existing column count.
        if ws.row_count < need_rows or ws.col_count < need_cols:
            try:
                ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
            except Exception:  # noqa: BLE001
                pass
        # clear() wipes values but NOT cell backgrounds — reset the whole grid to a clean
        # default first, or stale colours from a prior (differently-shaped) render bleed through.
        try:
            ws.format(f"A1:{_col_letter(ws.col_count)}{ws.row_count}", {
                "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                "textFormat": {"bold": False,
                               "foregroundColor": {"red": 0, "green": 0, "blue": 0}},
            })
        except Exception:  # noqa: BLE001
            pass
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=need_rows, cols=need_cols)
    if not grid:
        return
    ws.update(range_name="A1", values=grid)
    if fmts:
        try:
            ws.batch_format(fmts)
        except Exception:  # noqa: BLE001 — cosmetic; never fail the export over styling
            pass
    _apply_layout(sh, ws, layout or {})


def _apply_layout(sh, ws, layout: dict) -> None:
    """Fixed column widths, frozen panes, wrap/overflow, week dividers, and collapsible
    per-week column groups via one Sheets batchUpdate. All cosmetic — never fail over it."""
    sid = ws.id
    reqs: list[dict] = []

    # Clear any existing column groups first so re-runs don't nest them ever deeper.
    if layout.get("group_cols"):
        try:
            meta = sh.fetch_sheet_metadata(
                {"fields": "sheets(properties(sheetId),columnGroups(range(startIndex,endIndex)))"})
            for s in meta.get("sheets", []):
                if s.get("properties", {}).get("sheetId") != sid:
                    continue
                for g in s.get("columnGroups", []):
                    rng = g.get("range", {})
                    reqs.append({"deleteDimensionGroup": {"range": {
                        "sheetId": sid, "dimension": "COLUMNS",
                        "startIndex": rng.get("startIndex"), "endIndex": rng.get("endIndex")}}})
        except Exception:  # noqa: BLE001
            pass

    for i, px in enumerate(layout.get("col_px", [])):
        if not px:
            continue
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": px}, "fields": "pixelSize"}})

    nrows = ws.row_count
    for c in layout.get("divider_cols", []):  # solid line between adjacent weeks
        reqs.append({"updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": nrows,
                      "startColumnIndex": c, "endColumnIndex": c + 1},
            "right": {"style": "SOLID_MEDIUM", "color": {"red": 0.4, "green": 0.4, "blue": 0.4}}}})

    for s0, e0 in layout.get("group_cols", []):  # collapsible week (native +/- toggle)
        reqs.append({"addDimensionGroup": {"range": {
            "sheetId": sid, "dimension": "COLUMNS", "startIndex": s0, "endIndex": e0}}})
    if layout.get("wrap_all"):  # wrap everything first…
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat.wrapStrategy"}})
    for rr in layout.get("overflow_rows", []):  # …then let banner rows overflow instead
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": rr - 1, "endRowIndex": rr},
            "cell": {"userEnteredFormat": {"wrapStrategy": "OVERFLOW_CELL"}},
            "fields": "userEnteredFormat.wrapStrategy"}})
    fr = layout.get("freeze")
    if fr:
        reqs.append({"updateSheetProperties": {
            "properties": {"sheetId": sid,
                           "gridProperties": {"frozenRowCount": fr[0], "frozenColumnCount": fr[1]}},
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}})
    if reqs:
        try:
            sh.batch_update({"requests": reqs})
        except Exception:  # noqa: BLE001
            pass


def _cleanup_tabs(sh, keep: set[str]) -> None:
    """Remove tabs a previous render left behind. Only deletes recognised render tabs —
    anything the athlete added by hand is left alone."""
    for other in sh.worksheets():
        if other.title in keep:
            continue
        if _STALE_TAB.match(other.title) and len(sh.worksheets()) > 1:
            try:
                sh.del_worksheet(other)
            except Exception:  # noqa: BLE001
                pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("block_json", nargs="?", default=str(DRAFT_JSON),
                    help="Block JSON to render (default: brain/next-block-draft.json)")
    ap.add_argument("--title", help="Sheet title (create mode only; ignored for a pre-made sheet)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print both tabs' grids; no Google calls, no credentials needed.")
    ap.add_argument("--final", action="store_true",
                    help="Render as a finalized block: clean headers, no DRAFT/PROVISIONAL banners.")
    args = ap.parse_args()

    block = json.loads(Path(args.block_json).read_text())
    suffix = "" if args.final else " DRAFT"
    title = args.title or f"{block.get('block_id', 'block')}{suffix}"
    export(block, title, dry_run=args.dry_run, final=args.final)


if __name__ == "__main__":
    main()
