"""Evaluate rigged on the hand-labelled gold set.

Binary task: gaming vs not-gaming (suspicious counts as a flag, not a miss). Reports
precision/recall/F1 for the 'gaming' verdict and lists any errors.
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rigged import analyze  # noqa: E402
from gold import GOLD  # noqa: E402


def main():
    tp = fp = fn = tn = 0
    errors = []
    rows = []
    for label, problem, diff in GOLD:
        v = analyze(diff, problem)
        pred_gaming = v.verdict == "gaming"
        gold_gaming = label == "gaming"
        if pred_gaming and gold_gaming:
            tp += 1
        elif pred_gaming and not gold_gaming:
            fp += 1
            errors.append(("FALSE POSITIVE", label, v.verdict, v.score, diff.splitlines()[0],
                           v.signals[0].message if v.signals else ""))
        elif not pred_gaming and gold_gaming:
            fn += 1
            errors.append(("MISS", label, v.verdict, v.score, diff.splitlines()[0],
                           v.signals[0].message if v.signals else ""))
        else:
            tn += 1
        rows.append({"gold": label, "pred": v.verdict, "score": v.score})

    n = len(GOLD)
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / n
    out = {
        "n": n, "n_gaming": sum(1 for l, _, _ in GOLD if l == "gaming"),
        "n_clean": sum(1 for l, _, _ in GOLD if l == "clean"),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
        "accuracy": round(acc, 3), "rows": rows,
    }
    os.makedirs("bench/out", exist_ok=True)
    json.dump(out, open("bench/out/gold_eval.json", "w"), indent=2)
    print(f"gold cases: {n}  ({out['n_gaming']} gaming, {out['n_clean']} clean)")
    print(f"accuracy: {out['accuracy']}")
    print(f"gaming precision/recall/F1: {prec:.3f} / {rec:.3f} / {f1:.3f}")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")
    for e in errors:
        print("  ", e[0], "| gold", e[1], "-> pred", e[2], f"(score {e[3]})", "|", e[4])
        print("       ", e[5][:90])


if __name__ == "__main__":
    main()
