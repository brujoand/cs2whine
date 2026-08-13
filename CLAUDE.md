# cs2whine

Real-time CS2 coaching via Game State Integration. Python/Flask, ships as a
Windows exe (PyInstaller).

## Hard rules

- **Never push to `main`/`master`.** Feature branch + PR, always. Open the PR,
  report the URL, stop — **only the human merges.**
- **Conventional Commits** (`feat:`, `fix:`, `chore:`, …). Never hand-bump a version.
- **`pre-commit` is the gate.** Run `pre-commit run --files <changed>` before
  declaring a change done, and report the result.
- **`mise` provisions the toolchain** (`mise install`). New worktrees need `mise trust`.
- Plan every non-trivial task. If the plan fails, restart planning.

## Workflow

Default branch is `main`, protected. Auto-release triggers on merge: the version
bump is derived from commit prefixes and `__version__` is injected at build time
by CI — never bump it by hand. Pre-commit runs ruff lint, ruff format, secret
detection, and the conventional-commit check.

## Architecture

- `gsi_server.py` — Flask HTTP server receiving CS2 GSI POST payloads
- `coaching.py` — stateful engine: tracks rounds, detects patterns, emits tips
- `notify.py` — Windows toasts via direct PowerShell (no winotify)
- `setup_gsi.py` — installs/updates the GSI config into the CS2 cfg dir on launch
- `updater.py` — self-updates from GitHub releases on startup (frozen exe only)
- `config.py` — loads `config.json` with defaults
- `gamestate_integration_coach.cfg` — the GSI config pushed to CS2

## Commands

```bash
mise install
uv sync --group dev
uv run python test_coaching.py     # plain assert scripts, NOT pytest — no -k selector
uv run python test_console_log.py
uv run pyinstaller cs2whine.spec   # build the Windows exe
python simulate.py                 # exercise the engine without CS2 running
pre-commit run --files <changed files>   # NOT the commit-msg stage
git config core.hooksPath .githooks      # once per clone: makes both gates live
```

## Gotchas

- **Tests are plain scripts, not pytest.** Run a whole file; there is no test
  selector.
- The GSI config is compared by content on launch and overwritten if changed — if
  its format changes, update the comparison in `setup_gsi.py`.
- `__version__` in `updater.py` is injected at build time by CI, not committed.
- Notifications shell out to PowerShell via `subprocess.run`; errors print to the
  console rather than raising.
- Coaching tips are emitted once per round via the `emitted_tips` set, cleared on
  each new round.
- `.claude/` is gitignored here on purpose. Personal, untracked notes belong in
  `CLAUDE.local.md`; this file is the shared, tracked one.
