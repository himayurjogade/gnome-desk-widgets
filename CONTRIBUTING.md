# Contributing

Thanks for looking. Small, focused pull requests are easiest to review.

## Setup

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 fonts-jetbrains-mono
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## Ground rules

- **Nothing hardcoded.** Colours, sizes, fonts, intervals and usernames come
  from `config/`. Default configs ship placeholder usernames, never real ones.
- **Separate data from drawing.** Parsing, streak maths and grid layout live in
  `src/desk_widgets/data/` as pure functions with tests; `widgets/` only draws.
- **No blocking the UI thread.** Network calls run in a background thread, have
  a timeout, cache their last good result and degrade to a "stale" label.
- **Validate config.** A bad value falls back to the default and logs a warning
  that names the option. Never raise on user input.
- **Accessibility is not optional.** Keep WCAG AA contrast, keep an
  accessible label on every window and value, never signal with colour alone.
- Type hints and short docstrings. `ruff check .` must pass.
- Keep it small. The smallest change that works is the right one.

## Adding a widget

See "Add a new widget" in the README, and add tests for any new parsing or
maths under `tests/`.

## Commits

One logical change per commit, present tense ("add ring gauge"). Say in the PR
what you ran to check it.
