"""End-of-W4 next-block draft — the deterministic bookends around the design skill.

The block-drafting *intelligence* runs as a scheduled Claude Code routine that invokes
the `designing-training-block` skill in draft mode (it writes
`brain/next-block-draft.{md,json}`). This module owns the two deterministic halves the
routine leans on:

  check   — Is today the W4 Sunday of the running block? (the one before the W5 deload).
            Optionally syncs the Hevy log so the draft is built on fresh actuals.
            Exit 0 = proceed, 3 = skip. The routine branches on the exit code.

  notify  — After the routine has written the draft files: render them to a Google Sheet
            (scripts.sheets.export_block), push a Telegram heads-up with the Sheet URL,
            and commit the draft to a `draft/next-block` branch (never master).

Routine flow:
  1. python -m scripts.review.draft_next_block check     # stop if it exits 3
  2. python -m scripts.hevy.sync_archive                 # (or `check --sync`)
  3. <run designing-training-block, draft mode>          # Claude writes the draft files
  4. python -m scripts.review.draft_next_block notify

Flags mirror weekly_review.py: --force (bypass guard), --date (override today),
--skip-sync, --no-commit, --dry-run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date as date_cls, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..hevy.block_report import REPO_ROOT
from ..notifications import telegram
from ..sheets.export_block import KG_TO_LBS, export
from .weekly_metrics import geometry

TZ = ZoneInfo("America/Toronto")
DRAFT_JSON = REPO_ROOT / "brain" / "next-block-draft.json"
DRAFT_MD = REPO_ROOT / "brain" / "next-block-draft.md"
CURRENT_BLOCK = REPO_ROOT / "brain" / "current-block.json"
DRAFT_BRANCH = "draft/next-block"

SUNDAY = 6  # date.weekday(): Mon=0 … Sun=6
SKIP_EXIT = 3

# Primaries to surface in the Telegram glance, with the JSON prescription name.
GLANCE_LIFTS = ["Low-bar Squat", "Comp Bench", "Sumo Deadlift", "Weighted Pull-up", "Weighted Dip"]


def _today(date_arg: str | None) -> date_cls:
    if date_arg:
        return date_cls.fromisoformat(date_arg)
    return datetime.now(TZ).date()


def _target_week(block: dict) -> int:
    """The week we draft at the end of: the penultimate week (before the deload).
    For a standard 5-week block that's W4."""
    return max(1, block.get("weeks", 5) - 1)


def evaluate_guard(today: date_cls, force: bool) -> tuple[bool, dict]:
    """(proceed, geometry). Proceed when today is the Sunday of the block's penultimate
    week — the W4 Sunday for a 5-week block — or when forced."""
    block = json.loads(CURRENT_BLOCK.read_text())
    geo = geometry(block, today)
    target = _target_week(block)
    proceed = force or (today.weekday() == SUNDAY and geo["week_no"] == target)
    geo["target_week"] = target
    geo["is_sunday"] = today.weekday() == SUNDAY
    return proceed, geo


def _top_set(block: dict, week: int, name: str) -> dict | None:
    """First (top) set of a lift in a given week, for the Telegram glance."""
    for presc in block.get("prescriptions", []):
        if presc.get("week") != week:
            continue
        for ex in presc.get("exercises", []):
            if ex.get("name") == name and ex.get("sets"):
                return ex["sets"][0]
    return None


def _glance(block: dict) -> str:
    """A compact W1→peak top-set summary of the drafted primaries."""
    weeks = block.get("weeks", 5)
    peak = max(1, weeks - 1)
    lines = []
    for name in GLANCE_LIFTS:
        w1, wp = _top_set(block, 1, name), _top_set(block, peak, name)
        if not w1 or not wp:
            continue
        is_bw = "pull-up" in name.lower() or "dip" in name.lower()

        def fmt(s):
            lb = round((s.get("weight_kg") or 0) * KG_TO_LBS)
            tag = f"BW+{lb}" if is_bw else f"{lb}"
            return f"{tag}×{s.get('reps')}@{s.get('rpe'):g}" if s.get("rpe") is not None else f"{tag}×{s.get('reps')}"

        lines.append(f"• {name}: W1 {fmt(w1)} → W{peak} {fmt(wp)}")
    return "\n".join(lines)


