# Sessions & Titles

Central logs every session to JSONL and writes a companion meta file that tracks title and other metadata.

## Files

- `memory/sessions/YYYY-MM-DD/session-*.jsonl`: each line is a compact record of a turn
- `memory/sessions/YYYY-MM-DD/session-*.meta.json`: session metadata (id, path, turns, created, updated, title, custom)

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
  - Or in chat: `/sessions` or `/ls`
- Load a session as the starting context:
  - `python main.py --sessions-load session-YYYYMMDD-HHMMSS`
  - Or in chat: `/load session-YYYYMMDD-HHMMSS`

Notes:
- Loading reconstructs the conversation and starts a new live session; it does not append to the old file.
- Meta files are updated on every turn write and when titles change.

