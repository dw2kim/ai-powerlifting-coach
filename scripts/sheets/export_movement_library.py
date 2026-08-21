"""Render the barbell movement library to a filterable Google Sheet tab.

One row per barbell movement the athlete could ever run — everything he *has* done
(joined live against the Hevy log) plus the standard barbell lifts he *hasn't*, each
tagged with its role and whether it's available for the secondary-rotation slot
(`secondary-rotation` in reference/programming-rules.md). Arms/misc movements are out
of scope by athlete request — the library exists to serve rotation decisions, not
curl selection.

The curated part lives in `data/movement-library.csv` (pattern, role, note). The secondary
pool follows from the pattern — a squat-pattern secondary is a squat secondary — so it is
derived too rather than typed twice. The
rotation verdict is *derived* from role + pool + medical status + what the current block
is running — hand-typing it alongside the role let the two drift, and after one editing
pass 21 of 77 rows contradicted themselves ("Not for me" carrying "Add now"). The role is
the athlete's call; the verdict follows from it. The *factual* part — done or not, set count, first/last exposure — is never
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
# Deliberately narrower than export_block.py's scopes: this script only ever opens an
# existing spreadsheet by key and writes one tab. It never creates a file, so it never
# needs Drive. Anything holding this key can then touch the spreadsheets shared with the
# service account and nothing else in Drive.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADERS = [
    "Pattern", "Movement", "Done", "In Current Block", "Role",
    "Secondary Pool", "Rotation Verdict", "Sets Logged", "First Used", "Last Used", "Note",
]


# Which primary a secondary backs up. A pattern maps to exactly one Big-5 barbell lift, so
# the pool follows from the pattern instead of being a second column to keep in sync.
POOL_BY_PATTERN = {"Squat": "Squat", "Hinge": "Deadlift", "Press": "Bench"}


def pool_for(pattern: str, role: str) -> str:
    """The secondary pool a row belongs to, or an em dash when the row isn't a secondary."""
    return POOL_BY_PATTERN.get(pattern, "—") if role == "Secondary" else "—"


def verdict(role: str, done: bool, active: bool, medical: bool, block: str) -> str:
    """The rotation call, derived so it can never contradict the role beside it."""
    if role == "Primary":
        return "Fixed — never rotates"
    if role == "Injury log":
        return "—"
    if role in ("Not for me", "Retired"):
        return "No"
    if active:
        return f"In use — {block}"
    if medical:
        return "Blocked — medical"
    if not done:
        return "Needs first exposure"
    return "Available now"
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
    """Exercise names prescribed anywhere in the current block, plus its id and short label."""
    block = json.loads(CURRENT_BLOCK.read_text())
    names = {
        ex.get("name")
        for entry in block.get("prescriptions", [])
        for ex in entry.get("exercises", [])
        if ex.get("name")
    }
    block_id = block.get("block_id", "current block")
    # "2026-Q3-B05" -> "B5": the label the athlete actually uses for a block.
    tail = block_id.rsplit("-", 1)[-1]
    short = f"B{int(tail[1:])}" if tail[:1] == "B" and tail[1:].isdigit() else block_id
    return names, block_id, short


def build_grid() -> tuple[list[list[str]], list[dict]]:
    stats = log_stats()
    block_names, block_id, short = current_block_names()

    rows = list(csv.DictReader(LIBRARY_CSV.open(newline="")))
    # A typo in a hevy_name would silently render a real movement as "never done" — the
    # exact error this table exists to avoid. Fail instead.
    unknown = sorted({r["hevy_name"] for r in rows if r["hevy_name"] and r["hevy_name"] not in stats})
    if unknown:
        raise SystemExit(f"hevy_name not found in the log: {unknown}")

    orphans = sorted(r["movement"] for r in rows
                     if r["role"] == "Secondary" and r["pattern"] not in POOL_BY_PATTERN)
    if orphans:
        raise SystemExit(
            f"Secondary rows in a pattern with no Big-5 primary to back up: {orphans}. "
            "Either the pattern is wrong or the role should be Accessory."
        )

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
            pool_for(r["pattern"], r["role"]),
            verdict(r["role"], bool(st), active == "Yes", r["medical_block"] == "yes", short),
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


def pools() -> str:
    """The selectable movements, grouped the way block design consumes them.

    Secondaries are the *complete* legal set for the secondary slot — if it isn't listed,
    it isn't an option. Accessories are only the barbell subset; the real accessory pool
    also holds dumbbell, cable and machine work this table never claimed to cover.
    """
    stats = log_stats()
    block_names, block_id, short = current_block_names()
    rows = list(csv.DictReader(LIBRARY_CSV.open(newline="")))

    def line(r: dict) -> str:
        st = stats.get(r["hevy_name"]) if r["hevy_name"] else None
        active = r["block_alias"] and r["block_alias"] in block_names
        v = verdict(r["role"], bool(st), bool(active), r["medical_block"] == "yes", short)
        return f"    {r['movement']:38s} {v}"

    out = [f"Movement library · block {block_id}", ""]
    out.append("PRIMARIES (never rotate)")
    out += [line(r) for r in rows if r["role"] == "Primary"]
    for pool in ("Squat", "Bench", "Deadlift"):
        out += ["", f"{pool.upper()} SECONDARY POOL — complete; nothing outside it is legal"]
        out += [line(r) for r in rows
                if r["role"] == "Secondary" and pool_for(r["pattern"], r["role"]) == pool]
    out += ["", "BARBELL ACCESSORIES — a subset; DB/cable/machine options live outside this table"]
    out += [line(r) for r in rows if r["role"] == "Accessory"]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the grid, no Google calls")
    ap.add_argument("--csv", metavar="PATH", help="write the grid to a CSV for manual import")
    ap.add_argument("--pools", action="store_true",
                    help="print the selectable movements for block design; no Google calls")
    ap.add_argument("--tab", default=TAB_TITLE, help=f"tab name (default: {TAB_TITLE})")
    args = ap.parse_args()

    if args.pools:
        print(pools())
        return

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
