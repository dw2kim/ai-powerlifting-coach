"""Weekly Saturday review — the entrypoint the GitHub Action runs.

Pipeline:
  1. Time guard — proceed on the first Saturday firing at/after 11:00
     America/New_York (DST-safe); later firings no-op on the week's snapshot.
  2. Sync the Hevy log so the data is fresh (best-effort; a sync failure degrades
     to last-known data with a readiness warning rather than skipping the review).
  3. Compute the weekly metrics.
  4. Reconcile the plan's loads against the log — correct the weeks still ahead and
     re-render the Sheet, so the plan tracks what he actually trains (`sheet-load-sync`).
  5. Render the PNG progress chart.
  6. Write the coach-voice narrative (Anthropic API; falls back to a template).
  7. Send the chart + narrative to Telegram.
  8. Archive a snapshot to reviews/weekly/ and commit the synced data + snapshot.

Flags:
  --force        bypass the time guard (manual / test runs)
  --dry-run      compute + render + print; no Telegram, no commit, no plan edits
  --no-commit    send, but don't commit/push (e.g. local Telegram test)
  --skip-sync    don't hit the Hevy API (offline testing)
  --no-reconcile      skip the load reconciliation entirely
  --reconcile-report  reconcile in report-only mode (no plan edits, no Sheet push)
  --date         override 'today' (YYYY-MM-DD) for testing
  --assert-shipped  fail the job if the week still has no review after this firing
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..hevy.block_report import DEFAULT_BW, REPO_ROOT
from ..notifications import telegram
from ..sheets import reconcile_loads as recon
from . import back_checks
from .narrate import gather_context, narrate, render_fallback
from .render_chart import render
from .weekly_metrics import BLOCK_JSON, build_stats

EASTERN = ZoneInfo("America/New_York")
WEEKLY_DIR = REPO_ROOT / "reviews" / "weekly"
# Chart is a delivery artifact, not repo state — render to a temp path.
CHART_PATH = Path(tempfile.gettempdir()) / "weekly_review_chart.png"


def _eastern_now() -> datetime:
    return datetime.now(EASTERN)


def snapshot_path_for(day: date_cls) -> Path:
    """The week's snapshot file. Also the idempotency key for the time guard —
    one review per ISO week, whichever firing gets there first."""
    iso_year, iso_week, _ = day.isocalendar()
    return WEEKLY_DIR / f"{iso_year}-W{iso_week:02d}.md"


LOOKBACK_WEEKS = 8


def missed_weeks(today: date_cls, lookback: int = LOOKBACK_WEEKS) -> list[str]:
    """Past Saturdays in the lookback window that never got a review.

    A run can only ever speak for itself, and a week is lost precisely when no run
    happens: if GitHub drops every firing there is nobody left to raise the alarm.
    So the alarm has to be raised afterwards, by the next review that does ship.

    This is the check that would have caught 2026-W30 on 2026-08-01 instead of five
    weeks later, and W35 on 2026-09-05 instead of by the athlete noticing his phone
    was quiet.

    Floored at the earliest snapshot on disk so it never flags the weeks before the
    review job existed.
    """
    existing = sorted(p.stem for p in WEEKLY_DIR.glob("*-W*.md"))
    if not existing:
        return []
    floor = existing[0]
    saturday = today - timedelta(days=(today.weekday() - 5) % 7)
    gaps = []
    for i in range(1, lookback + 1):   # from 1: the week being shipped is not a gap
        d = saturday - timedelta(weeks=i)
        iso_year, iso_week, _ = d.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        if key >= floor and not (WEEKLY_DIR / f"{key}.md").exists():
            gaps.append(key)
    return sorted(gaps)


def time_guard(force: bool) -> tuple[bool, str]:
    """(should we run, why).

    The job is scheduled several times on Saturday so that one firing lands at or after
    11:00 Eastern in either EDT or EST. This guard decides which firing does the work.

    It used to decide by matching the hour exactly (`now.hour == 11`), which assumed
    GitHub fires scheduled workflows on time. It does not — cron runs are best-effort and
    queue behind runner load, routinely by tens of minutes and occasionally by hours. Any
    firing that slipped past 11:59 Eastern missed the window, the job returned cleanly,
    and the review was dropped with a green check and no Telegram. That silently ate
    2026-W30 (both firings landed 12:02 and 13:06 ET) and 2026-W35 (14:10 and 15:20 ET),
    and 2026-W31 survived by 58 seconds.

    So the clock is no longer the thing that has to be exact. Run on any Saturday firing
    from 11:00 Eastern onward, and let the week's snapshot be the idempotency key — the
    later firings become the no-op instead of the delay becoming a dropped review. A
    delayed run still ships, just late. In EST the 15:00 UTC firing lands at 10:00 and is
    still correctly held back for the 16:00 one.

    The snapshot is committed and pushed by the run that writes it, and the workflow's
    concurrency group serialises firings, so a later firing checks out a tree that already
    carries it. If that push ever fails, this degrades to a duplicate review rather than a
    missing one — the right way round.
    """
    if force:
        print("Time guard bypassed (--force).")
        return True, "forced"
    now = _eastern_now()
    is_saturday = now.weekday() == 5
    past_11 = now.hour >= 11
    done = snapshot_path_for(now.date()).exists()
    ok = is_saturday and past_11 and not done
    reason = ("this firing does the work" if ok else
              "not Saturday" if not is_saturday else
              "before 11:00 ET" if not past_11 else
              "this week's review already shipped")
    print(f"Eastern now = {now:%Y-%m-%d %H:%M %Z} (Sat? {is_saturday}, hour {now.hour}, "
          f"already shipped? {done}) → {'proceed' if ok else 'skip'} — {reason}")
    return ok, reason


def summary(*lines: str) -> None:
    """Write the run's outcome to the Actions run page.

    In the runs list a green check that shipped a review and a green check that
    skipped one are the same pixel. That is how 2026-W30 sat unnoticed for five
    weeks and W35 for two days — the status was never wrong, it just never said
    what happened. This puts the outcome where it is read without opening a log.
    """
    print("\n".join(lines))
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError as exc:  # noqa: BLE001 — a summary is never worth failing a send over
        print(f"⚠️ Could not write the job summary ({exc}).")


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


def reconcile_step(today: date_cls | None, bw: float, *,
                   enabled: bool = True, apply_changes: bool = True) -> dict | None:
    """Diff the plan's loads against the log; correct the weeks still ahead and push the
    Sheet (rule `sheet-load-sync`).

    Only accessories are rewritten, and only for weeks that haven't been trained — see
    `reconcile_loads` for why primaries are report-only. Entirely best-effort: this runs
    after the metrics are computed, so any failure here costs the load sync, never the
    weekly review itself.

    Returns the report (with `changes` / `pushed` attached) for the narrative, or None.
    """
    if not enabled:
        return None
    try:
        block = recon.load_block()
        report = recon.reconcile(block, today, bw=bw)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Load reconciliation failed ({exc}); plan left as-is.")
        return None

    # None (not []) in report-only mode, so the summary omits the "applied" section
    # instead of claiming nothing needed doing.
    changes: list[dict] | None = None
    pushed = False
    if apply_changes:
        changes = []
        try:
            changes = recon.apply_corrections(block, report)
            if changes:
                BLOCK_JSON.write_text(json.dumps(block, indent=2, ensure_ascii=False) + "\n")
                print(f"Load sync: rewrote {len(changes)} prescription(s) from W{report['from_week']}.")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Could not apply load corrections ({exc}).")
            changes = []
        if changes:
            # The Sheet is the athlete's surface — a corrected JSON nobody can see is
            # half a fix. Needs GOOGLE_SA_JSON + SHEETS_SPREADSHEET_ID; skipped without them.
            try:
                from ..sheets.export_block import export
                export(block, block.get("block_id", "block"), final=True)
                pushed = True
            except SystemExit as exc:      # missing creds — expected when unconfigured
                print(f"⚠️ Sheet not updated ({exc}). Corrections are in the block JSON.")
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️ Sheet push failed ({exc}). Corrections are in the block JSON.")
    report["changes"] = changes
    report["pushed_to_sheet"] = pushed
    return report


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
    path = snapshot_path_for(today)
    geo = stats["geometry"]
    header = (f"# Weekly review — {geo['block_id']} · Week {geo['week_no']}/{geo['weeks']}"
              f"\n\n_Generated {stats['generated_for']} (Saturday review). "
              f"Hevy log = source of truth._\n\n---\n\n")
    body = message + "\n"
    bc = stats.get("back_checks")
    if bc:
        # The compliance record is the audit trail behind "no check, no progression" —
        # keep it with the week it judged, not just in the file it was read from.
        body += ("\n---\n\n" + back_checks.render(bc) + "\n")
    report = stats.get("load_drift")
    if report:
        # Keep the audit trail of what the sync moved next to the review it moved on.
        body += ("\n---\n\n" + recon.render_md(report, report.get("changes")) + "\n")
    path.write_text(header + body)
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
    ap.add_argument("--no-reconcile", action="store_true",
                    help="Skip the plan-vs-log load reconciliation entirely")
    ap.add_argument("--reconcile-report", action="store_true",
                    help="Reconcile in report-only mode — no plan edits, no Sheet push")
    ap.add_argument("--date")
    ap.add_argument("--bw", type=float, default=DEFAULT_BW)
    ap.add_argument("--assert-shipped", action="store_true",
                    help="Fail the job if this Saturday still has no review after "
                         "this firing. Wire it to the last scheduled firing of the day.")
    args = ap.parse_args()

    proceed, why = time_guard(args.force)
    if not proceed:
        # A skip is the correct outcome for every firing but the one that does the
        # work, so it stays green — turning the second firing red every Saturday
        # would train us to ignore a red Saturday, which is the actual failure mode
        # we are trying to fix. It must simply stop LOOKING like a shipped review.
        summary(f"### ⏭️ Weekly review skipped", "", f"**Reason:** {why}.", "",
                "No Telegram message was sent by this run.")
        if args.assert_shipped and not snapshot_path_for(_eastern_now().date()).exists():
            # Last firing of the day, and the week still has nothing. Every earlier
            # firing was delayed, dropped or refused: that is a lost review, and a
            # lost review must never be green.
            summary("", "### ❌ No review shipped this week",
                    "", "This was the last scheduled firing and "
                    f"`{snapshot_path_for(_eastern_now().date()).name}` does not exist. "
                    "Re-run this workflow with `review_date` set to this Saturday.")
            raise SystemExit(
                "FAILED: the week is over and no review was ever sent. "
                "Failing loudly rather than exiting green."
            )
        return

    synced = sync_log(args.skip_sync or args.dry_run)
    today = date_cls.fromisoformat(args.date) if args.date else None
    # Metrics first: the week just finished is judged against the plan it actually ran
    # under, before the sync rewrites anything ahead of it.
    stats = build_stats(today, args.bw)
    report = reconcile_step(
        today, args.bw,
        enabled=not args.no_reconcile,
        apply_changes=not (args.dry_run or args.reconcile_report),
    )
    if report:
        stats["load_drift"] = report

    render(stats, CHART_PATH)
    message = build_message(stats)
    cap = caption(stats, synced)

    # Surface lost weeks where he actually looks — his phone — not only in a job log.
    gaps = missed_weeks(date_cls.fromisoformat(stats["generated_for"]))
    if gaps:
        message += ("\n\n⚠️ <b>No review was ever sent for: "
                    + ", ".join(gaps) + "</b>")

    if args.dry_run:
        print("\n===== CAPTION =====\n" + cap)
        print("\n===== MESSAGE =====\n" + message)
        if report:
            print("\n===== LOAD SYNC (report only in --dry-run) =====\n"
                  + recon.render_md(report, report.get("changes")))
        print(f"\n===== CHART =====\n{CHART_PATH}")
        summary("### 🔍 Dry run — nothing sent, nothing committed")
        return

    telegram.send_photo(CHART_PATH, caption=cap)
    telegram.send_message(message)
    print("Sent to Telegram.")

    snapshot = write_snapshot(stats, message)
    if not args.no_commit:
        commit([REPO_ROOT / "data" / "logs", REPO_ROOT / "brain" / "current-block.json", snapshot])

    geo = stats["geometry"]
    summary(f"### ✅ Weekly review shipped — {geo['block_id']} W{geo['week_no']}/{geo['weeks']}",
            "", f"- Telegram: **sent**",
            f"- Hevy sync: {'ok' if synced else '**failed** — ran on last-known data'}",
            f"- Snapshot: `{snapshot.relative_to(REPO_ROOT)}`")

    if gaps:
        # Shipped first, complain second: a past gap must never withhold this week's
        # review. But it must not leave a green check either — green is what let W30
        # sit unnoticed for five weeks.
        summary("", "### ❌ Weeks that never got a review", "",
                *[f"- `{g}`" for g in gaps], "",
                "Re-run this workflow with `review_date` set to that Saturday.")
        raise SystemExit(
            "This week shipped, but these weeks never did: " + ", ".join(gaps)
        )


if __name__ == "__main__":
    main()
