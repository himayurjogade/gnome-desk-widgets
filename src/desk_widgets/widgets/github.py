"""GitHub contribution streak widget."""

from __future__ import annotations

from ..data import github
from .streak import StreakWidget


class GitHubWidget(StreakWidget):
    """Contribution grid and streaks for a public GitHub user."""

    widget_name = "github"
    title_text = "GitHub streak"
    unit = "contributions"
    fetcher = staticmethod(github.fetch)
