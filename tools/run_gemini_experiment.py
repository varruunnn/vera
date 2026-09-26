import json
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from vera.core.store import ContextStore
from vera.core.engine import DeterministicEngine
from vera.core.models import ContextPayload, Scope, TickRequest

def run_experiment_mode(pairs, dataset_path, mode_name, use_gemini, use_verifier, results_out):
    print(f"\n--- Running Mode: {mode_name} ---")
    
    metrics = {
        "total_cases": len(pairs),
        "send_cases": 0,
        "no_action_cases": 0,
        "valid_outputs": 0,
        "exceptions": 0,
        "gemini_calls": 0,
        "fallback_count": 0,
        "verifier_failures": 0,
        "grounding_failures": 0,
        "url_violations": 0,
        "invented_number_failures": 0,
        "invented_date_failures": 0,
        "latencies": []
    }
    
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
            
            if use_gemini:
                time.sleep(4.1) # Free tier rate limit 10 RPM
                
            response = engine.tick(request, use_gemini=use_gemini, use_verifier=use_verifier, verifier_failures_dict=v_fails_dict)
            latency = time.time() - start_time
            metrics["latencies"].append(latency)
            
            if use_gemini:
                metrics["gemini_calls"] += 1  # 1 call per action attempt
                
            fails = v_fails_dict.get(trigger["id"], [])
            fallback_used = len(fails) > 0
            if fallback_used:
                metrics["fallback_count"] += 1
                if "Composer failed or timed out" not in fails:
                    metrics["verifier_failures"] += 1
                for f in fails:
                    if "URL detected" in f:
                        metrics["url_violations"] += 1
                    elif "Invented number" in f:
                        metrics["invented_number_failures"] += 1
                    elif "Invented year" in f:
                        metrics["invented_date_failures"] += 1
                        
            
            case_result = {
                "case_id": f"{m_id}_{c_id}_{t_id}",
                "trigger_kind": trigger["kind"] if trigger else "unknown",
                "decision": "acted" if response.actions else "no_action",
                "action_no_action": "action" if response.actions else "no_action",
                "body": response.actions[0].body if response.actions else None,
                "cta": response.actions[0].cta if response.actions else None,
                "Gemini_used": use_gemini,
                "fallback_used": fallback_used,
                "verifier_passed": not fallback_used if use_verifier else None,
                "verifier_reason": fails,
                "latency": latency
            }
            results_out[mode_name]["cases"].append(case_result)
            
            if not response.actions:
                metrics["no_action_cases"] += 1
                continue
                
            metrics["send_cases"] += 1
            metrics["valid_outputs"] += 1
                
        except Exception as e:
            metrics["exceptions"] += 1
            metrics["latencies"].append(time.time() - start_time)
            print(f"Exception on {t_id}: {e}")
            
    metrics["avg_latency"] = sum(metrics["latencies"]) / len(metrics["latencies"]) if metrics["latencies"] else 0
    metrics["max_latency"] = max(metrics["latencies"]) if metrics["latencies"] else 0
    s_lats = sorted(metrics["latencies"])
    metrics["p95_latency"] = s_lats[int(len(s_lats) * 0.95)] if s_lats else 0
    
    results_out[mode_name]["metrics"] = metrics

def main():
    dataset_path = Path("dataset_expanded/test_pairs.json")
    if not dataset_path.exists():
        print("Dataset missing.")
        return
        
    with open(dataset_path, "r") as f:
        data = json.load(f)
        
    pairs = data.get("pairs", [])
    
    results = {
        "A - Deterministic": {"cases": [], "metrics": {}},
        "B - Gemini": {"cases": [], "metrics": {}},
        "C - Gemini + verifier": {"cases": [], "metrics": {}}
    }
    
    run_experiment_mode(pairs, dataset_path, "A - Deterministic", use_gemini=False, use_verifier=False, results_out=results)
    run_experiment_mode(pairs, dataset_path, "B - Gemini", use_gemini=True, use_verifier=False, results_out=results)
    run_experiment_mode(pairs, dataset_path, "C - Gemini + verifier", use_gemini=True, use_verifier=True, results_out=results)
    
    with open("experiment_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("Experiment complete. Results saved to experiment_results.json.")

if __name__ == "__main__":
    main()
