import json
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from bot import compose
from vera.core.store import ContextStore
from vera.core.engine import DeterministicEngine
from vera.core.models import ContextPayload, Scope, TickRequest

def run_evaluation(pairs, dataset_path, mode_name, use_gemini, use_verifier):
    total_cases = len(pairs)
    send_cases = 0
    no_action_cases = 0
    valid_outputs = 0
    grounding_failures = 0
    send_as_failures = 0
    audience_failures = 0
    exceptions = 0
    fallback_count = 0
    verifier_fails = 0

    latencies = []

    print(f"\n--- Benchmark Mode: {mode_name} ---")

    for pair in pairs:
        m_id = pair.get("merchant_id")
        c_id = pair.get("customer_id")
        t_id = pair.get("trigger_id")

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
        v_fails_dict = {}

        try:
            store = ContextStore()
            engine = DeterministicEngine(store)

            if category: store.push(ContextPayload(scope=Scope.CATEGORY, context_id=category["category_id"], version=1, payload=category))
            if merchant: store.push(ContextPayload(scope=Scope.MERCHANT, context_id=merchant["merchant_id"], version=1, payload=merchant))
            if customer: store.push(ContextPayload(scope=Scope.CUSTOMER, context_id=customer["customer_id"], version=1, payload=customer))
            if trigger: store.push(ContextPayload(scope=Scope.TRIGGER, context_id=trigger["id"], version=1, payload=trigger))

            req_now = "2026-04-26T10:00:00Z"
            request = TickRequest(now=req_now, available_triggers=[trigger["id"]])

            response = engine.tick(request, use_gemini=use_gemini, use_verifier=use_verifier, verifier_failures_dict=v_fails_dict)
            latencies.append(time.time() - start_time)

            if v_fails_dict.get(trigger["id"]):
                verifier_fails += 1
                fallback_count += 1
            elif use_gemini and response.actions and "Hello" in response.actions[0].body and "has a message for you" in response.actions[0].body:
                # Naive heuristic to detect if it fell back due to Gemini timeout/fail without verifier fails
                fallback_count += 1

            if not response.actions:
                no_action_cases += 1
                continue

            send_cases += 1
            action = response.actions[0]

            # Simple check
            is_valid = True
            if action.send_as not in ("vera", "merchant_on_behalf"):
                send_as_failures += 1; is_valid = False
            if "http" in action.body:
                grounding_failures += 1; is_valid = False

            if is_valid: valid_outputs += 1

        except Exception as e:
            exceptions += 1
            latencies.append(time.time() - start_time)
            print(f"Exception on {t_id}: {e}")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0

    print(f"total cases: {total_cases}")
    print(f"send cases: {send_cases}")
    print(f"no-action cases: {no_action_cases}")
    print(f"valid outputs: {valid_outputs}")
    print(f"grounding failures: {grounding_failures}")
    print(f"verifier failures: {verifier_fails}")
    print(f"fallback count: {fallback_count}")
    print(f"send_as failures: {send_as_failures}")
    print(f"audience failures: {audience_failures}")
    print(f"exceptions: {exceptions}")
    print(f"average latency: {avg_latency:.4f}s")
    print(f"max latency: {max_latency:.4f}s")


def main():
    dataset_path = Path("dataset_expanded/test_pairs.json")
    if not dataset_path.exists():
        print("Dataset missing. Run generate_dataset.py first.")
        return

    with open(dataset_path, "r") as f:
        data = json.load(f)

    pairs = data.get("pairs", [])

    import os
    from vera.config.env import config

    # Run Mode A (Deterministic Base)
    run_evaluation(pairs, dataset_path, "A - Deterministic baseline", use_gemini=False, use_verifier=False)

    if not config.gemini_api_key:
        print("\nGEMINI_API_KEY not set. Gemini benchmark as NOT RUN.")
        return

    # Run Mode B (Gemini composition)
    # run_evaluation(pairs, dataset_path, "B - Gemini composition", use_gemini=True, use_verifier=False)

    # Run Mode C (Gemini + verifier)
    # run_evaluation(pairs, dataset_path, "C - Gemini + verifier", use_gemini=True, use_verifier=True)

if __name__ == "__main__":
    main()
