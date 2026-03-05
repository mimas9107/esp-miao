import json
import argparse
from pathlib import Path
from typing import List, Dict
import statistics

def load_metrics(log_path: str) -> List[Dict]:
    data = []
    path = Path(log_path)
    if not path.exists():
        print(f"Error: Log file {log_path} not found.")
        return []
        
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data

def analyze(data: List[Dict]):
    if not data:
        print("No data to analyze.")
        return

    total = len(data)
    print(f"=== Metrics Analysis (N={total}) ===\n")

    # 1. Latency Analysis
    print("--- Latency (seconds) ---")
    asr_lats = [d.get("asr_latency", 0) for d in data]
    llm_lats = [d.get("llm_inference_latency", 0) for d in data if d.get("llm_called")]
    total_lats = [d.get("total_latency", 0) for d in data]

    print(f"Avg ASR Latency:   {statistics.mean(asr_lats):.3f} (Max: {max(asr_lats):.3f})")
    if llm_lats:
        print(f"Avg LLM Latency:   {statistics.mean(llm_lats):.3f} (Max: {max(llm_lats):.3f})")
    else:
        print("Avg LLM Latency:   N/A (No LLM calls)")
    print(f"Avg Total Latency: {statistics.mean(total_lats):.3f} (Max: {max(total_lats):.3f})")
    print("")

    # 2. Logic Analysis
    print("--- Logic Flow ---")
    llm_calls = sum(1 for d in data if d.get("llm_called"))
    llm_success = sum(1 for d in data if d.get("llm_success"))
    keyword_hit = sum(1 for d in data if d.get("keyword_action_found"))
    
    print(f"Keyword Hit Rate:  {keyword_hit / total * 100:.1f}%")
    print(f"LLM Fallback Rate: {llm_calls / total * 100:.1f}%")
    if llm_calls > 0:
        print(f"LLM Success Rate:  {llm_success / llm_calls * 100:.1f}%")
    print("")

    # 3. Dispatch Analysis
    print("--- Dispatch ---")
    mqtt_count = sum(1 for d in data if d.get("dispatch_type") == "mqtt")
    http_count = sum(1 for d in data if d.get("dispatch_type") == "http_api")
    dispatch_success = sum(1 for d in data if d.get("dispatch_success"))
    
    print(f"MQTT Dispatches:   {mqtt_count}")
    print(f"HTTP Dispatches:   {http_count}")
    print(f"Success Rate:      {dispatch_success / total * 100:.1f}%")
    print("")

    # 4. Error Analysis
    print("--- Errors ---")
    errors = [d.get("error_type") for d in data if d.get("error_type")]
    if errors:
        from collections import Counter
        counts = Counter(errors)
        for err, cnt in counts.most_common():
            print(f"- {err}: {cnt}")
    else:
        print("No errors recorded.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze esp-miao metrics logs.")
    parser.add_argument("log_file", nargs="?", default="metrics.jsonl", help="Path to metrics.jsonl")
    args = parser.parse_args()
    
    metrics_data = load_metrics(args.log_file)
    analyze(metrics_data)
