"""Where a block's routines get filed.

Two jobs here.

1. **Folder reuse** — a retry after a partial failure must not create a second folder.
   B7's push failed twice on 2026-11-02 and left TWO empty folders titled 2026-Q4-B07
   (4003373 and 4003492), because the push created a folder before POSTing the first routine
   and the retry created another. Hevy has no DELETE for folders or routines via the API, so
   each orphan is a manual cleanup in the app.
2. **One folder per week** — from B8, routines are filed under `<block-id>-W<n>` so a
   training week is one tap in the app (FB 2026-11-21). B7 and earlier stay on the old
   single-folder shape, pinned by `"folder_layout": "single"` in their own JSON, because
   re-shaping a block he is already training off is not a correction.
"""
import unittest

from scripts.hevy.push_block import (
    existing_folders,
    existing_routines,
    folder_layout,
    folder_title,
    resolve_folder,
)


class _Client:
    """Stub with a settable response shape — the real one is not pinned down anywhere."""

    def __init__(self, items, raises=False):
        self.items, self.raises = items, raises

    def paginate(self, path, key, **kw):
        assert path == "/routine_folders", path
        assert key == "routine_folders", key
        if self.raises:
            raise RuntimeError("404 not found")
        return iter(self.items)


class ExistingFoldersTests(unittest.TestCase):
    def test_finds_the_folder_by_title(self):
        c = _Client([{"id": 4003373, "title": "2026-Q4-B07"},
                     {"id": 3744659, "title": "2026-Q4-B06"}])
        self.assertEqual(existing_folders(c, "2026-Q4-B07"), [4003373])

    def test_the_real_duplicate_case_returns_both_oldest_first(self):
        """Both of B7's orphans; the push fills the first and warns about the rest."""
        c = _Client([{"id": 4003492, "title": "2026-Q4-B07"},
                     {"id": 4003373, "title": "2026-Q4-B07"}])
        self.assertEqual(existing_folders(c, "2026-Q4-B07"), [4003373, 4003492])

    def test_no_match_is_empty_so_the_caller_creates_one(self):
        c = _Client([{"id": 1, "title": "2026-Q4-B06"}])
        self.assertEqual(existing_folders(c, "2026-Q4-B07"), [])

    def test_nested_routine_folder_shape_is_handled(self):
        c = _Client([{"routine_folder": {"id": 7, "title": "2026-Q4-B07"}}])
        self.assertEqual(existing_folders(c, "2026-Q4-B07"), [7])

    def test_a_lookup_failure_is_not_fatal(self):
        """A blocked push is worse than a duplicate folder, so this degrades, not raises."""
        self.assertEqual(existing_folders(_Client([], raises=True), "2026-Q4-B07"), [])

    def test_junk_items_are_skipped(self):
        c = _Client([None, "nope", {"title": "2026-Q4-B07"}, {"id": 9, "title": "2026-Q4-B07"}])
        self.assertEqual(existing_folders(c, "2026-Q4-B07"), [9])


class FolderLayoutTests(unittest.TestCase):
    def test_per_week_is_the_default_so_a_new_block_gets_it_unasked(self):
        self.assertEqual(folder_layout({"block_id": "2026-Q4-B08"}), "per-week")

    def test_a_live_block_pins_itself_to_single(self):
        self.assertEqual(folder_layout({"folder_layout": "single"}), "single")

    def test_a_typo_in_the_key_fails_loudly_before_the_api_is_touched(self):
        with self.assertRaises(SystemExit):
            folder_layout({"folder_layout": "weekly"})

    def test_the_titles_are_the_ones_he_asked_for(self):
        self.assertEqual(folder_title("2026-Q4-B08", "per-week", 1), "2026-Q4-B08-W1")
        self.assertEqual(folder_title("2026-Q4-B08", "per-week", 5), "2026-Q4-B08-W5")
        self.assertEqual(folder_title("2026-Q4-B07", "single", 3), "2026-Q4-B07")


class _FolderClient:
    """Stub that records folder POSTs, so a test can see what the push would create."""

    def __init__(self, folders=()):
        self.folders = list(folders)
        self.posted = []
        self._next = 500

    def paginate(self, path, key, **kw):
        return iter(self.folders)

    def post(self, path, body):
        assert path == "/routine_folders", path
        title = body["routine_folder"]["title"]
        self.posted.append(title)
        self._next += 1
        self.folders.append({"id": self._next, "title": title})
        return {"routine_folder": {"id": self._next}}


class ResolveFolderTests(unittest.TestCase):
    def test_creates_the_week_folder_when_it_is_missing(self):
        c = _FolderClient()
        fid = resolve_folder(c, "2026-Q4-B08-W1", create=True, apply=True)
        self.assertEqual(c.posted, ["2026-Q4-B08-W1"])
        self.assertEqual(fid, 501)

    def test_reuses_the_week_folder_on_a_retry(self):
        """The whole point: a second attempt at W1 must not make a second W1 folder."""
        c = _FolderClient([{"id": 77, "title": "2026-Q4-B08-W1"}])
        self.assertEqual(resolve_folder(c, "2026-Q4-B08-W1", create=True, apply=True), 77)
        self.assertEqual(c.posted, [])

    def test_update_mode_never_creates_a_folder(self):
        """A correction leaves no empty folder behind; the routine keeps its own."""
        c = _FolderClient()
        self.assertIsNone(resolve_folder(c, "2026-Q4-B08-W3", create=False, apply=True))
        self.assertEqual(c.posted, [])

    def test_a_dry_run_touches_nothing(self):
        c = _FolderClient()
        self.assertIsNone(resolve_folder(c, "2026-Q4-B08-W1", create=True, apply=False))
        self.assertEqual(c.posted, [])


class _RoutineClient:
    def __init__(self, routines):
        self.routines = routines

    def paginate(self, path, key, **kw):
        assert path == "/routines", path
        return iter(self.routines)


class ExistingRoutinesScopeTests(unittest.TestCase):
    """Routine titles carry no block id, so the folder is what tells two blocks apart.

    B3 and B4 both ran "W1-D1 Squat + Comp Bench". A leftover routine under the prior
    block's folder must not be mistaken for this block's.
    """

    ROUTINES = [
        {"id": "b7", "title": "W1-D1 Squat + Comp Bench", "folder_id": 100},
        {"id": "b8", "title": "W1-D1 Squat + Comp Bench", "folder_id": 200},
        {"id": "loose", "title": "tmp", "folder_id": None},
        {"id": "", "title": "no id", "folder_id": 200},
    ]

    def test_scoped_to_this_blocks_folders(self):
        got = existing_routines(_RoutineClient(self.ROUTINES), {200})
        self.assertEqual(got, {"W1-D1 Squat + Comp Bench": "b8"})

    def test_a_prior_blocks_routine_is_invisible_to_the_new_block(self):
        got = existing_routines(_RoutineClient(self.ROUTINES), {999})
        self.assertEqual(got, {})

    def test_a_folder_id_from_the_command_line_still_matches(self):
        """`--folder-id 200` is the string "200"; Hevy's folder_id is the int 200."""
        got = existing_routines(_RoutineClient(self.ROUTINES), {"200"})
        self.assertEqual(got, {"W1-D1 Squat + Comp Bench": "b8"})

    def test_none_falls_back_to_the_whole_account(self):
        """What an update does when the block's folders can't be found: better a title
        match than a duplicate set of routines."""
        got = existing_routines(_RoutineClient(self.ROUTINES), None)
        self.assertIn("tmp", got)
        self.assertEqual(len(got), 2)


if __name__ == "__main__":
    unittest.main()
