"""Render the barbell movement library to a filterable Google Sheet tab.

One row per barbell movement the athlete could ever run — everything he *has* done
(joined live against the Hevy log) plus the standard barbell lifts he *hasn't*, each
tagged with its role and whether it's available for the secondary-rotation slot
(`secondary-rotation` in reference/programming-rules.md). Arms/misc movements are out
of scope by athlete request — the library exists to serve rotation decisions, not
curl selection.

The curated part lives in `data/movement-library.csv` (pattern, role, pool, verdict,
note). The *factual* part — done or not, set count, first/last exposure — is never
hand-maintained: it is recomputed from `data/logs/workouts.csv` on every run, so the
tab re-renders current instead of drifting. "In current block" comes from
`brain/current-block.json`.

The tab is written with a frozen header and a basic filter across every column, so the
athlete filters it himself: Done = No, Verdict = Available now, Pool = Bench, and so on.

Auth: the same service account as export_block.py (GOOGLE_SA_JSON + SHEETS_SPREADSHEET_ID).
This script only ever touches its own tab — it never deletes or reorders the block tabs.

CLI:
  python -m scripts.sheets.export_movement_library [--dry-run] [--csv PATH] [--tab NAME]

`--dry-run` prints the grid; `--csv` writes it to a file for a manual File > Import.
Neither needs credentials.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_CSV = REPO_ROOT / "data" / "movement-library.csv"
WORKOUTS_CSV = REPO_ROOT / "data" / "logs" / "workouts.csv"
CURRENT_BLOCK = REPO_ROOT / "brain" / "current-block.json"

TAB_TITLE = "Movement Library"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Pattern", "Movement", "Done", "In Current Block", "Role",
    "Secondary Pool", "Rotation Verdict", "Sets Logged", "First Used", "Last Used", "Note",
]
COL_PX = [90, 260, 60, 130, 100, 120, 150, 90, 100, 100, 520]

# Hevy timestamps: "Jan 21, 2023, 1:21 PM".
HEVY_TS = "%b %d, %Y, %I:%M %p"


def _hex(h: str) -> dict:
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


_HEADER_BG = _hex("2c3e50")   # dark slate banner, white text — matches the block tabs
_DONE_BG = _hex("eaf3ea")     # pale green — logged
_NEVER_BG = _hex("f6f0f0")    # pale warm grey — never logged
_ACTIVE_BG = _hex("cfe3cf")   # stronger green — running in the current block
_WHITE = {"red": 1, "green": 1, "blue": 1}


def log_stats() -> dict[str, dict]:
    """Set count and first/last exposure per Hevy exercise title."""
    stats: dict[str, dict] = {}
    with WORKOUTS_CSV.open(newline="") as fh:
        for row in csv.DictReader(fh):
            name = row["exercise_title"]
            st = stats.setdefault(name, {"sets": 0, "first": None, "last": None})
            st["sets"] += 1
            try:
                dt = datetime.strptime(row["start_time"], HEVY_TS)
            except ValueError:
                continue
            if st["first"] is None or dt < st["first"]:
                st["first"] = dt
            if st["last"] is None or dt > st["last"]:
                st["last"] = dt
    return stats


def current_block_names() -> tuple[set[str], str]:
    """Exercise names prescribed anywhere in the current block, plus the block id."""
    block = json.loads(CURRENT_BLOCK.read_text())
    names = {
        ex.get("name")
        for entry in block.get("prescriptions", [])
        for ex in entry.get("exercises", [])
        if ex.get("name")
    }
    return names, block.get("block_id", "current block")


def build_grid() -> tuple[list[list[str]], list[dict]]:
    stats = log_stats()
    block_names, block_id = current_block_names()

    rows = list(csv.DictReader(LIBRARY_CSV.open(newline="")))
    # A typo in a hevy_name would silently render a real movement as "never done" — the
    # exact error this table exists to avoid. Fail instead.
    unknown = sorted({r["hevy_name"] for r in rows if r["hevy_name"] and r["hevy_name"] not in stats})
    if unknown:
        raise SystemExit(f"hevy_name not found in the log: {unknown}")

    grid: list[list[str]] = [HEADERS]
    fmts: list[dict] = []
    for i, r in enumerate(rows, start=2):  # row 1 is the header
        st = stats.get(r["hevy_name"]) if r["hevy_name"] else None
        done = "Yes" if st else "No"
        active = "Yes" if r["block_alias"] and r["block_alias"] in block_names else "No"
        grid.append([
            r["pattern"],
            r["movement"],
            done,
            active,
            r["role"],
            r["pool"] or "—",
            r["verdict"],
            str(st["sets"]) if st else "",
            st["first"].date().isoformat() if st and st["first"] else "",
            st["last"].date().isoformat() if st and st["last"] else "",
            r["note"],
        ])
        bg = _ACTIVE_BG if active == "Yes" else (_DONE_BG if st else _NEVER_BG)
        fmts.append({"range": f"A{i}:K{i}", "format": {"backgroundColor": bg}})

    fmts.insert(0, {"range": "A1:K1", "format": {
        "backgroundColor": _HEADER_BG,
        "textFormat": {"bold": True, "foregroundColor": _WHITE},
    }})
    print(f"{len(rows)} movements · current block: {block_id}")
    return grid, fmts


def _client():
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


def write_tab(grid: list[list[str]], fmts: list[dict], tab: str) -> str:
    from dotenv import load_dotenv
    load_dotenv()

    import gspread

    sheet_id = os.environ.get("SHEETS_SPREADSHEET_ID")
    if not sheet_id:
        raise SystemExit("SHEETS_SPREADSHEET_ID not set — the spreadsheet shared with the service account.")
    sh = _client().open_by_key(sheet_id)

    need_rows, need_cols = len(grid) + 5, len(HEADERS)
    try:
        ws = sh.worksheet(tab)
        ws.clear()
        if ws.row_count < need_rows or ws.col_count < need_cols:
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
        # clear() leaves backgrounds behind; reset before re-tinting.
        ws.format(f"A1:K{ws.row_count}", {"backgroundColor": _WHITE,
                                          "textFormat": {"bold": False}})
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=need_rows, cols=need_cols)

    ws.update(range_name="A1", values=grid)
    ws.batch_format(fmts)

    sid = ws.id
    sh.batch_update({"requests": [
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        # The point of the tab: every column filterable from the header dropdowns.
        {"setBasicFilter": {"filter": {"range": {
            "sheetId": sid, "startRowIndex": 0, "endRowIndex": len(grid),
            "startColumnIndex": 0, "endColumnIndex": len(HEADERS)}}}},
        *[{"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1},
            "properties": {"pixelSize": px}, "fields": "pixelSize"}}
          for c, px in enumerate(COL_PX)],
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 11},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat.wrapStrategy"}},
    ]})
    print(f"Tab '{tab}' updated: {sh.url}")
    return sh.url


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the grid, no Google calls")
    ap.add_argument("--csv", metavar="PATH", help="write the grid to a CSV for manual import")
    ap.add_argument("--tab", default=TAB_TITLE, help=f"tab name (default: {TAB_TITLE})")
    args = ap.parse_args()

    grid, fmts = build_grid()

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            csv.writer(fh).writerows(grid)
        print(f"Wrote {args.csv}")
    if args.dry_run:
        for row in grid:
            print(" | ".join(row[:7]))
    if not args.dry_run and not args.csv:
        write_tab(grid, fmts, args.tab)


if __name__ == "__main__":
    main()
