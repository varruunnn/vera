import json
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from bot import compose
from vera.core.store import ContextStore
from vera.core.engine import DeterministicEngine
from vera.core.models import ContextPayload, Scope, TickRequest

def main():
    dataset_path = Path("dataset_expanded/test_pairs.json")
    if not dataset_path.exists():
        print("Dataset missing. Run generate_dataset.py first.")
        return

    with open(dataset_path, "r") as f:
        data = json.load(f)

    pairs = data.get("pairs", [])
    total_cases = len(pairs)
    send_cases = 0
    no_action_cases = 0
    valid_outputs = 0
    grounding_failures = 0
    send_as_failures = 0
    audience_failures = 0
    unsupported_claim_failures = 0
    exceptions = 0

    latencies = []

    print("\n--- Diagnostic Evaluation ---\n")

    for pair in pairs:
        m_id = pair.get("merchant_id")
        c_id = pair.get("customer_id")
        t_id = pair.get("trigger_id")

        # Load contexts
        merchant, customer, trigger = None, None, None
        if m_id:
            m_path = dataset_path.parent / "merchants" / f"{m_id}.json"
            if m_path.exists():
                with open(m_path, "r") as f: merchant = json.load(f)
        if c_id:
            c_path = dataset_path.parent / "customers" / f"{c_id}.json"
            if c_path.exists():
                with open(c_path, "r") as f: customer = json.load(f)
        if t_id:
            t_path = dataset_path.parent / "triggers" / f"{t_id}.json"
            if t_path.exists():
                with open(t_path, "r") as f:
                    trigger = json.load(f)
                    trigger["id"] = t_id

        category = {"category_id": merchant.get("category_slug", "unknown"), "name": "Dummy"} if merchant else None

        start_time = time.time()

        try:
            # We explicitly recreate engine loop here to capture internal decision details which compose() strips.
            store = ContextStore()
            engine = DeterministicEngine(store)

            if category: store.push(ContextPayload(scope=Scope.CATEGORY, context_id=category["category_id"], version=1, payload=category))
            if merchant: store.push(ContextPayload(scope=Scope.MERCHANT, context_id=merchant["merchant_id"], version=1, payload=merchant))
            if customer: store.push(ContextPayload(scope=Scope.CUSTOMER, context_id=customer["customer_id"], version=1, payload=customer))
            if trigger: store.push(ContextPayload(scope=Scope.TRIGGER, context_id=trigger["id"], version=1, payload=trigger))

            req_now = "2026-04-26T10:00:00Z"

            # Extract Evidence & Evaluate Decision manually for diagnostics
            trigger_ctx = engine.store.get(Scope.TRIGGER, t_id)
            if trigger_ctx:
                from vera.core.models import TriggerContext
                t_ctx_model = TriggerContext(**trigger_ctx.payload)
                evidence = engine._extract_evidence(t_ctx_model, req_now)
                decision = engine._evaluate(t_id, evidence)
                action = engine._generate_action(decision)

                latencies.append(time.time() - start_time)

                print(f"CASE: {t_id}")
                print(f"Category: {category['category_id'] if category else 'None'}")
                print(f"Merchant: {merchant['merchant_id'] if merchant else 'None'}")
                print(f"Customer: {customer['customer_id'] if customer else 'None'}")
                print(f"Trigger Kind/Scope: {t_ctx_model.kind} / {t_ctx_model.scope}")
                print(f"Decision Should Act: {decision.should_act}")
                print(f"Reason: {decision.reason}")
                print(f"Evidence count: {len(decision.evidence.items)}")
                print(f"Evidence sources: {', '.join(list(set(e.source_domain for e in decision.evidence.items)))}")

                if decision.should_act and action:
                    send_cases += 1
                    print(f"Action Type: {decision.intent.action_type if decision.intent else 'None'}")
                    print(f"Audience: {decision.intent.audience if decision.intent else 'None'}")
                    print(f"Send As: {action.send_as}")

                    is_valid = True
                    # Simple rule checks
                    if action.send_as not in ("vera", "merchant_on_behalf"):
                        send_as_failures += 1; is_valid = False
                    if decision.intent and decision.intent.audience == "customer" and action.send_as != "merchant_on_behalf":
                        audience_failures += 1; is_valid = False
                    if "http" in action.body:
                        grounding_failures += 1; is_valid = False

                    if is_valid: valid_outputs += 1
                else:
                    no_action_cases += 1

                print("-" * 40)

        except Exception as e:
            exceptions += 1
            latencies.append(time.time() - start_time)
            print(f"Exception on {t_id}: {e}")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0

    print("\n--- Baseline Evaluation Results ---")
    print(f"total cases: {total_cases}")
    print(f"send cases: {send_cases}")
    print(f"no-action cases: {no_action_cases}")
    print(f"valid outputs: {valid_outputs}")
    print(f"grounding failures: {grounding_failures}")
    print(f"send_as failures: {send_as_failures}")
    print(f"audience failures: {audience_failures}")
    print(f"unsupported-claim failures: {unsupported_claim_failures}")
    print(f"exceptions: {exceptions}")
    print(f"average latency: {avg_latency:.4f}s")
    print(f"max latency: {max_latency:.4f}s")

if __name__ == "__main__":
    main()
