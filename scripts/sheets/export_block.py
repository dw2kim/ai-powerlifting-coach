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
from pathlib import Path

from ..hevy.block_report import KG_TO_LBS, REPO_ROOT

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
_TITLE_BG = (0.20, 0.25, 0.31)   # dark slate — tab title banner (white text)
_SECTION_BG = (0.87, 0.89, 0.93)  # pale slate — overview section headers
_HEADER_GRAY = (0.85, 0.85, 0.85)  # plan column-header row
_POS_GREEN = (0.71, 0.88, 0.72)   # Δ improvement
_NEG_RED = (0.96, 0.78, 0.76)     # Δ regression

# Weekly-phase colours: calm calibration → hot peak → cool deload.
_WK_COLORS = {
    1: (0.81, 0.91, 0.87),  # Calibration — pale teal
    2: (0.72, 0.85, 0.67),  # Establish   — green
    3: (0.99, 0.85, 0.58),  # Push        — amber
    4: (0.93, 0.60, 0.51),  # Peak        — red
    5: (0.66, 0.79, 0.92),  # Deload      — blue
}
_WK_PHASE = {1: "Calibration", 2: "Establish", 3: "Push", 4: "Peak", 5: "Deload"}

# Lift-family shading in the Plan tab: a lift's primary AND its secondary share one tint so
# the eye groups them (e.g. Low-bar Squat + Paused Low-bar Squat both yellow). Only the three
# barbell lifts get coloured — pull-up, dip, and accessories stay plain. Membership is by
# exercise name; extend each set when a new secondary rotates in (see `accessory-rotation` /
# the secondary-rotation rule). Colours are light so black text stays readable, and distinct
# from the week-phase header bands (which sit on separate rows).
_LIFT_FAMILIES: dict[str, tuple[tuple, set[str]]] = {
    "Squat":    ((1.00, 0.95, 0.70), {"Low-bar Squat", "Paused Low-bar Squat"}),      # pale yellow
    "Bench":    ((0.87, 0.85, 0.96), {"Comp Bench", "CGB"}),                            # pale lavender
    "Deadlift": ((0.99, 0.86, 0.83), {"Sumo Deadlift", "Paused RDL"}),                  # pale coral
}


def _family_bg(name: str) -> tuple | None:
    """Background tint for a squat/bench/deadlift primary-or-secondary; None otherwise."""
    for color, names in _LIFT_FAMILIES.values():
        if name in names:
            return color
    return None


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

def build_overview(block: dict, prior: dict | None) -> tuple[list[list[str]], list[dict]]:
    rows: list[list[str]] = []
    fmts: list[dict] = []
    label = _block_label(block)
    bid = block.get("block_id", "block")
    summary = block.get("summary") or {}
    prior_id = (prior or {}).get("block_id") if prior else None
    compare = bool(prior) and prior_id and prior_id != bid

    def _row() -> int:
        return len(rows) + 1  # 1-based index of the row about to be appended

    r = _row(); rows.append([f"{label} — DRAFT (PROVISIONAL)",
                             "Review & iterate during W5, then finalize"])
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
    return rows, fmts


