# cs2whine

Real-time CS2 coaching that runs alongside the game. Uses Valve's Game State Integration to watch your rounds and sends Windows notifications when it spots patterns you should fix.

## What it does

Tracks your gameplay and alerts you about:
- Dying early in repeated rounds
- Dying in the same spot repeatedly
- Loss streaks
- Rounds with no kills
- Bomb site patterns the enemy is exploiting

## Setup

1. Download `cs2whine-<version>.exe` from the [latest release](https://github.com/brujoand/cs2whine/releases/latest)
2. Run it. It automatically installs the GSI config into your CS2 `cfg/` folder
3. Launch CS2 and play. Tips appear as Windows notifications

If CS2 is installed in a non-standard location, the app will tell you to manually copy `gamestate_integration_coach.cfg` to your CS2 `cfg/` directory.

## Configuration

Edit `config.json` next to the exe:

| Key | Default | Description |
|-----|---------|-------------|
| `port` | `3001` | Port the local server listens on |
| `notification_rate_limit` | `8.0` | Minimum seconds between notifications |

## Updates

The app checks for updates on startup and downloads new versions automatically in the background. No action needed.

## VAC Safe

This app only reads game state data through Valve's official GSI API. It never touches game memory, injects code, or modifies game files (other than the GSI config). Same category as stream overlays and RGB integrations.
