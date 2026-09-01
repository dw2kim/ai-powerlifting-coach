"""Tests for the Saturday scheduling logic in scripts/review/weekly_review.py.

Run: python -m unittest discover -s tests

These cover the two things that actually went wrong in production — a review that
was never generated (2026-W30, 2026-W35) and the fact that nothing noticed — so
they are written against real firing times taken from the Actions API rather than
invented ones.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts.review import weekly_review as wr

ET = ZoneInfo("America/New_York")

# (run_started_at UTC, did the OLD guard let it ship) — every scheduled firing of
# the weekly review from 2026-06-27 to 2026-08-29, from the Actions API.
FIRINGS = [
    ("2026-06-27T15:29:33Z", True),  ("2026-06-27T16:31:49Z", False),
    ("2026-07-04T15:26:05Z", True),  ("2026-07-04T16:27:08Z", False),
    ("2026-07-11T15:54:27Z", True),  ("2026-07-11T17:04:21Z", False),
    ("2026-07-18T15:55:19Z", True),  ("2026-07-18T17:03:20Z", False),
    ("2026-07-25T16:02:41Z", False), ("2026-07-25T17:06:58Z", False),  # W30 lost
    ("2026-08-01T15:59:02Z", True),  ("2026-08-01T17:07:07Z", False),  # by 58s
    ("2026-08-08T15:27:27Z", True),  ("2026-08-08T16:40:51Z", False),
    ("2026-08-15T15:17:52Z", True),  ("2026-08-15T16:31:18Z", False),
    ("2026-08-22T15:18:03Z", True),  ("2026-08-22T16:31:21Z", False),
    ("2026-08-29T18:10:15Z", False), ("2026-08-29T19:20:19Z", False),  # W35 lost
]


def _et(iso_utc: str) -> datetime:
    return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(ET)


def guard_at(iso_utc: str, already_shipped: bool) -> bool:
    fake = mock.MagicMock()
    fake.exists.return_value = already_shipped
    with mock.patch.object(wr, "_eastern_now", return_value=_et(iso_utc)), \
         mock.patch.object(wr, "snapshot_path_for", return_value=fake):
        return wr.time_guard(force=False)[0]


class TimeGuard(unittest.TestCase):
    def test_edt_on_time_ships(self):
        self.assertTrue(guard_at("2026-08-29T15:00:00Z", False))     # 11:00 ET

    def test_edt_three_hours_late_still_ships(self):
        """The 2026-08-29 failure: 14:10 ET. The old guard dropped this."""
        self.assertTrue(guard_at("2026-08-29T18:10:15Z", False))

    def test_second_firing_is_a_noop_once_the_week_shipped(self):
        self.assertFalse(guard_at("2026-08-29T16:00:00Z", True))

    def test_est_first_firing_is_too_early(self):
        self.assertFalse(guard_at("2026-12-05T15:00:00Z", False))    # 10:00 EST

    def test_est_second_firing_ships(self):
        self.assertTrue(guard_at("2026-12-05T16:00:00Z", False))     # 11:00 EST

    def test_never_runs_off_saturday(self):
        self.assertFalse(guard_at("2026-08-31T15:00:00Z", False))    # Monday
        self.assertFalse(guard_at("2026-08-30T16:00:00Z", False))    # Sunday

    def test_force_bypasses(self):
        self.assertTrue(wr.time_guard(force=True)[0])

    def test_replay_new_guard_ships_every_saturday_exactly_once(self):
        shipped: set[tuple[int, int]] = set()
        for ts, _ in FIRINGS:
            week = _et(ts).date().isocalendar()[:2]
            if guard_at(ts, week in shipped):
                self.assertNotIn(week, shipped, f"{ts} shipped a second review")
                shipped.add(week)
        saturdays = {_et(ts).date().isocalendar()[:2] for ts, _ in FIRINGS}
        self.assertEqual(shipped, saturdays, "a Saturday went unshipped")

    def test_replay_reproduces_the_old_guard_and_its_two_gaps(self):
        """Guards against a fix that silently changes which firing does the work."""
        old = [(_et(ts).weekday() == 5 and _et(ts).hour == 11) for ts, _ in FIRINGS]
        self.assertEqual(old, [expected for _, expected in FIRINGS])


class MissedWeeks(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(wr, "WEEKLY_DIR", self.dir)
        patcher.start(); self.addCleanup(patcher.stop)
        ack = mock.patch.object(wr, "GAP_ACK", self.dir / ".gap-ack")
        ack.start(); self.addCleanup(ack.stop)

    def _write(self, *keys: str) -> None:
        for k in keys:
            (self.dir / f"{k}.md").write_text("x")

    def test_finds_a_gap_the_following_saturday(self):
        self._write("2026-W29", "2026-W31")          # W30 missing
        self.assertEqual(wr.missed_weeks(date(2026, 8, 1)), ["2026-W30"])

    def test_the_week_being_shipped_is_not_a_gap(self):
        self._write("2026-W34")
        self.assertNotIn("2026-W35", wr.missed_weeks(date(2026, 8, 29)))

    def test_floors_at_the_earliest_snapshot(self):
        """Never flags the weeks before the review job existed."""
        self._write("2026-W29", "2026-W30")
        self.assertEqual(wr.missed_weeks(date(2026, 7, 25)), [])

    def test_acknowledged_gaps_stop_firing(self):
        self._write("2026-W29", "2026-W31")
        self.assertEqual(wr.missed_weeks(date(2026, 8, 1)), ["2026-W30"])
        (self.dir / ".gap-ack").write_text("2026-W30  # B04, archived\n")
        self.assertEqual(wr.missed_weeks(date(2026, 8, 1)), [])

    def test_no_snapshots_at_all_is_not_eight_gaps(self):
        self.assertEqual(wr.missed_weeks(date(2026, 8, 1)), [])

    def test_gaps_fail_the_job(self):
        with self.assertRaises(SystemExit):
            wr._fail_on_gaps(["2026-W30"])
        wr._fail_on_gaps([])          # no gaps must not raise


class DateInBlock(unittest.TestCase):
    """geometry() clamps to the running block, so an out-of-block --date would
    review the wrong week and file it under the missing week's name."""

    BLOCK = {"block_id": "2026-Q3-B05", "start_date": "2026-08-10", "weeks": 5}

    def _check(self, day: date):
        with mock.patch.object(wr.recon, "load_block", return_value=self.BLOCK):
            wr._require_date_in_block(day)

    def test_accepts_a_date_inside_the_block(self):
        self._check(date(2026, 8, 29))

    def test_accepts_the_boundaries(self):
        self._check(date(2026, 8, 10))
        self._check(date(2026, 9, 13))

    def test_refuses_a_date_from_an_earlier_block(self):
        with self.assertRaises(SystemExit) as cm:
            self._check(date(2026, 7, 25))          # W30, block B04
        self.assertIn("outside the running block", str(cm.exception))

    def test_refuses_a_date_after_the_block(self):
        with self.assertRaises(SystemExit):
            self._check(date(2026, 9, 14))


if __name__ == "__main__":
    unittest.main()
