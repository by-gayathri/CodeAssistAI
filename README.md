# CodeAssistAI

LLM-based code review assistant. Submit source code through a FastAPI service and receive structured findings covering logic, readability, security, performance, testing, and related quality concerns.

## Features

- `POST /api/v1/reviews` — structured code review with severity filtering
- `GET /api/v1/reviews/{review_id}` — fetch a previous review (in-memory, development only)
- `POST /api/v1/reviews/{review_id}/feedback` — store feedback on findings
- `GET /health` — service health
- Pluggable providers: **mock** (default), Hugging Face **transformer**, OpenAI-compatible **external** LLM
- Prompt templates with anti-prompt-injection guidance
- Lightweight Python static analysis (AST syntax + pattern checks)
- Evaluation dataset and metrics CLI
- Docker, pytest suite, and GitHub Actions CI

## Architecture

```
Client → FastAPI routes → ReviewService
                           ├─ PromptService
                           ├─ ReviewModelProvider (mock | transformer | external)
                           ├─ ParserService
                           ├─ StaticAnalysisService
                           └─ ReviewRepository (in-memory)
```

Submitted code is treated as untrusted input and is **never executed**.

## Technology stack

| Area | Choice |
|------|--------|
| Language | Python 3.11+ |
| API | FastAPI + Pydantic |
| Models | Mock / Hugging Face Transformers + PyTorch / OpenAI-compatible HTTP |
| Tests | pytest + TestClient |
| Quality | Ruff, Black, optional mypy |
| Ops | Docker, GitHub Actions |

## Repository structure

```
app/                 FastAPI application, services, providers, prompts
evaluation/          Dataset, metrics, CLI runner
tests/               Unit and integration tests
examples/            Sample HTTP requests
Dockerfile           Container image (mock provider by default)
.github/workflows/   CI pipeline
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open interactive docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Docker

```bash
docker build -t codeassistai .
docker run -p 8000:8000 codeassistai
# or
docker compose up --build
```

The container starts with `PROVIDER=mock` and does not require API keys or a GPU.

## Environment variables

See [`.env.example`](.env.example). Important settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROVIDER` | `mock` | `mock`, `transformer`, or `external` |
| `MAX_CODE_LENGTH` | `50000` | Maximum accepted code size |
| `TRANSFORMER_MODEL_NAME` | `Salesforce/codegen-350M-mono` | HF model when `PROVIDER=transformer` |
| `TRANSFORMER_DEVICE` | `cpu` | Device for transformer inference |
| `EXTERNAL_LLM_API_KEY` | _(empty)_ | Required when `PROVIDER=external` |
| `EXTERNAL_LLM_BASE_URL` | OpenAI URL | OpenAI-compatible base URL |
| `EXTERNAL_LLM_MODEL` | `gpt-4o-mini` | External model name |

Never hardcode secrets. API keys are loaded only from the environment.

## API usage

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/api/v1/reviews \
  -H 'Content-Type: application/json' \
  -d '{
    "code": "def divide(a, b):\n    return a / b",
    "language": "python",
    "file_name": "math_utils.py",
    "review_types": ["logic", "readability", "security", "performance", "testing"],
    "severity_threshold": "low",
    "include_summary": true
  }'
```

Supported languages: `python`, `javascript`, `typescript`, `java`, `go`.  
Static analysis currently runs for **Python** only; other languages use the LLM/mock path.

Supported review categories: `logic`, `readability`, `security`, `performance`, `testing`, `maintainability`, `code_quality`.

More examples: [`examples/sample_requests.http`](examples/sample_requests.http).

### Example review response (shape)

```json
{
  "review_id": "review-...",
  "status": "completed",
  "language": "python",
  "summary": {
    "overall_score": 72,
    "risk_level": "medium",
    "overview": "..."
  },
  "findings": [
    {
      "finding_id": "finding-1",
      "category": "logic",
      "severity": "medium",
      "title": "Division by zero is not handled",
      "description": "...",
      "line_start": 2,
      "line_end": 2,
      "confidence": 0.94,
      "source": "llm"
    }
  ],
  "metadata": {
    "provider": "mock",
    "model": "mock-deterministic-v1",
    "duration_ms": 12,
    "created_at": "..."
  }
}
```

## Testing

```bash
export PROVIDER=mock
ruff check .
black --check app evaluation tests
pytest
```

Integration tests override providers via FastAPI dependency/app state and never call external LLM APIs or download transformer weights.

## Evaluation

```bash
python -m evaluation.run_evaluation
# optional:
python -m evaluation.run_evaluation --provider mock --output evaluation/results/latest.json
```

Matching strategy (documented in `evaluation/metrics.py`): category membership plus severity proximity and/or token Jaccard similarity against the expected issue description. Metrics include precision, recall, category accuracy, severity agreement, duplicate rate, JSON validity, latency, and provider failure rate.

**Do not treat mock-provider scores as production LLM quality.** Re-run evaluation when switching providers and report only measured results.

## CI pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR:

1. Install dependencies  
2. `ruff check .`  
3. `black --check`  
4. `pytest` with `PROVIDER=mock`  
5. `mypy app` (non-blocking)

## Security considerations

- Submitted code is never executed.
- Prompt templates instruct the model to ignore instructions embedded in code/comments.
- API responses do not expose API keys, full prompts, stack traces, or internal configuration.
- Structured logs avoid full source code and secrets by default.
- In-memory storage is for local development only — not multi-tenant safe or durable.

## Implemented vs planned

| Capability | Status |
|------------|--------|
| FastAPI review + feedback API | Implemented |
| Mock provider (default) | Implemented |
| Transformer provider (CPU, lazy load) | Implemented (requires model download when enabled) |
| External OpenAI-compatible provider | Implemented (requires API key when enabled) |
| In-memory repository | Implemented (dev only) |
| Python static analysis | Implemented (lightweight) |
| Evaluation CLI + dataset | Implemented |
| Docker / CI / README | Implemented |
| PostgreSQL persistence | Planned |
| Auth / multi-tenancy | Planned |
| GPU-optimized serving | Not claimed / not implemented |
| Non-Python static analyzers (Ruff/Bandit as services) | Planned enhancement |

## Known limitations

- Reviews are stored in process memory and lost on restart.
- Mock findings are heuristic and deterministic — useful for demos and CI, not a substitute for a strong LLM.
- Transformer quality depends on the configured HF model; small CPU models may produce imperfect JSON (parser fails closed).
- Static analysis coverage is intentionally narrow and Python-only.

## Future improvements

- Durable storage (PostgreSQL) behind the existing repository interface
- Authentication and rate limiting
- Richer static analysis integrations
- Multi-file / diff-based reviews
- Calibration of evaluation matching with human-labeled data
