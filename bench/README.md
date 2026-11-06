# Benchmarks

| corpus | what | n | source |
|---|---|---|---|
| **gold** | hand-labelled patches (gaming vs clean) | 34 | `bench/gold.py` |
| **SWE-bench gold** | real human bug-fixes — the false-alarm baseline | 500 | [princeton-nlp/SWE-bench_Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified) |
| **SWE-agent** | real agent patch attempts | 6,052 | [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) |

## Reproduce

```bash
pip install -r requirements-bench.txt

# gold precision/recall (no download)
python bench/eval_gold.py

# false-positive baseline + real agent patches
curl -L -o /tmp/verified.parquet \
  https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/main/data/test-00000-of-00001.parquet
curl -L -o /tmp/swe_traj.parquet \
  https://huggingface.co/datasets/nebius/SWE-agent-trajectories/resolve/main/data/train-00000-of-00012.parquet
python bench/run_bench.py /tmp/verified.parquet /tmp/swe_traj.parquet bench/out
```

## Headline results (`bench/out/report.json`)

- **Gold set:** precision 1.00 / recall 1.00 / F1 1.00 (34 patches, 19 gaming / 15 clean).
- **500 real human fixes:** 0.0% flagged as gaming (0 false positives); 0.2% flagged for any review.
- **6,052 agent patches:** 12.1% modify a test file; 4.5% of those are gaming; 0.59% overall.
- **Gaming vs outcome:** gaming is 4.5× more frequent in runs that failed their task
  (0.71% of failed-run patches vs 0.16% of solved-run patches).
- Zero analyzer crashes; ~0.1 ms per patch.
