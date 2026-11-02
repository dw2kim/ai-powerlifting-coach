"""Folder reuse: a retry after a partial failure must not create a second folder.

B7's push failed twice on 2026-11-02 and left TWO empty folders titled 2026-Q4-B07 (4003373
and 4003492), because the push created a folder before POSTing the first routine and the
retry created another. Hevy has no DELETE for folders or routines via the API, so each
orphan is a manual cleanup in the app.
"""
import unittest

from scripts.hevy.push_block import existing_folders


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


if __name__ == "__main__":
    unittest.main()
