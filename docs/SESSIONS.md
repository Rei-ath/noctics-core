# Session Vault Manual (core)

Nox Core logs every turn when ChatClient logging is enabled (the core CLI does
this by default). Session tooling lives in the `noxl` package.

## Where everything lives
- Default root: `~/.local/share/noctics/memory` (or `XDG_DATA_HOME`).
- Override with `NOCTICS_DATA_ROOT` or `NOCTICS_MEMORY_HOME`.
- If the preferred root is not writable, the repo `memory/` directory is used.
- Legacy repo sessions are migrated on first run.

Layout overview:
```
memory/
  sessions/YYYY-MM-DD/session-*.jsonl
  sessions/YYYY-MM-DD/session-*.meta.json
  early-archives/
  users/<user-id>/user.json
  users/<user-id>/sessions/YYYY-MM-DD/session-*.jsonl
```

## File anatomy
- `session-*.jsonl` -> turn-by-turn log
- `session-*.meta.json` -> metadata (id, title, created/updated, user info)
- `day.json` -> optional day rollup (written by `append_session_to_day_log`)

## Titles and naming
- Auto-title uses the first meaningful user message.
- Rename with `noxl rename` or `noxl merge --title ...`.
- Programmatic: `ChatClient.set_session_title(...)`.

## Listing, loading, archiving (noxl)
```bash
noxl list
noxl list --search "instrument" --limit 10
noxl latest
noxl latest --json
noxl show session-20250101-010203
noxl show session-20250101-010203 --raw
noxl rename session-20250101-010203 "Prod Outage Retro"
noxl merge session-A session-B --title "Combo Tape"
noxl archive
noxl archive --keep-sources
noxl meta session-20250101-010203
noxl count --search "latency"
```

Compatibility flags also exist:
```bash
noxl --show session-20250101-010203
noxl --latest
```

Use `--root PATH` on any command to point at alternate directories. `noxl` will
also detect per-user stores under `memory/users/` automatically.

## Programmatic utilities
```python
from noxl import list_sessions, load_session_messages, compute_title_from_messages
```

## Day rollups
If you want `day.json` summaries, call:
```python
from noxl import append_session_to_day_log
append_session_to_day_log(log_path)
```

## Telemetry
CLI run metrics (if enabled by the wrapper) live in
`memory/telemetry/metrics.json`. The core itself does not upload anything.
