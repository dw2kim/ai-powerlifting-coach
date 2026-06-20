"""Weekly Saturday review — the entrypoint the GitHub Action runs.

Pipeline:
  1. Time guard — only proceed at Saturday 11:00 America/New_York (DST-safe).
  2. Sync the Hevy log so the data is fresh (best-effort; a sync failure degrades
     to last-known data with a readiness warning rather than skipping the review).
  3. Compute the weekly metrics.
  4. Render the PNG progress chart.
  5. Write the coach-voice narrative (Anthropic API; falls back to a template).
  6. Send the chart + narrative to Telegram.
  7. Archive a snapshot to reviews/weekly/ and commit the synced data + snapshot.

Flags:
  --force        bypass the time guard (manual / test runs)
  --dry-run      compute + render + print; no Telegram, no commit
  --no-commit    send, but don't commit/push (e.g. local Telegram test)
  --skip-sync    don't hit the Hevy API (offline testing)
  --date         override 'today' (YYYY-MM-DD) for testing
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from datetime import date as date_cls, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..hevy.block_report import DEFAULT_BW, REPO_ROOT
from ..notifications import telegram
from .narrate import gather_context, narrate, render_fallback
from .render_chart import render
from .weekly_metrics import build_stats

EASTERN = ZoneInfo("America/New_York")
WEEKLY_DIR = REPO_ROOT / "reviews" / "weekly"
# Chart is a delivery artifact, not repo state — render to a temp path.
CHART_PATH = Path(tempfile.gettempdir()) / "weekly_review_chart.png"


def _eastern_now() -> datetime:
    return datetime.now(EASTERN)


def time_guard(force: bool) -> bool:
    """True if we should run. The job is scheduled at both 15:00 and 16:00 UTC on
    Saturday so that exactly one firing lands on 11:00 Eastern in either EDT or EST;
    this guard is what picks the right one."""
    if force:
        return True
    now = _eastern_now()
    ok = now.weekday() == 5 and now.hour == 11
    print(f"Eastern now = {now:%Y-%m-%d %H:%M %Z} (Sat? {now.weekday()==5}, "
          f"hour {now.hour}) → {'proceed' if ok else 'skip'}")
    return ok


def sync_log(skip: bool) -> bool:
    """Pull the latest Hevy workouts. Best-effort: returns False on failure so the
    review still ships from local data with a readiness caveat."""
    if skip:
        print("Skipping Hevy sync (--skip-sync)")
        return True
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.hevy.sync_archive"],
            cwd=REPO_ROOT, check=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — resilience is the point here
        print(f"⚠️ Hevy sync failed ({exc}); proceeding on last-known data.")
        return False


def caption(stats: dict, synced: bool) -> str:
    geo = stats["geometry"]
    rd = stats["readiness"]
    flag = "✅" if rd["all_in"] else "⚠️"
    sync_note = "" if synced else " · ⚠️ sync failed"
    return (f"🏋️ {geo['block_id']} · Week {geo['week_no']}/{geo['weeks']} "
            f"{flag} {stats['generated_for']}{sync_note}")


def build_message(stats: dict) -> str:
    try:
        text = narrate(stats, gather_context())
        print("Narrative: Anthropic API")
        return text
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Narrative API unavailable ({exc}); using template fallback.")
        return render_fallback(stats)


def write_snapshot(stats: dict, message: str) -> Path:
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    today = date_cls.fromisoformat(stats["generated_for"])
    iso_year, iso_week, _ = today.isocalendar()
    path = WEEKLY_DIR / f"{iso_year}-W{iso_week:02d}.md"
    geo = stats["geometry"]
    header = (f"# Weekly review — {geo['block_id']} · Week {geo['week_no']}/{geo['weeks']}"
              f"\n\n_Generated {stats['generated_for']} (Sat 11:00 ET). "
              f"Hevy log = source of truth._\n\n---\n\n")
    path.write_text(header + message + "\n")
    return path


def commit(paths: list[Path]) -> None:
    """Commit the synced data + snapshot so the repo stays fresh and the scheduled
    workflow stays alive (GitHub disables crons after 60 days of inactivity)."""
    rels = [str(p.relative_to(REPO_ROOT)) for p in paths]
    subprocess.run(["git", "-C", str(REPO_ROOT), "add", "--", *rels], check=True)
    status = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", *rels],
        capture_output=True, text=True, check=True,
    )
    if not status.stdout.strip():
        print("No changes to commit.")
        return
    subprocess.run(
        ["git", "-C", str(REPO_ROOT), "commit", "-m",
         "chore(review): weekly Saturday sync + snapshot"],
        check=True,
    )
    subprocess.run(["git", "-C", str(REPO_ROOT), "push"], check=True)
    print("Committed + pushed weekly review.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--skip-sync", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--bw", type=float, default=DEFAULT_BW)
    args = ap.parse_args()

    if not time_guard(args.force):
        return

    synced = sync_log(args.skip_sync or args.dry_run)
    today = date_cls.fromisoformat(args.date) if args.date else None
    stats = build_stats(today, args.bw)

    render(stats, CHART_PATH)
    message = build_message(stats)
    cap = caption(stats, synced)

    if args.dry_run:
        print("\n===== CAPTION =====\n" + cap)
        print("\n===== MESSAGE =====\n" + message)
        print(f"\n===== CHART =====\n{CHART_PATH}")
        return

    telegram.send_photo(CHART_PATH, caption=cap)
    telegram.send_message(message)
    print("Sent to Telegram.")

    snapshot = write_snapshot(stats, message)
    if not args.no_commit:
        commit([REPO_ROOT / "data" / "logs", REPO_ROOT / "brain" / "current-block.json", snapshot])


if __name__ == "__main__":
    main()
