# Vera Contract Notes

This document captures the external contract expectations from the official challenge material.

## Overview
The architecture is structured around 5 endpoints:
- `GET /v1/healthz`: Health check, budget 2s.
- `GET /v1/metadata`: Returns metadata about the bot, budget 2s.
- `POST /v1/context`: Pushes context data (Categories, Merchants, Customers, Triggers), budget 5s.
- `POST /v1/tick`: Polls for candidate actions given available triggers, budget 10s.
- `POST /v1/reply`: Sends a user reply and returns an action, budget 10s.

## Constraints & Behaviors

### 1. Context Identity & Versioning
- Contexts are uniquely identified by `(scope, context_id)`.
- Re-pushing a context with a strictly newer version *atomically replaces* the previous context.
- Pushing a context with an older or *identical* version must be rejected.
- Format for rejection (HTTP 409 Conflict):
  ```json
  {
    "accepted": false,
    "reason": "stale_version",
    "current_version": <version>
  }
  ```
  *(Note: This executable behavior overrides any higher-level wording suggesting same-version acceptance).*

### 2. `/v1/tick` Behavior
- May legitimately return no actions: `{"actions": []}`
- Emits candidate actions. Each action must contain:
  - `conversation_id`
  - `merchant_id`
  - `customer_id`
  - `send_as`
  - `trigger_id`
  - `template_name`
  - `template_params`
  - `body`
  - `cta`
  - `suppression_key`
  - `rationale`

### 3. Messaging Conventions
- **Customer-facing**: `send_as = merchant_on_behalf`
- **Merchant-facing**: `send_as = vera`
- No URLs are allowed in the generated message bodies. This is a hard failure (results in -3 penalty).

### 4. `/v1/reply` Behavior
- Expected to return one of the following terminal states:
  - `send`
  - `wait`
  - `end`

### 5. Architectural Non-Negotiables
- The live judge has tight latency requirements (e.g., 10s for ticks).
- Must avoid long-running, uncontrolled model calls.
- There are four main context scopes:
  - `CategoryContext`
  - `MerchantContext`
  - `CustomerContext`
  - `TriggerContext`
- There should be ONE core logic shared between offline `bot.py compose()` and the FastAPI webserver `/v1/*`.
- Deterministic systems own routing, context selection, constraints, rejection, deadlines, policies, etc. Gemini is strictly an engine part, not the architecture itself.
