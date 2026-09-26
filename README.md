# Vera AI Challenge Submission

Vera is a deterministic merchant engagement engine built for the magicpin AI Challenge. It receives structured context (category, merchant, customer, trigger) via an HTTP API, constructs hierarchical evidence, applies rule-based decision logic, and produces outreach actions or conversation replies. A deterministic decision core handles all business logic: audience selection, send/no-action decisions, conversation state management, and safety gates. An optional Gemini-based language composer can enhance message copy when available, but all decisions remain deterministic regardless of LLM availability.

## Architecture

```
Context Push (/v1/context)
        |
        v
  ContextStore (in-memory, versioned, thread-safe)
        |
        v
  Tick (/v1/tick)  or  Reply (/v1/reply)
        |                    |
        v                    v
  _extract_evidence()    IntentClassifier (regex-based)
        |                    |
        v                    v
  DecisionEvidenceSet    ConversationState update
  (hierarchical:              |
   trigger, merchant,         v
   customer, category,   _extract_evidence()
   conversation)              |
        |                     |
        +----------+----------+
                   |
                   v
            _evaluate() — deterministic decision engine
                   |
                   v
            Decision (should_act, reason, intent, strategy)
                   |
                   v
            _generate_action() — deterministic message composition
                   |           (optional: GeminiComposer + OutputVerifier)
                   v
            Action / ReplyResponse
```

**Key modules:**

| Module | Purpose |
|---|---|
| `store.py` | Thread-safe in-memory context store with version enforcement |
| `evidence.py` | Typed evidence items (`RAW_FACT`, `DERIVED_FACT`) with domain ownership |
| `engine.py` | Core decision engine: evidence extraction, evaluation, action generation |
| `classifier.py` | Deterministic regex-based intent classifier for conversation replies |
| `decision.py` | `Decision`, `ActionIntent`, `MessageStrategy` data structures |
| `composer.py` | Optional Gemini-based language composer (lazy-loaded, fallback-safe) |
| `verifier.py` | Output verifier that rejects invented URLs, numbers, and dates |
| `models.py` | Pydantic models for all API request/response schemas and state |

## Project Structure

```
vera/
├── bot.py                          # Offline compose() entry point
├── pyproject.toml                  # Project metadata and dependencies
├── .env.example                    # Environment variable template
├── .gitignore
├── README.md
│
├── src/vera/
│   ├── adapters/
│   │   └── fastapi_app.py          # FastAPI HTTP adapter (5 endpoints)
│   ├── config/
│   │   └── env.py                  # .env loader and config singleton
│   └── core/
│       ├── engine.py               # Deterministic decision engine
│       ├── store.py                # In-memory versioned context store
│       ├── evidence.py             # Evidence types and evidence set
│       ├── decision.py             # Decision, ActionIntent, MessageStrategy
│       ├── classifier.py           # Regex-based intent classifier
│       ├── composer.py             # Optional Gemini composer
│       ├── verifier.py             # Output verification / policy gate
│       └── models.py              # Pydantic schemas (API + state)
│
├── tests/
│   ├── adapters/test_api.py        # HTTP endpoint contract tests
│   ├── core/
│   │   ├── test_baseline.py        # Canonical 30-pair baseline tests
│   │   ├── test_conversation.py    # Conversation state machine tests
│   │   ├── test_adversarial.py     # Adversarial intent + safety gate tests
│   │   ├── test_hygiene.py         # Evidence ownership + grounding tests
│   │   └── test_gemini_integration.py  # Gemini composer integration tests
│   └── contract/                   # Contract schema validation tests
│
├── tools/
│   ├── evaluate_baseline.py        # Run deterministic baseline over 30 canonical pairs
│   ├── replay_conversations.py     # Multi-turn conversation state replay
│   └── run_gemini_experiment.py    # A/B/C Gemini vs deterministic benchmark
│
└── challenge/                      # Official challenge materials (read-only reference)
    ├── challenge-brief.md
    ├── challenge-testing-brief.md
    ├── engagement-design.md
    ├── engagement-research.md
    ├── examples/api-call-examples.md
    ├── judge_simulator.py
    └── dataset/                    # Seed data (categories, merchants, customers, triggers)
```

## Requirements

- Python 3.10 or higher
- Dependencies defined in `pyproject.toml`:
  - `pydantic>=2.0.0`
  - `fastapi>=0.100.0`
  - `uvicorn>=0.23.0`
  - `google-genai` (used only when Gemini composition is enabled)
- Dev dependencies: `pytest>=7.0.0`, `httpx>=0.24.0`

## Setup

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Environment Variables

Copy the template and fill in your key:

