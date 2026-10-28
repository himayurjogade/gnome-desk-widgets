"""LeetCode submission streak widget."""

from __future__ import annotations

from ..data import leetcode
from ..data.grid import Day
from .streak import StreakWidget


class LeetCodeWidget(StreakWidget):
    """Submission calendar and streaks for a public LeetCode user."""

    widget_name = "leetcode"
    title_text = "LeetCode streak"
    unit = "submissions"

    def fetch_days(self, weeks: int, timeout: float) -> list[Day]:
        """Fetch with the configured per-level submission thresholds."""
        return leetcode.fetch(username=self.username, weeks=weeks, timeout=timeout,
                              thresholds=[int(v) for v in self.section["levels"]])
