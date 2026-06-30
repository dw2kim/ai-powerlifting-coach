"""Render a block JSON spec to a Google Sheet, matching the B1–B3 layout.

The athlete reviews the next-block *draft* in a Sheet during the W5 deload (same medium
the blocks were always authored in). This script takes the structured block JSON
(`brain/next-block-draft.json` by default, but works on any block JSON of the same
schema) and writes a fresh Google Sheet:

  - **Overview** tab — block id, dates, weeks, and the day split.
  - **W1 … Wn** tabs — one per week, every day's exercises with the set scheme,
    load (lb), RPE, and notes. Top vs backoff is distinguished by the exercise `notes`.

Auth: a Google **service account**. Same env-from-.env pattern as the Hevy/Telegram
helpers. Required:

  GOOGLE_SA_JSON           the service-account key — EITHER a path to the key file
                           (local, e.g. ~/.gcp/key.json) OR the key's JSON content
                           itself (CI: a GitHub secret has no filesystem path). A
                           value starting with '{' is read as inline JSON.

And ONE destination:

  SHEETS_SPREADSHEET_ID    (preferred) id of a spreadsheet you pre-made and shared with
                           the SA as Editor. The SA rewrites its tabs each draft. Works
                           on personal Gmail — a service account has no Drive quota, so
                           it cannot *create* files, only edit one it's been shared.
  SHEETS_DRIVE_FOLDER_ID   (Shared Drive / Workspace only) folder to create a new Sheet
                           in. Optional GOOGLE_SHARE_EMAIL grants you writer access.

Optional:

  GOOGLE_SHARE_EMAIL       email to grant writer access (so the athlete can open it)

CLI:
  python -m scripts.sheets.export_block [block.json] [--title "..."] [--dry-run]

`--dry-run` prints the tab-by-tab grid to stdout and skips all Google calls — use it to
eyeball the layout (and to diff against the live B3 sheet during calibration) without
credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ..hevy.block_report import KG_TO_LBS, REPO_ROOT

DRAFT_JSON = REPO_ROOT / "brain" / "next-block-draft.json"

# gspread needs both scopes: spreadsheets to write cells, drive to create in a folder.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _is_bw_lift(name: str) -> bool:
    """BW-anchored primaries store *added* weight; show them as BW+N."""
    n = name.lower()
    return "pull-up" in n or "pullup" in n or "dip" in n


def _fmt_load(weight_kg: float | None, is_bw: bool) -> str:
    if weight_kg is None:
        return "—"
    lbs = round(weight_kg * KG_TO_LBS)
    return f"BW+{lbs}" if is_bw else f"{lbs}"


def _fmt_rpe(rpe) -> str:
    if rpe is None:
        return ""
    return f"@{rpe:g}"


def _summarize_sets(sets: list[dict], is_bw: bool) -> tuple[str, str, str]:
    """Collapse a prescription's sets into (scheme, load, rpe) display strings.

    Identical sets fold into "N×reps" at a single load/RPE (the common backoff case).
    A varying ramp (e.g. warm-up cluster) is listed set-by-set instead."""
    working = [s for s in sets if s.get("type") != "warmup"]
    if not working:
        return ("—", "—", "")
    def _reps(s) -> str:
        # reps==0 is the convention for a bodyweight AMRAP set.
        return "AMRAP" if s.get("reps") in (0, None) else str(s.get("reps"))

    keys = {(s.get("weight_kg"), s.get("reps"), s.get("rpe")) for s in working}
    if len(keys) == 1:
        s = working[0]
        scheme = _reps(s) if _reps(s) == "AMRAP" else f"{len(working)}×{_reps(s)}"
        return (scheme, _fmt_load(s.get("weight_kg"), is_bw), _fmt_rpe(s.get("rpe")))
    # Mixed sets — render each on its own line within the cells.
    schemes, loads, rpes = [], [], []
    for s in working:
        r = _reps(s)
        schemes.append(r if r == "AMRAP" else f"1×{r}")
        loads.append(_fmt_load(s.get("weight_kg"), is_bw))
        rpes.append(_fmt_rpe(s.get("rpe")))
    return ("\n".join(schemes), "\n".join(loads), "\n".join(rpes))


def _overview_grid(block: dict) -> list[list[str]]:
    rows = [
        ["Block", block.get("block_id", "")],
        ["Weeks", str(block.get("weeks", ""))],
        ["Start date", block.get("start_date", "")],
        [],
        ["Day", "Weekday", "Focus"],
    ]
    for d in block.get("days", []):
        rows.append([d.get("label", ""), d.get("weekday", ""), d.get("focus", "")])
    return rows


def _week_grid(block: dict, week: int) -> list[list[str]]:
    header = ["Day", "Exercise", "Set / Notes", "Sets×Reps", "Load (lb)", "RPE"]
    rows = [header]
    # Day order from the block's declared split, falling back to label sort.
    day_order = [d.get("label") for d in block.get("days", [])]
    prescs = [p for p in block.get("prescriptions", []) if p.get("week") == week]
    prescs.sort(key=lambda p: day_order.index(p["day"]) if p.get("day") in day_order else 99)
    for presc in prescs:
        day = presc.get("day", "")
        first = True
        for ex in presc.get("exercises", []):
            name = ex.get("name", "")
            is_bw = _is_bw_lift(name)
            scheme, load, rpe = _summarize_sets(ex.get("sets", []), is_bw)
            rows.append([
                day if first else "",
                name,
                (ex.get("notes") or "").strip(),
                scheme, load, rpe,
            ])
            first = False
        rows.append([])  # blank spacer between days
    return rows


def build_grids(block: dict) -> dict[str, list[list[str]]]:
    """Tab name → 2D grid. Drives both the dry-run print and the Sheet write."""
    grids = {"Overview": _overview_grid(block)}
    for w in range(1, block.get("weeks", 0) + 1):
        grids[f"W{w}"] = _week_grid(block, w)
    return grids


def _print_dry_run(grids: dict[str, list[list[str]]]) -> None:
    for tab, grid in grids.items():
        print(f"\n===== {tab} =====")
        for row in grid:
            print(" | ".join(str(c).replace("\n", " / ") for c in row))


def _client():
    """Authorize gspread from the service-account key. Imported lazily so --dry-run
    and --help work without the Google libraries installed."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:  # noqa: BLE001
        raise SystemExit(
            "Missing Google deps. Install with: pip install gspread google-auth"
        ) from exc
    raw = os.environ.get("GOOGLE_SA_JSON")
    if not raw:
        raise SystemExit(
            "GOOGLE_SA_JSON not set — set it to the service-account key file path "
            "(local) or the key JSON itself (CI secret)."
        )
    # Accept either a path to the key file (local: runs on your Mac) or the key's
    # JSON content directly (CI: a GitHub secret has no filesystem path). A value
    # starting with '{' is treated as inline JSON; anything else as a file path.
    if raw.lstrip().startswith("{"):
        creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    else:
        if not Path(raw).is_file():
            raise SystemExit(f"GOOGLE_SA_JSON points at a missing file: {raw}")
        creds = Credentials.from_service_account_file(raw, scopes=SCOPES)
    return gspread.authorize(creds)


