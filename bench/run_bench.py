"""Benchmark rigged on real patches.

  1. SWE-bench Verified gold patches (500): real human fixes — the clean baseline.
     rigged should flag very few of these as gaming (false-positive rate).
  2. SWE-agent generated patches (~6k): real agent attempts. Measure gaming
     prevalence, and compare runs that solved vs failed their task.
"""
from __future__ import annotations
import json
import os
import sys
import time
import collections

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd  # noqa: E402
from rigged import analyze  # noqa: E402


def bench_gold(path, out_dir):
    df = pd.read_parquet(path, columns=["instance_id", "patch", "problem_statement"])
    counts = collections.Counter()
    flagged = []
    lat = []
    for _, r in df.iterrows():
        t0 = time.perf_counter()
        v = analyze(r["patch"] or "", r.get("problem_statement", "") or "")
        lat.append((time.perf_counter() - t0) * 1000)
        counts[v.verdict] += 1
        if v.verdict != "clean":
            flagged.append({"instance": r["instance_id"], "verdict": v.verdict,
                            "score": v.score, "why": [s.message for s in v.signals[:2]]})
    lat.sort()
    n = len(df)
    summary = {
        "corpus": "swebench_gold", "n": n, "verdicts": dict(counts),
        "false_positive_pct": round(100 * (counts["gaming"]) / n, 2),
        "flagged_any_pct": round(100 * (n - counts["clean"]) / n, 2),
        "latency_ms": {"mean": round(sum(lat) / n, 4), "p99": round(lat[int(n * 0.99)], 4)},
    }
    json.dump(summary, open(f"{out_dir}/gold_summary.json", "w"), indent=2)
    json.dump(flagged, open(f"{out_dir}/gold_flagged.json", "w"), indent=2)
    return summary


def bench_agent(path, out_dir):
    df = pd.read_parquet(path, columns=["instance_id", "model_name", "target", "generated_patch"])
    df = df[df.generated_patch.map(lambda p: isinstance(p, str) and p.strip() != "")]
    counts = collections.Counter()
    by_solved = {True: collections.Counter(), False: collections.Counter()}
    sigcodes = collections.Counter()
    examples = []
    lat = []
    for _, r in df.iterrows():
        t0 = time.perf_counter()
        v = analyze(r["generated_patch"])
        lat.append((time.perf_counter() - t0) * 1000)
        counts[v.verdict] += 1
        by_solved[bool(r["target"])][v.verdict] += 1
        for s in v.signals:
            sigcodes[s.code] += 1
        if v.verdict == "gaming" and len(examples) < 300:
            examples.append({"instance": r["instance_id"], "model": r["model_name"],
                             "solved": bool(r["target"]), "score": v.score,
                             "why": [s.message for s in v.signals[:3]],
                             "lines": [s.line.strip()[:120] for s in v.signals[:3] if s.line]})
    lat.sort()
    n = len(df)

    def rate(d):
        tot = sum(d.values())
        return round(100 * d["gaming"] / tot, 3), tot
    sg, sn = rate(by_solved[True])
    fg, fn = rate(by_solved[False])
    summary = {
        "corpus": "swe_agent", "n": n, "verdicts": dict(counts),
        "verdict_pct": {k: round(100 * v / n, 2) for k, v in counts.items()},
        "gaming_pct": round(100 * counts["gaming"] / n, 2),
        "solved_gaming_pct": sg, "failed_gaming_pct": fg,
        "solved_n": sn, "failed_n": fn,
        "gaming_ratio": round(fg / sg, 1) if sg else None,
        "top_signals": sigcodes.most_common(15),
        "latency_ms": {"mean": round(sum(lat) / n, 4), "p99": round(lat[int(n * 0.99)], 4)},
    }
    json.dump(summary, open(f"{out_dir}/agent_summary.json", "w"), indent=2)
    json.dump(examples, open(f"{out_dir}/agent_gaming_examples.json", "w"), indent=2)
    return summary


if __name__ == "__main__":
    out = sys.argv[3] if len(sys.argv) > 3 else "bench/out"
    os.makedirs(out, exist_ok=True)
    g = bench_gold(sys.argv[1], out)
    print("GOLD:", json.dumps(g))
    a = bench_agent(sys.argv[2], out)
    print("AGENT:", json.dumps({k: a[k] for k in ("n", "verdict_pct", "gaming_pct",
          "solved_gaming_pct", "failed_gaming_pct", "gaming_ratio", "latency_ms")}))
