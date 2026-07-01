"""Render a block JSON spec to a single Google Sheet tab for review.

The athlete reviews the next-block *draft* in a Sheet during the W5 deload, marks it up,
and iterates until happy — then it's finalized into the real block. This script takes the
structured block JSON (`brain/next-block-draft.json` by default) and writes ONE tab:

  - an **Overview** header: goal, peak targets (heaviest programmed set per Big-5 lift),
    the load change vs the current block, and the accessory / structural changes; then
  - the **weekly plan** stacked below (W1…Wn), every day's exercises with the set scheme,
    load (lb, rounded to real plate loads), RPE, and notes. Top vs backoff is in the notes.

Auth: a Google **service account**. Same env-from-.env pattern as the Hevy/Telegram helpers.

  GOOGLE_SA_JSON           the service-account key — EITHER a path to the key file
                           (local, e.g. ~/.gcp/key.json) OR the key's JSON content itself
                           (CI: a GitHub secret has no path). A value starting with '{'
                           is read as inline JSON.

And ONE destination:

  SHEETS_SPREADSHEET_ID    (preferred) id of a spreadsheet you pre-made and shared with the
                           SA as Editor. The SA rewrites the "Draft" tab each run. Works on
                           personal Gmail — a service account has no Drive quota, so it can't
                           *create* files, only edit one it's been shared.
  SHEETS_DRIVE_FOLDER_ID   (Shared Drive / Workspace only) folder to create a new Sheet in.

CLI:
  python -m scripts.sheets.export_block [block.json] [--dry-run]

`--dry-run` prints the grid to stdout and skips all Google calls — no credentials needed.
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
TAB_NAME = "Draft"

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


def _overview_rows(block: dict, prior: dict | None) -> list[list[str]]:
    bid = block.get("block_id", "block")
    summary = block.get("summary") or {}
    prior_id = (prior or {}).get("block_id") if prior else None
    compare = bool(prior) and prior_id and prior_id != bid

    rows: list[list[str]] = [
        [f"{bid} — DRAFT", "PROVISIONAL — review & iterate during W5, then finalize"],
    ]
    if summary.get("goal"):
        rows.append(["Goal", summary["goal"]])
    rows.append(["Structure", f"{block.get('weeks', 5)}-week block · start {block.get('start_date') or 'TBD'}"])
    rows.append([])

    rows.append(["PEAK TARGETS (heaviest programmed)", "load × reps",
                 f"Δ vs {prior_id}" if compare else ""])
    for label, name, is_bw in PRIMARY_PEAKS:
        pk = _peak(block, name)
        if not pk:
            continue
        delta = ""
        if compare:
            pp = _peak(prior, name)
            if pp:
                d = _round5(pk[0] * KG_TO_LBS) - _round5(pp[0] * KG_TO_LBS)
                delta = f"{'+' if d >= 0 else ''}{d} lb"
        rows.append([label, f"{_fmt_load(pk[0], is_bw)} × {pk[1]}", delta])
    rows.append([])

    if summary.get("changes"):
        rows.append([f"CHANGES vs {prior_id or 'prior block'}"])
        rows.extend([["• " + c] for c in summary["changes"]])
        rows.append([])
    if summary.get("accessory_changes"):
        rows.append(["ACCESSORY CHANGES (rotations + 1–2 new)"])
        rows.extend([["• " + c] for c in summary["accessory_changes"]])
        rows.append([])
    if not summary:
        rows.append(["(Goal, block-vs-block changes, and accessory changes are written here "
                     "when the design skill generates the real draft. This preview is rendered "
                     "straight from the block JSON.)"])
        rows.append([])

    rows.append(["═══════════  WEEKLY PLAN  ═══════════"])
    return rows


def _week_rows(block: dict, week: int) -> list[list[str]]:
    rows: list[list[str]] = [[], [f"WEEK {week}"],
                             ["Day", "Exercise", "Set / Notes", "Sets×Reps", "Load (lb)", "RPE"]]
    day_order = [d.get("label") for d in block.get("days", [])]
    prescs = [p for p in block.get("prescriptions", []) if p.get("week") == week]
    prescs.sort(key=lambda p: day_order.index(p["day"]) if p.get("day") in day_order else 99)
    for presc in prescs:
        day = presc.get("day", "")
        first = True
        for ex in presc.get("exercises", []):
            name = ex.get("name", "")
            scheme, load, rpe = _summarize_sets(ex.get("sets", []), _is_bw_lift(name))
            rows.append([day if first else "", name, (ex.get("notes") or "").strip(),
                         scheme, load, rpe])
            first = False
        rows.append([])
    return rows


def build_grid(block: dict, prior: dict | None = None) -> list[list[str]]:
    """The single-tab 2D grid: overview header, then all weeks stacked below it."""
    grid = _overview_rows(block, prior)
    for w in range(1, block.get("weeks", 0) + 1):
        grid.extend(_week_rows(block, w))
    return grid


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
    grid = build_grid(block, _load_prior(block))
    if dry_run:
        _print_dry_run(grid)
        return None

    from dotenv import load_dotenv
    load_dotenv()

    gc = _client()
    sheet_id = os.environ.get("SHEETS_SPREADSHEET_ID")
    folder_id = os.environ.get("SHEETS_DRIVE_FOLDER_ID")

    if sheet_id:
        sh = gc.open_by_key(sheet_id)
        _write_single_tab(sh, grid)
        print(f"Sheet updated: {sh.url}")
    elif folder_id:
        sh = gc.create(title, folder_id=folder_id)
        share_email = os.environ.get("GOOGLE_SHARE_EMAIL")
        if share_email:
            sh.share(share_email, perm_type="user", role="writer")
        _write_single_tab(sh, grid)
        print(f"Sheet created: {sh.url}")
    else:
        raise SystemExit(
            "Set SHEETS_SPREADSHEET_ID (a spreadsheet you pre-made and shared with the "
            "service account) — or SHEETS_DRIVE_FOLDER_ID for a Shared Drive."
        )
    return sh.url


# Stale tabs a prior render (per-week or default) may have left behind.
_STALE_TAB = re.compile(r"^(Overview|W\d+|Sheet\d+)$")


def _write_single_tab(sh, grid: list[list[str]]) -> None:
    """Write the whole draft into one tab, size columns to content, and clean up any
    tabs a previous render left behind. Nothing else the athlete added is touched."""
    import gspread

    try:
        ws = sh.worksheet(TAB_NAME)
        ws.clear()
    except gspread.WorksheetNotFound:
        cols = max((max((len(r) for r in grid), default=1)), 6)
        ws = sh.add_worksheet(title=TAB_NAME, rows=max(len(grid) + 5, 20), cols=cols)
    if grid:
        ws.update(range_name="A1", values=grid)
        ws.freeze(rows=1)
        try:
            ncols = max((len(r) for r in grid), default=6)
            ws.columns_auto_resize(0, ncols - 1)  # size columns to their content
        except Exception:  # noqa: BLE001 — cosmetic; never fail the export over it
            pass

    for other in sh.worksheets():
        if other.title != TAB_NAME and _STALE_TAB.match(other.title) and len(sh.worksheets()) > 1:
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
                    help="Print the grid; no Google calls, no credentials needed.")
    args = ap.parse_args()

    block = json.loads(Path(args.block_json).read_text())
    title = args.title or f"{block.get('block_id', 'block')} DRAFT"
    export(block, title, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
