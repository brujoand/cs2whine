# cs2whine

Real-time CS2 coaching via Game State Integration. Runs as a Windows exe (PyInstaller).

## Workflow

- **Never push directly to main** — branch protection enforced. Always feature branch + PR.
- Conventional commits required: `feat:`, `fix:`, `chore:`, etc.
- Auto-release triggers on merge to main (version bump based on commit prefixes).
- Pre-commit hooks: ruff lint, ruff format, secret detection, conventional commits.

## Dev setup

- `mise install` for tooling (python 3.14, uv, gh, gitleaks)
- `uv sync --group dev` for dependencies
- Tests: `.venv/bin/python test_coaching.py` (plain scripts, not pytest)
- Build: `uv run pyinstaller cs2coach.spec`

## Architecture

- `gsi_server.py` — Flask HTTP server receiving CS2 GSI POST payloads
- `coaching.py` — Stateful coaching engine: tracks rounds, detects patterns, emits tips
- `notify.py` — Windows toast notifications via direct PowerShell (no winotify)
- `setup_gsi.py` — Auto-installs/updates GSI config to CS2 cfg dir on launch
- `updater.py` — Self-update from GitHub releases on startup (frozen exe only)
- `config.py` — Loads config.json with defaults
- `gamestate_integration_coach.cfg` — GSI config pushed to CS2; update `setup_gsi.py` comparison if format changes

## Key details

- GSI config is compared by content on launch and overwritten if changed
- `__version__` in updater.py is injected at build time by CI (not manually bumped)
- Notifications use `subprocess.run` calling PowerShell — errors print to console
- All coaching tips are emitted once per round via `emitted_tips` set (cleared on new round)