```powershell
copy .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | No | Google Gemini API key. Only required when Gemini composition mode is enabled. The deterministic baseline operates without it. |

The `.env` file is gitignored. Never commit API keys to the repository.

## Run the API

Start the FastAPI server locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn vera.adapters.fastapi_app:app --host 0.0.0.0 --port 8080
```

The server will be available at `http://127.0.0.1:8080`.

The application module path is `vera.adapters.fastapi_app:app`. The `pythonpath` is configured in `pyproject.toml` to include `src/`.

For deployment to a hosted platform, bind to `0.0.0.0` and configure the port via the `--port` flag.

## API Endpoints

### `GET /v1/healthz`

Liveness probe. Returns `200` with `{"status": "ok"}`.

### `GET /v1/metadata`

Bot identity. Returns `200` with name and version:

```json
{"name": "Vera Baseline", "version": "0.1.0"}
```

### `POST /v1/context`

Receives context pushes from the judge (category, merchant, customer, trigger payloads).

**Request:**
```json
{
  "scope": "merchant",
  "context_id": "m_001",
  "version": 1,
  "payload": {
    "merchant_id": "m_001",
    "name": "Dr. Meera's Dental Clinic",
    "subscription": {"status": "active"}
  }
}
```

**Success (200):**
```json
{"accepted": true, "ack_id": "ack_m_001_v1", "stored_at": "2026-04-26T10:00:00.123456+00:00"}
```

**Version conflict (409):**
```json
{"accepted": false, "reason": "stale_version", "current_version": 2}
```

### `POST /v1/tick`

Periodic evaluation. The bot inspects available triggers and decides whether to initiate outreach.

**Request:**
```json
{
  "now": "2026-04-26T10:00:00Z",
  "available_triggers": ["trg_001", "trg_002"]
}
```

**Response (200):**
```json
{
  "actions": [
    {
      "conversation_id": "conv_m_001_trg_001",
      "merchant_id": "m_001",
      "customer_id": null,
      "send_as": "vera",
      "trigger_id": "trg_001",
      "body": "...",
      "cta": "...",
      "suppression_key": "...",
      "rationale": "..."
    }
  ]
}
```

The `actions` array may be empty if no triggers warrant outreach.

### `POST /v1/reply`

Receives a merchant or customer reply to a previous bot message. The bot classifies the intent, updates conversation state, and responds.

**Request:**
```json
{
  "conversation_id": "conv_m_001_trg_001",
  "merchant_id": "m_001",
  "from_role": "merchant",
  "message": "yes proceed",
  "turn_number": 2
}
```

**Response (200):** one of three actions:

```json
{"action": "send", "body": "Executing your request now.", "rationale": "Execute requested action"}
```
```json
{"action": "wait", "wait_seconds": 86400, "rationale": "Received question, pausing outreach"}
```
```json
{"action": "end", "rationale": "User opted out"}
```

## Context Versioning

The `ContextStore` enforces monotonically increasing versions per `(scope, context_id)` pair:

- A push with a **higher version** than the stored version replaces the stored context. Returns `200` with `accepted: true`.
- A push with a version **equal to or lower than** the stored version is rejected. Returns `409` with `reason: "stale_version"` and the `current_version`.
- The first push for any `(scope, context_id)` is always accepted.

## Conversation Behavior

The `/v1/reply` endpoint implements a deterministic conversation state machine. Each conversation is scoped by `conversation_id` and tracked independently in the context store.

### Intent Classification

The `IntentClassifier` uses ordered regex rules. Classification priority (highest first):

| Intent | Triggers on | Engine behavior |
|---|---|---|
| `OPT_OUT` | "stop", "unsubscribe", "cancel", "opt out" | Terminal `end` action. State becomes `OPTED_OUT`. |
| `NEGATIVE_INTENT` | "no", "not interested", "never" | `wait`. Pauses outreach. |
| `UNCERTAINTY` | "maybe", "not sure", "might", "perhaps" | `wait`. Pauses outreach. |
| `QUESTION` | Contains `?`, or "what", "how", "why", etc. | `wait`. Pauses outreach. |
| `CONDITIONAL_POSITIVE_INTENT` | Positive keyword + "if", "but", "provided", "only if" | `wait`. State becomes `QUALIFYING`. Execution blocked until condition resolved. |
| `POSITIVE_INTENT` | "yes", "proceed", "go ahead", "sounds good" | `send` with execution. |
| `ACTION_REQUEST` | Positive + specific action verb with "can you" | `send` with execution. |
| `OTHER` | No pattern matched | `wait` if conversation is already engaged. |

### Execution Hard Gate

Before any `execute_action` decision is emitted, the engine checks:

