# Sessions & Titles

Central logs every session to JSONL and writes a companion meta file that tracks title and other metadata.

## Files

- `memory/sessions/YYYY-MM-DD/session-*.json`: array of turn records (each record mirrors the JSONL format)
- `memory/sessions/YYYY-MM-DD/session-*.meta.json`: session metadata (id, path, turns, created, updated, title, custom)
- `memory/sessions/YYYY-MM-DD/day.json`: aggregate of every session saved that day (deduplicated on session close)

## Titles

- Set a title manually:
  - In chat: `/title My Topic`
  - Non-interactive: `python main.py --sessions-rename session-YYYYMMDD-HHMMSS "My Topic"`
- Auto-title:
  - If no custom title is set, Central derives a short title from the first meaningful user message at the end of the session
- Rename saved sessions:
  - In chat: `/rename session-YYYYMMDD-HHMMSS New Title`
  - Non-interactive: `--sessions-rename ...`

## Listing & Loading

- List with titles:
  - `python main.py --sessions-ls`
  - `python main.py --sessions-latest` (quick summary of the most recent session)
  - Or in chat: `/sessions` or `/ls`
- Show only the most recent session in chat: `/last`
- Pretty-print a session without loading it: `python main.py --sessions-show session-YYYYMMDD-HHMMSS` or `/show ID`
- Interactively browse & view sessions: `python main.py --sessions-browse` or `/browse`
- Archive everything but the latest session into `memory/early-archives/`:
  - `python main.py --sessions-archive-early`
  - Or in chat: `/archive`
- Load a session as the starting context:
  - `python main.py --sessions-load session-YYYYMMDD-HHMMSS`
  - Or in chat: `/load` (interactive picker) or `/load ID`

## Merging

- Combine multiple sessions into a new merged session (keeps first system, concatenates user/assistant pairs):
  - Non-interactive: `python main.py --sessions-merge ID_OR_INDEX [ID_OR_INDEX ...]`
  - Interactive: `/merge ID_OR_INDEX [ID_OR_INDEX ...]`
  - Examples:
    - `python main.py --sessions-merge 1 3`
    - In chat: `/merge session-20250913-234409 session-20250914-010016`

Notes:
- The merged session is saved under `memory/sessions/merged-<date>/` with a meta title like `Merged: A | B | C`.
- You can rename the merged session later with `--sessions-rename` or `/rename`.

Notes:
- Loading reconstructs the conversation and starts a new live session; it does not append to the old file.
- Meta files are updated on every turn write and when titles change.