def sync_log(skip: bool) -> bool:
    if skip:
        print("Skipping Hevy sync.")
        return True
    try:
        subprocess.run([sys.executable, "-m", "scripts.hevy.sync_archive"],
                       cwd=REPO_ROOT, check=True)
        return True
    except Exception as exc:  # noqa: BLE001 — resilience: draft off last-known data
        print(f"⚠️ Hevy sync failed ({exc}); proceeding on last-known data.")
        return False


def commit_draft() -> None:
    """Commit the draft files to a dedicated branch (never master), best-effort."""
    git = ["git", "-C", str(REPO_ROOT)]
    rels = [str(p.relative_to(REPO_ROOT)) for p in (DRAFT_MD, DRAFT_JSON) if p.exists()]
    if not rels:
        print("No draft files to commit.")
        return
    try:
        # Create or switch to the draft branch from current HEAD.
        exists = subprocess.run(git + ["rev-parse", "--verify", DRAFT_BRANCH],
                                capture_output=True).returncode == 0
        subprocess.run(git + ["checkout", DRAFT_BRANCH] if exists
                       else git + ["checkout", "-b", DRAFT_BRANCH], check=True)
        subprocess.run(git + ["add", "--", *rels], check=True)
        status = subprocess.run(git + ["status", "--porcelain", "--", *rels],
                                capture_output=True, text=True, check=True)
        if not status.stdout.strip():
            print("No changes to commit.")
            return
        block = json.loads(DRAFT_JSON.read_text())
        subprocess.run(git + ["commit", "-m",
                              f"draft: next block after {block.get('block_id','?')} (end-of-W4)"],
                       check=True)
        subprocess.run(git + ["push", "-u", "origin", DRAFT_BRANCH], check=True)
        print(f"Committed draft to {DRAFT_BRANCH}.")
    except Exception as exc:  # noqa: BLE001 — notification already shipped; don't hard-fail
        print(f"⚠️ Draft commit/push failed ({exc}). Draft files are on disk.")


def cmd_check(args) -> int:
    today = _today(args.date)
    proceed, geo = evaluate_guard(today, args.force)
    print(json.dumps({"today": today.isoformat(), "proceed": proceed, **geo}, indent=2))
    if proceed and not args.no_sync:
        sync_log(args.skip_sync)
    return 0 if proceed else SKIP_EXIT


def cmd_notify(args) -> int:
    if not DRAFT_JSON.is_file():
        raise SystemExit(f"No draft at {DRAFT_JSON} — run the design skill (draft mode) first.")
    block = json.loads(DRAFT_JSON.read_text())
    title = f"{block.get('block_id', 'next-block')} DRAFT"

    if args.dry_run:
        url = "<dry-run: no Sheet>"
        export(block, title, dry_run=True)
    else:
        url = export(block, title) or "<no url>"

    msg = (
        f"📋 <b>Next-block draft ready</b> — {block.get('block_id','?')}\n"
        f"Drafted end of W4 from W1–W4 actuals. <i>Provisional</i> — review during the W5 "
        f"deload, finalize after the block review.\n\n"
        f"{_glance(block)}\n\n"
        f"Sheet: {url}"
    )
    if args.dry_run:
        print("\n===== TELEGRAM =====\n" + msg)
        return 0

    telegram.send_message(msg)
    print("Sent Telegram heads-up.")
    if not args.no_commit:
        commit_draft()
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="Guard: is today the W4 Sunday? (exit 3 = skip)")
    c.add_argument("--force", action="store_true")
    c.add_argument("--date")
    c.add_argument("--no-sync", action="store_true", help="Don't sync even when proceeding.")
    c.add_argument("--skip-sync", action="store_true", help="Treat sync as a no-op success.")
    c.set_defaults(func=cmd_check)

    n = sub.add_parser("notify", help="Export Sheet + Telegram + commit the draft.")
    n.add_argument("--dry-run", action="store_true")
    n.add_argument("--no-commit", action="store_true")
    n.set_defaults(func=cmd_notify)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
