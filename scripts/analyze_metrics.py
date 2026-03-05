import json
import argparse
from pathlib import Path
from typing import List, Dict
import statistics

def load_metrics(log_path: str) -> List[Dict]:
    data = []
    path = Path(log_path)
    if not path.exists():
        return []
        
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data

def get_stats(data: List[Dict]) -> Dict:
    if not data:
        return {}
    
    total = len(data)
    asr_lats = [d.get("asr_latency", 0) for d in data]
    llm_lats = [d.get("llm_inference_latency", 0) for d in data if d.get("llm_called")]
    total_lats = [d.get("total_latency", 0) for d in data]
    
    llm_calls = sum(1 for d in data if d.get("llm_called"))
    llm_success = sum(1 for d in data if d.get("llm_success"))
    keyword_hit = sum(1 for d in data if d.get("keyword_action_found"))
    errors = sum(1 for d in data if d.get("error_type"))

    return {
        "n": total,
        "avg_asr": statistics.mean(asr_lats),
        "max_asr": max(asr_lats),
        "avg_llm": statistics.mean(llm_lats) if llm_lats else 0,
        "avg_total": statistics.mean(total_lats),
        "max_total": max(total_lats),
        "keyword_rate": keyword_hit / total,
        "llm_rate": llm_calls / total,
        "error_rate": errors / total
    }

def print_single(name: str, s: Dict):
    print(f"=== Metrics Analysis: {name} (N={s['n']}) ===\n")
    print(f"{'Metric':<25} | {'Value':<10}")
    print("-" * 40)
    print(f"{'Avg ASR Latency':<25} | {s['avg_asr']:.3f}s")
    print(f"{'Max ASR Latency':<25} | {s['max_asr']:.3f}s")
    if s['avg_llm']:
        print(f"{'Avg LLM Latency':<25} | {s['avg_llm']:.3f}s")
    print(f"{'Avg Total Latency':<25} | {s['avg_total']:.3f}s")
    print(f"{'Max Total Latency':<25} | {s['max_total']:.3f}s")
    print("-" * 40)
    print(f"{'Keyword Hit Rate':<25} | {s['keyword_rate']*100:.1f}%")
    print(f"{'LLM Fallback Rate':<25} | {s['llm_rate']*100:.1f}%")
    print(f"{'Error Rate':<25} | {s['error_rate']*100:.1f}%")
    print("\n")

def print_comparison(s1: Dict, name1: str, s2: Dict, name2: str):
    print(f"=== Hardware Comparison: {name1} vs {name2} ===\n")
    header = f"{'Metric':<25} | {name1:<12} | {name2:<12} | {'Diff (%)':<10}"
    print(header)
    print("-" * len(header))
    
    def row(label, key, reverse=False):
        v1 = s1[key]
        v2 = s2[key]
        diff = ((v2 - v1) / v1 * 100) if v1 else 0
        # reverse=True means higher is better (like Hit Rate)
        # default is lower is better (like Latency)
        indicator = " (Faster)" if diff < 0 else " (Slower)"
        if reverse:
            indicator = " (Better)" if diff > 0 else " (Worse)"
            
        print(f"{label:<25} | {v1:<12.3f} | {v2:<12.3f} | {diff:>+7.1f}%{indicator}")

    row("Avg ASR Latency", "avg_asr")
    row("Avg Total Latency", "avg_total")
    row("Max Total Latency", "max_total")
    if s1['avg_llm'] and s2['avg_llm']:
        row("Avg LLM Latency", "avg_llm")
    
    print("-" * len(header))
    row("Keyword Hit Rate", "keyword_rate", reverse=True)
    row("Error Rate", "error_rate")
    print("\n[Summary]")
    slowdown = s2['avg_total'] / s1['avg_total'] if s1['avg_total'] else 0
    print(f"-> {name2} overall is {slowdown:.2f}x slower than {name1}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze and Compare metrics.")
    parser.add_argument("files", nargs="+", help="One or two metrics files to analyze")
    args = parser.parse_args()
    
    results = []
    for f in args.files:
        data = load_metrics(f)
        if data:
            results.append((f, get_stats(data)))
        else:
            print(f"Warning: Could not load data from {f}")

    if len(results) == 1:
        print_single(results[0][0], results[0][1])
    elif len(results) >= 2:
        print_comparison(results[0][1], results[0][0], results[1][1], results[1][0])
