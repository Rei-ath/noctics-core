from central.core import ChatClient


def test_describe_target_reports_config(monkeypatch):
    monkeypatch.delenv("CENTRAL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = ChatClient(
        url="http://example.com",
        model="test-model",
        temperature=0.3,
        max_tokens=256,
        stream=True,
        sanitize=True,
        enable_logging=False,
        strip_reasoning=False,
    )

    info = client.describe_target()

    assert info["model"] == "test-model"
    assert info["url"] == "http://example.com"
    assert info["stream"] is True
    assert info["sanitize"] is True
    assert info["strip_reasoning"] is False
    assert info["logging_enabled"] is False
    assert info["has_api_key"] is False
    assert info["temperature"] == 0.3
    assert info["max_tokens"] == 256
