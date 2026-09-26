import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot import compose

def main():
    dataset_path = Path("dataset_expanded/test_pairs.json")
    if not dataset_path.exists():
        print("Dataset missing. Run generate_dataset.py first.")
        return

    with open(dataset_path, "r") as f:
        data = json.load(f)

    pairs = data.get("pairs", [])
    total_cases = len(pairs)
    valid_outputs = 0
    no_action_outputs = 0
    invalid_outputs = 0
    grounding_failures = 0
    send_as_failures = 0
    exceptions = 0

    latencies = []

    for pair in pairs:
        m_id = pair.get("merchant_id")
        c_id = pair.get("customer_id")
        t_id = pair.get("trigger_id")

        # Load merchant
        merchant = None
        if m_id:
            m_path = dataset_path.parent / "merchants" / f"{m_id}.json"
            if m_path.exists():
                with open(m_path, "r") as f:
                    merchant = json.load(f)

        # Load customer
        customer = None
        if c_id:
            c_path = dataset_path.parent / "customers" / f"{c_id}.json"
            if c_path.exists():
                with open(c_path, "r") as f:
                    customer = json.load(f)

        # Load trigger
        trigger = None
        if t_id:
            t_path = dataset_path.parent / "triggers" / f"{t_id}.json"
            if t_path.exists():
                with open(t_path, "r") as f:
                    trigger = json.load(f)
                    trigger["trigger_id"] = t_id

        # We need a dummy category since the baseline just needs it for compose
        category = {"category_id": "dummy_cat", "name": "Dummy"}

        start_time = time.time()

        try:
            if not merchant or not trigger:
                no_action_outputs += 1
                continue

            actions = compose(category, merchant, trigger, customer)
            latencies.append(time.time() - start_time)

            if not actions:
                no_action_outputs += 1
                continue

            action = actions[0]

            # Validation
            if "http" in action.get("body", ""):
                grounding_failures += 1
                invalid_outputs += 1
                continue

            if action.get("send_as") not in ("vera", "merchant_on_behalf"):
                send_as_failures += 1
                invalid_outputs += 1
                continue

            if "customer" in trigger.get("kind", "") and action.get("send_as") != "merchant_on_behalf":
                send_as_failures += 1
                invalid_outputs += 1
                continue

            valid_outputs += 1

        except Exception as e:
            exceptions += 1
            latencies.append(time.time() - start_time)
            print(f"Exception on {trigger.get('trigger_id')}: {e}")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0

    print("Baseline Evaluation Results")
    print("---------------------------")
    print(f"total cases: {total_cases}")
    print(f"valid outputs: {valid_outputs}")
    print(f"no-action outputs: {no_action_outputs}")
    print(f"invalid outputs: {invalid_outputs}")
    print(f"grounding failures: {grounding_failures}")
    print(f"send_as failures: {send_as_failures}")
    print(f"exceptions: {exceptions}")
    print(f"average latency: {avg_latency:.4f}s")
    print(f"max latency: {max_latency:.4f}s")

if __name__ == "__main__":
    main()
