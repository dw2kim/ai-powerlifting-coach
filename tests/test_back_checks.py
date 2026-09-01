import tempfile
import unittest
from pathlib import Path

from scripts.review.back_checks import load_injections


class LoadInjectionsTests(unittest.TestCase):
    def _load(self, rows: str) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "injections.md"
            path.write_text(rows)
            return load_injections(path)

    def test_markdown_emphasis_is_normalized_before_validation(self):
        injections = self._load(
            "| 2026-08-28 | **given** | _lower back_ | **anesthetic** | note |\n"
        )

        self.assertEqual(
            injections,
            [{
                "date": "2026-08-28",
                "status": "given",
                "site": "lower back",
                "agent": "anesthetic",
            }],
        )

    def test_cancelled_and_unknown_statuses_are_ignored(self):
        injections = self._load(
            "| 2026-08-28 | **cancelled** | lower back | anesthetic | note |\n"
            "| 2026-09-11 | delayed | lower back | anesthetic | note |\n"
        )

        self.assertEqual(injections, [])


if __name__ == "__main__":
    unittest.main()