- No unresolved condition/constraint (`has_unresolved_condition` flag)
- No active opt-out
- Trigger is not expired
- Merchant context exists and subscription is active
- Customer consent is present (for customer-scoped triggers)

If any gate fails, the engine returns `wait` (or `end` for opt-out) instead of executing.

### Repeated Reply Suppression

Auto-reply detection is based on **exact message repetition**, not phrase matching. If the current reply is identical to the previous reply (`consecutive_similar_replies >= 1`), the intent is overridden to `AUTO_REPLY` and the state transitions to `WAITING`. A single occurrence of any message is never classified as an auto-reply regardless of its content.

## Offline / Deterministic Evaluation

### Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### Run Canonical Baseline (30 pairs)

```powershell
.\.venv\Scripts\python.exe tools/evaluate_baseline.py
```

Evaluates the deterministic engine against all 30 canonical (merchant, trigger) pairs from the seed dataset. Reports send/no-action counts, grounding failures, and latency.

### Run Conversation Replay

```powershell
.\.venv\Scripts\python.exe tools/replay_conversations.py
```

Steps through a multi-turn conversation scenario and reports intent classification, state transitions, and actions at each turn.

### Offline compose()

The `bot.py` module provides `compose(category, merchant, trigger, customer=None)` for direct offline evaluation without HTTP:

```python
from bot import compose
result = compose(category_dict, merchant_dict, trigger_dict)
```

## Validation

Current verified results (as of latest commit):

| Metric | Result |
|---|---|
| pytest | 48 passed |
| Canonical send cases | 26 |
| Canonical no-action cases | 4 |
| Grounding failures | 0 |
| Audience violations | 0 |
| send_as violations | 0 |
| Exceptions | 0 |
| Average deterministic latency | 0.0001s |
| Max deterministic latency | 0.0007s |

The official LLM judge (`challenge/judge_simulator.py`) was not run because the configured Gemini free-tier quota is exhausted (HTTP 429). The judge requires a working Gemini API key to function.

## Deployment

To deploy to a hosted environment:

1. **Install dependencies:**
   ```bash
   pip install -e .
   ```

2. **Set environment variables** on the host:
   - `GEMINI_API_KEY` (optional, only for Gemini composition mode)

3. **Start command:**
   ```bash
   uvicorn vera.adapters.fastapi_app:app --host 0.0.0.0 --port $PORT
   ```

   The port is passed via the `--port` CLI flag. On platforms like Render that set a `PORT` environment variable, use `$PORT` directly in the start command.

   For local development:
   ```bash
   uvicorn vera.adapters.fastapi_app:app --host 0.0.0.0 --port 8080
   ```

### Render

| Setting | Value |
|---|---|
| Build Command | `pip install -e .` |
| Start Command | `uvicorn vera.adapters.fastapi_app:app --host 0.0.0.0 --port $PORT` |
| Environment | `GEMINI_API_KEY` (optional) |

4. **PYTHONPATH:** Ensure `src/` is on the Python path. This is configured automatically when installed via `pip install -e .` using the `[tool.pytest.ini_options] pythonpath` setting in `pyproject.toml`.

## Security / Secrets

- `.env` is listed in `.gitignore` and must never be committed.
- API keys must not appear in source code, test output, logs, or HTTP responses.
- The deterministic engine operates fully without `GEMINI_API_KEY`. Gemini is lazy-loaded only when explicitly enabled.
- No internal evidence, prompts, or raw Gemini output is exposed in API responses.

## Known Limitations

- **Repeated-reply detection uses strict string equality.** If an automated reply varies per occurrence (e.g., appends a timestamp), the loop suppression will not trigger. This is an intentional conservative boundary; false negatives (missing a loop) are preferred over false positives (misclassifying human replies).
- **Output verification is deterministic and rule-based.** The verifier catches invented URLs and unsupported numeric/date claims, but cannot detect nuanced contextual hallucinations (e.g., subtle misattributions of research findings) without LLM assistance.
- **Gemini composition is currently unavailable** due to free-tier quota exhaustion. The system falls back to deterministic template-based composition automatically.

## Submission Checklist

```
[ ] Clone repository
[ ] Create .venv and install dependencies
[ ] Create .env from .env.example (optional for baseline)
[ ] Run tests:                    python -m pytest
[ ] Run baseline:                 python tools/evaluate_baseline.py
[ ] Run conversation replay:      python tools/replay_conversations.py
[ ] Start API:                    uvicorn vera.adapters.fastapi_app:app --host 0.0.0.0 --port 8080
[ ] Verify health:                GET /v1/healthz returns {"status": "ok"}
[ ] Verify .env is not tracked:   git status shows .env as untracked or absent
[ ] Verify repository is clean:   git status shows no uncommitted changes
```
