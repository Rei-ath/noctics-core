from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from interfaces.session_logger import SessionLogger, format_session_display_name


def test_session_logger_creates_files_and_updates_meta(tmp_path: Path):
    logger = SessionLogger(model="test-model", sanitized=True, dirpath=tmp_path)
    logger.start()

    log_path = logger.log_path()
    meta_path = logger.meta_path()
    assert log_path is not None and log_path.exists()
    assert meta_path is not None and meta_path.exists()

    # Log one turn; verify meta updates
    logger.log_turn(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    )
    meta1 = logger.get_meta()
    assert meta1.get("turns") == 1
    assert meta1.get("model") == "test-model"
    assert meta1.get("sanitized") is True
    assert meta1.get("file_name").endswith(".json")
    session_id = meta1.get("id")
    assert session_id is not None
    assert meta1.get("display_name") == format_session_display_name(session_id)

    # Set a title and ensure it persists in meta
    logger.set_title("My Title", custom=True)
    meta2 = logger.get_meta()
    assert meta2.get("title") == "My Title"
    assert meta2.get("custom") is True
    assert meta2.get("display_name") == meta1.get("display_name")

    # Ensure JSONL record also carries the file/display metadata
    data = json.loads(log_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    meta_entry = data[0].get("meta", {})
    assert meta_entry.get("file_name") == log_path.name
    assert meta_entry.get("display_name") == meta1.get("display_name")
