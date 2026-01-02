# Inference Runtime (core)

This section documents how Nox Core builds payloads and talks to inference
endpoints. The relevant code lives in:
- `central/core/payloads.py` (payload construction + env-based options)
- `central/transport.py` (HTTP transport + streaming)
- `central/core/client.py` (OpenAI adapter + target model selection)
- `scripts/nox.run` (local Ollama bootstrap)
- `inference/ollama` (bundled Ollama binary used by the script)

## Endpoint modes
Nox detects the URL path and shapes requests accordingly:
- `/api/generate` (Ollama generate): payload uses `prompt` and `system` and
  the transport drops `messages` before sending.
- `/api/chat` (Ollama chat): payload uses `messages` and the transport drops
  `prompt` and `system` before sending.
- Other URLs: payload is sent as-is and streaming uses SSE framing.

## Response shape expectations
- `/api/generate` expects JSON lines with a `response` field (plus optional
  `error`). Responses are concatenated in order.
- `/api/chat` expects JSON with `message.content` (or `response` as a fallback).
- Other URLs (non-stream) expect OpenAI-style JSON with
  `choices[0].message.content`. If that key is missing, the reply is `None`.
- Other URLs (streaming) expect SSE frames whose `data:` payload is either raw
  text or JSON with `choices[0].delta.content`, `choices[0].message.content`,
  or `choices[0].text`.

## Payload construction
`build_payload(...)` builds a unified payload that works with both `/api/chat`
and `/api/generate`:
- System prompt = concatenation of all `system` messages.
- Prompt = last 3 user/assistant exchanges (up to 6 messages) formatted as:
  `<|user|>...` and `<|assistant|>...`, always ending with `<|assistant|>`.
- `messages` are included for chat-style endpoints.
- `options` are injected from environment variables (see below).

### Inference tuning env vars
These are read when building the payload:
- `NOX_NUM_THREADS` or `NOX_NUM_THREAD` -> `options.num_thread`
- `NOX_NUM_THREADS_CAP` -> caps detected CPU count (default cap 6 on Termux)
- `NOX_NUM_CTX`, `NOX_CONTEXT_LENGTH`, `NOX_CONTEXT_LEN`, `OLLAMA_CONTEXT_LENGTH`
  -> `options.num_ctx`
- `NOX_NUM_BATCH` -> `options.num_batch`
- `NOX_KEEP_ALIVE`, `NOX_OLLAMA_KEEP_ALIVE`, `OLLAMA_KEEP_ALIVE` -> `keep_alive`
- `NOX_NUM_PREDICT` is not used; `max_tokens` maps to `options.num_predict`

## Authentication header
If `NOX_LLM_API_KEY` (or `OPENAI_API_KEY`) is set, requests include
`Authorization: Bearer <key>` for all endpoints.

## OpenAI endpoint adapter
If the URL contains `openai.com`, ChatClient rewrites the payload to an OpenAI
style request:
- `model` becomes the selected target model.
- `messages` are flattened to `{role, content}` strings.
- `temperature`, `max_tokens`, and `stream` are passed through.

Target model selection:
- `NOX_TARGET_MODEL` overrides everything.
- If the base model is `nox` or `gpt-5`, it maps to `NOX_OPENAI_MODEL` (default
  `gpt-4o-mini`).

## Streaming behavior
`LLMTransport.send(...)` chooses a streaming parser based on URL:
- `/api/generate`: reads JSON lines and concatenates `response` fields.
- `/api/chat`: reads JSON lines and concatenates `message.content` or `response`.
- Other URLs: reads SSE frames (`data:`) and concatenates deltas.

ChatClient can strip `<think>...</think>` while streaming when
`strip_reasoning=True` (default). It buffers raw output, surfaces only the
public segments, and cleans auxiliary blocks before logging.

## Local Ollama bootstrap (`scripts/nox.run`)
The helper script provides a local-first inference loop:
1. Creates or reuses `.venv`, then installs `requirements.txt`.
2. Ensures the `inference/ollama` binary exists:
   - If missing, it clones `OLLAMA_REPO_URL` into `inference/ollama-mini` and
     copies the `ollama` binary into `inference/ollama`.
3. Starts `ollama serve` on `OLLAMA_HOST` (default `127.0.0.1:11434`).
4. Polls `http://$OLLAMA_HOST/api/version` until the server is live.
5. Ensures the model is available:
   - Uses `ollama list` to check for the model.
   - Falls back to `ollama pull`.
   - If a `models/ModelFile` exists, tries `ollama create`.
6. Launches `python main.py --stream --show-think --url ... --model ...`.

Script-specific env vars:
- `MODEL_NAME` sets the default model name.
- `NOX_MODEL` overrides the model pulled/created.
- `NOX_LLM_URL_OVERRIDE` and `NOX_LLM_MODEL_OVERRIDE` override runtime values.
- `OLLAMA_REPO_URL` points to the repo that contains the Ollama binary.
- `OLLAMA_HOST` sets the local serve host/port.
- `OLLAMA_MODELS` is set to `models/` under the repo root.

## Model listing helper
The core CLI can list installed model aliases with `--list-models`. It resolves
`ollama` in this order:
1. `OLLAMA_BIN` (explicit path or binary name)
2. `ollama` in `PATH`
3. `assets/ollama/bin/ollama`

## Minimal usage examples
Local Ollama chat:
```bash
export NOX_LLM_URL=http://127.0.0.1:11434/api/chat
export NOX_LLM_MODEL=nox
python main.py --stream
```

Local Ollama generate:
```bash
export NOX_LLM_URL=http://127.0.0.1:11434/api/generate
export NOX_LLM_MODEL=nox
python main.py --stream
```

Hosted OpenAI-compatible:
```bash
export NOX_LLM_URL=https://api.openai.com/v1/chat/completions
export NOX_LLM_MODEL=nox
export NOX_LLM_API_KEY=...
export NOX_OPENAI_MODEL=gpt-4o-mini
python main.py --stream
```
