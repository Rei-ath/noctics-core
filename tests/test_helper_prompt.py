from __future__ import annotations

import json
from pathlib import Path

import pytest

from central.core import ChatClient


@pytest.mark.usefixtures("tmp_path")
def test_helper_result_injects_system_prompt(monkeypatch):
    captured: dict[str, object] = {}

    def fake_request(self, req):
        payload = json.loads(req.data.decode("utf-8"))
        captured["messages"] = payload["messages"]
        return "ok", {}

    monkeypatch.setattr(ChatClient, "_request_non_streaming", fake_request)

    client = ChatClient(stream=False, enable_logging=False)
    client.process_helper_result("helper text")

    msgs = captured["messages"]
    assert msgs[-2]["role"] == "system"
    assert "Do you want the explanation" in msgs[-2]["content"]