def export(block: dict, title: str, dry_run: bool = False) -> str | None:
    grids = build_grids(block)
    if dry_run:
        _print_dry_run(grids)
        return None

    # Load .env before reading ANY of the Google env vars (sheet/folder id, share
    # email, and the SA key in _client) so a local .env is honored.
    from dotenv import load_dotenv
    load_dotenv()

    gc = _client()
    sheet_id = os.environ.get("SHEETS_SPREADSHEET_ID")
    folder_id = os.environ.get("SHEETS_DRIVE_FOLDER_ID")

    if sheet_id:
        # Preferred path: write into a spreadsheet the athlete pre-made and shared
        # with the service account (Editor). A service account has no Drive quota,
        # so it can't *create* files — but it can *edit* one it doesn't own.
        sh = gc.open_by_key(sheet_id)
        _write_tabs(gc, sh, grids)
        print(f"Sheet updated: {sh.url}")
    elif folder_id:
        # Fallback for Shared Drives (Workspace): the SA *can* create there.
        sh = gc.create(title, folder_id=folder_id)
        share_email = os.environ.get("GOOGLE_SHARE_EMAIL")
        if share_email:
            sh.share(share_email, perm_type="user", role="writer")
        _write_tabs(gc, sh, grids)
        print(f"Sheet created: {sh.url}")
    else:
        raise SystemExit(
            "Set SHEETS_SPREADSHEET_ID (a spreadsheet you pre-made and shared with the "
            "service account) — or SHEETS_DRIVE_FOLDER_ID for a Shared Drive."
        )
    return sh.url


def _write_tabs(gc, sh, grids: dict[str, list[list[str]]]) -> None:
    """Upsert each tab into the spreadsheet: clear-and-rewrite if it exists, else add.
    Nothing the athlete added is removed except the default empty 'Sheet1' placeholder."""
    import gspread  # already importable — _client ran first

    target = set(grids)
    for tab, grid in grids.items():
        try:
            ws = sh.worksheet(tab)
            ws.clear()
        except gspread.WorksheetNotFound:
            rows = max(len(grid) + 2, 10)
            cols = max((max((len(r) for r in grid), default=1)), 6)
            ws = sh.add_worksheet(title=tab, rows=rows, cols=cols)
        if grid:
            ws.update(range_name="A1", values=grid)
            ws.freeze(rows=1)
    # Drop the default placeholder a fresh spreadsheet ships with, once real tabs exist.
    for ws in sh.worksheets():
        if ws.title == "Sheet1" and ws.title not in target and len(sh.worksheets()) > 1:
            try:
                sh.del_worksheet(ws)
            except Exception:  # noqa: BLE001
                pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("block_json", nargs="?", default=str(DRAFT_JSON),
                    help="Block JSON to render (default: brain/next-block-draft.json)")
    ap.add_argument("--title", help="Sheet title (default: '<block_id> DRAFT')")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the grids; no Google calls, no credentials needed.")
    args = ap.parse_args()

    block = json.loads(Path(args.block_json).read_text())
    title = args.title or f"{block.get('block_id', 'block')} DRAFT"
    export(block, title, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