def build_plan(block: dict) -> tuple[list[list[str]], list[dict]]:
    rows: list[list[str]] = []
    fmts: list[dict] = []
    label = _block_label(block)
    weeks = block.get("weeks", 0)

    def _row() -> int:
        return len(rows) + 1

    r = _row(); rows.append([f"{label} — Weekly Plan (PROVISIONAL)"])
    fmts.append({"range": _a1(r, 1, r, NCOL), "format": _cell_fmt(bg=_TITLE_BG, bold=True, white=True)})

    # Week colour key: one shaded cell per week/phase.
    order = list(range(1, weeks + 1))
    r = _row(); rows.append(["Week colours →"] + [f"W{w} {_WK_PHASE.get(w, '')}".strip() for w in order])
    fmts.append({"range": _a1(r, 1, r, 1), "format": _cell_fmt(bold=True)})
    for i, w in enumerate(order):
        col = 2 + i
        fmts.append({"range": _a1(r, col, r, col), "format": _cell_fmt(bg=_WK_COLORS.get(w), bold=True)})

    # Lift colour key: primary + its secondary share the family tint.
    r = _row(); rows.append(["Lift colours →"] + [f"{lift} + secondary" for lift in _LIFT_FAMILIES])
    fmts.append({"range": _a1(r, 1, r, 1), "format": _cell_fmt(bold=True)})
    for i, (color, _names) in enumerate(_LIFT_FAMILIES.values()):
        col = 2 + i
        fmts.append({"range": _a1(r, col, r, col), "format": _cell_fmt(bg=color, bold=True)})

    rows.append(["Primary lifts in bold. Blank RPE on accessories = assume 7–8."])

    day_order = [d.get("label") for d in block.get("days", [])]
    for w in range(1, weeks + 1):
        rows.append([])
        r = _row(); rows.append([f"WEEK {w} — {_WK_PHASE.get(w, '')}".strip()])
        fmts.append({"range": _a1(r, 1, r, NCOL), "format": _cell_fmt(bg=_WK_COLORS.get(w), bold=True)})
        r = _row(); rows.append(["Day", "Exercise", "Set / Notes", "Sets×Reps", "Load (lb)", "RPE"])
        fmts.append({"range": _a1(r, 1, r, NCOL), "format": _cell_fmt(bg=_HEADER_GRAY, bold=True)})
        prescs = [p for p in block.get("prescriptions", []) if p.get("week") == w]
        prescs.sort(key=lambda p: day_order.index(p["day"]) if p.get("day") in day_order else 99)
        for presc in prescs:
            day = presc.get("day", "")
            first = True
            for ex in presc.get("exercises", []):
                name = ex.get("name", "")
                scheme, load, rpe = _summarize_sets(ex.get("sets", []), _is_bw_lift(name))
                r = _row(); rows.append([day if first else "", name, (ex.get("notes") or "").strip(),
                                         scheme, load, rpe])
                fmt = _cell_fmt(bg=_family_bg(name), bold=name in PRIMARY_NAMES)
                if fmt:  # squat/bench/dl rows get a family tint; primaries also bold
                    fmts.append({"range": _a1(r, 1, r, NCOL), "format": fmt})
                first = False
            rows.append([])
    return rows, fmts


def _print_dry_run(grid: list[list[str]]) -> None:
    for row in grid:
        print(" | ".join(str(c).replace("\n", " / ") for c in row))


def _load_prior(block: dict) -> dict | None:
    """The current block, for block-vs-block deltas — unless we're rendering it itself."""
    if not CURRENT_BLOCK.is_file():
        return None
    prior = json.loads(CURRENT_BLOCK.read_text())
    return None if prior.get("block_id") == block.get("block_id") else prior


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


def export(block: dict, title: str, dry_run: bool = False) -> str | None:
    prior = _load_prior(block)
    label = _block_label(block)
    ov_title, pl_title = f"{label} Overview", f"{label} Plan"
    ov_rows, ov_fmts = build_overview(block, prior)
    pl_rows, pl_fmts = build_plan(block)

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

    _write_tab(sh, ov_title, ov_rows, ov_fmts, freeze_rows=1)
    _write_tab(sh, pl_title, pl_rows, pl_fmts, freeze_rows=0)
    _cleanup_tabs(sh, keep={ov_title, pl_title})
    try:  # Overview first, Plan second — cosmetic.
        sh.reorder_worksheets([sh.worksheet(ov_title), sh.worksheet(pl_title)])
    except Exception:  # noqa: BLE001
        pass
    print(f"Sheet updated: {sh.url}")
    return sh.url


# Old single/per-week tabs a prior render may have left behind (never touches athlete tabs).
_STALE_TAB = re.compile(r"^(Draft|Overview|W\d+|Sheet\d+)$")


def _write_tab(sh, title: str, grid: list[list[str]], fmts: list[dict], freeze_rows: int = 0) -> None:
    """Write one grid into a named tab, apply cell formats, and size columns to content."""
    import gspread

    try:
        ws = sh.worksheet(title)
        ws.clear()
    except gspread.WorksheetNotFound:
        cols = max((max((len(r) for r in grid), default=1)), NCOL)
        ws = sh.add_worksheet(title=title, rows=max(len(grid) + 5, 20), cols=cols)
    if not grid:
        return
    ws.update(range_name="A1", values=grid)
    if freeze_rows:
        try:
            ws.freeze(rows=freeze_rows)
        except Exception:  # noqa: BLE001
            pass
    if fmts:
        try:
            ws.batch_format(fmts)
        except Exception:  # noqa: BLE001 — cosmetic; never fail the export over styling
            pass
    try:
        ncols = max((len(r) for r in grid), default=NCOL)
        ws.columns_auto_resize(0, ncols - 1)  # size columns to their content
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
    args = ap.parse_args()

    block = json.loads(Path(args.block_json).read_text())
    title = args.title or f"{block.get('block_id', 'block')} DRAFT"
    export(block, title, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
