"""Block handover readiness — the check that would have caught B7 arriving with nothing.

B6 ended Fri 2026-10-30 with no block review and a `next-block-draft.json` four blocks out
of date (2026-Q3-B04, from July). B7 was due to start Mon 2026-11-02. Nothing in the repo
said a word, and the athlete had to ask.

Two separate defects, one test file:
  1. nothing checked that a block had ended without a review or a draft  -> handover.py
  2. `draft_next_block`'s guard could only ever fire on the W4 Sunday, because
     `geometry()` clamps week_no to the block length -> one missed firing was permanent.
"""
import json
import unittest
from datetime import date
from unittest import mock

from scripts.review import draft_next_block, handover


def _block(block_id="2026-Q4-B06", start="2026-09-28", weeks=5, final_days=("D1", "D2", "D3", "D4")):
    return {
        "block_id": block_id,
        "start_date": start,
        "weeks": weeks,
        "prescriptions": [{"week": weeks, "day": d, "exercises": []} for d in final_days],
    }


class BlockEndTests(unittest.TestCase):
    def test_end_is_the_last_prescribed_day_of_the_final_week(self):
        # W1 Mon 2026-09-28 + 4 weeks, D4 = Friday -> 2026-10-30, which is what B6 did.
        self.assertEqual(handover.block_end(_block()), date(2026, 10, 30))

    def test_a_final_week_that_drops_days_ends_earlier(self):
        # B5 W6 ran D1 + D2 only. The end date must not claim a Friday it never trained.
        self.assertEqual(
            handover.block_end(_block(final_days=("D1", "D2"))), date(2026, 10, 27))


class DraftStatusTests(unittest.TestCase):
    def _with_draft(self, payload, archived=()):
        m = mock.mock_open(read_data=json.dumps(payload))
        return mock.patch.object(handover, "DRAFT_JSON", mock.MagicMock(
            exists=lambda: True, read_text=lambda: json.dumps(payload))), \
            mock.patch.object(handover, "_archived_ids", lambda: set(archived))

    def test_a_draft_of_an_archived_block_is_stale_not_present(self):
        """The actual B6 bug: the draft said 2026-Q3-B04, which had been archived in August."""
        d, a = self._with_draft({"block_id": "2026-Q3-B04"}, archived={"2026-Q3-B04"})
        with d, a:
            self.assertEqual(handover.draft_status("2026-Q4-B06"), ("stale", "2026-Q3-B04"))

    def test_a_draft_of_the_running_block_is_stale(self):
        d, a = self._with_draft({"block_id": "2026-Q4-B06"})
        with d, a:
            self.assertEqual(handover.draft_status("2026-Q4-B06")[0], "stale")

    def test_a_draft_of_an_unseen_next_block_is_current(self):
        d, a = self._with_draft({"block_id": "2026-Q4-B07"}, archived={"2026-Q4-B06"})
        with d, a:
            self.assertEqual(handover.draft_status("2026-Q4-B06"), ("current", "2026-Q4-B07"))

    def test_missing_file_is_missing(self):
        with mock.patch.object(handover, "DRAFT_JSON",
                               mock.MagicMock(exists=lambda: False)):
            self.assertEqual(handover.draft_status("x"), ("missing", None))


class StateTests(unittest.TestCase):
    def _state(self, today, draft="stale", review=False):
        with mock.patch.object(handover, "draft_status", lambda _: (draft, "2026-Q3-B04")), \
             mock.patch.object(handover, "REVIEWS", mock.MagicMock(
                 __truediv__=lambda s, o: mock.MagicMock(exists=lambda: review))):
            return handover.state(_block(), date.fromisoformat(today))

    def test_silent_before_the_penultimate_week(self):
        st = self._state("2026-10-17")          # B6 W3
        self.assertFalse(st["active"])
        self.assertEqual(handover.render(st), "")

    def test_nags_in_the_penultimate_week_but_does_not_block(self):
        st = self._state("2026-10-24")          # B6 W4 Saturday
        self.assertTrue(st["active"])
        self.assertFalse(st["ended"])
        self.assertEqual(handover.blocking(st), [])
        self.assertIn("STALE", handover.render(st))

    def test_blocks_once_the_block_has_ended_with_no_review_and_no_draft(self):
        st = self._state("2026-10-31")          # the Saturday after B6 ended
        self.assertTrue(st["ended"])
        self.assertEqual(len(handover.blocking(st)), 2)
        self.assertIn("no review", " ".join(handover.blocking(st)))

    def test_week_no_keeps_counting_past_the_end_unlike_geometry(self):
        """geometry() clamps to the block length; a handover warning must outlive the block."""
        # B6 W1 Monday was 2026-09-28; 2026-11-08 is 41 days on = week 6, past the 5-week block.
        self.assertEqual(self._state("2026-11-08")["week_no"], 6)

    def test_a_current_draft_and_a_written_review_clear_it(self):
        st = self._state("2026-10-31", draft="current", review=True)
        self.assertEqual(handover.blocking(st), [])
        self.assertIn("✅", handover.render(st))


class DraftGuardCatchUpTests(unittest.TestCase):
    """The guard bug: `week_no == target` could only ever be true on one single Sunday."""

    def _guard(self, today, draft="stale", block=None):
        blk = block or _block()
        with mock.patch.object(draft_next_block, "CURRENT_BLOCK", mock.MagicMock(
                read_text=lambda: json.dumps(blk))), \
             mock.patch.object(handover, "draft_status", lambda _: (draft, "2026-Q3-B04")):
            return draft_next_block.evaluate_guard(date.fromisoformat(today), force=False)

    def test_fires_on_the_target_sunday(self):
        proceed, geo = self._guard("2026-10-25")    # B6 W4 Sunday
        self.assertTrue(proceed)
        self.assertIn("on-target", geo["reason"])

    def test_silent_on_an_earlier_sunday(self):
        self.assertFalse(self._guard("2026-10-18")[0])

    def test_silent_on_a_weekday(self):
        self.assertFalse(self._guard("2026-10-26")[0])

    def test_catches_up_on_later_sundays_while_the_draft_is_stale(self):
        """This is the regression. Every one of these used to return False forever."""
        for d in ("2026-11-01", "2026-11-08", "2026-11-15"):
            proceed, geo = self._guard(d)
            self.assertTrue(proceed, f"{d} should catch up")
            self.assertIn("catch-up", geo["reason"])

    def test_catch_up_stops_once_a_current_draft_exists(self):
        """Otherwise a Sunday in the deload would redraft over a draft under review."""
        self.assertFalse(self._guard("2026-11-08", draft="current")[0])

    def test_catch_up_also_covers_a_missing_draft(self):
        self.assertTrue(self._guard("2026-11-08", draft="missing")[0])


if __name__ == "__main__":
    unittest.main()
