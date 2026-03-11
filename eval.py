"""Evaluation script for targetID prediction.

Computes Precision, Recall and F1 by comparing predicted targetIDs (output.json)
against ground-truth targetIds (data.json), matched on paragraph ID.

Metrics are computed in two ways:
  - Micro: aggregate TP/FP/FN across all paragraphs, then compute ratios.
  - Macro: compute per-paragraph scores, then average (paragraphs with no ground
           truth and no prediction are excluded to avoid inflating the average).
"""

import argparse
import json
from dataclasses import dataclass, field


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        return 2 * p * r / (p + r) if (p + r) else 0.0


def evaluate(ground_truth_path: str, predictions_path: str) -> dict:
    with open(ground_truth_path, encoding="utf-8") as fh:
        gt_data = json.load(fh)
    with open(predictions_path, encoding="utf-8") as fh:
        pred_data = json.load(fh)

    # Build ground-truth lookup: paragraphId → set of target IDs
    gt_map: dict[str, set[str]] = {
        entry["id"]: set(entry.get("targetIds", []))
        for entry in gt_data.get("paragraphLinks", gt_data)
    }

    # Build prediction lookup: paragraphId → set of target IDs
    pred_map: dict[str, set[str]] = {
        entry["paragraphId"]: set(entry.get("targetIDs", []))
        for entry in pred_data
    }

    micro = Counts()
    per_paragraph: list[Counts] = []
    unmatched_predictions = 0

    for para_id, gt_targets in gt_map.items():
        pred_targets = pred_map.get(para_id, set())

        tp = len(gt_targets & pred_targets)
        fp = len(pred_targets - gt_targets)
        fn = len(gt_targets - pred_targets)

        micro.tp += tp
        micro.fp += fp
        micro.fn += fn

        # Exclude paragraphs where both sides are empty (no signal either way)
        if gt_targets or pred_targets:
            per_paragraph.append(Counts(tp=tp, fp=fp, fn=fn))

    for para_id in pred_map:
        if para_id not in gt_map:
            unmatched_predictions += 1

    macro_p = (
        sum(c.precision() for c in per_paragraph) / len(per_paragraph)
        if per_paragraph else 0.0
    )
    macro_r = (
        sum(c.recall() for c in per_paragraph) / len(per_paragraph)
        if per_paragraph else 0.0
    )
    macro_f1 = (
        2 * macro_p * macro_r / (macro_p + macro_r)
        if (macro_p + macro_r) else 0.0
    )

    return {
        "paragraphs_evaluated": len(gt_map),
        "paragraphs_with_signal": len(per_paragraph),
        "unmatched_prediction_ids": unmatched_predictions,
        "micro": {
            "precision": round(micro.precision(), 4),
            "recall":    round(micro.recall(),    4),
            "f1":        round(micro.f1(),        4),
            "tp": micro.tp,
            "fp": micro.fp,
            "fn": micro.fn,
        },
        "macro": {
            "precision": round(macro_p,  4),
            "recall":    round(macro_r,  4),
            "f1":        round(macro_f1, 4),
        },
    }


def _print_results(results: dict) -> None:
    print(f"\n{'─' * 44}")
    print(f"  Paragraphs evaluated : {results['paragraphs_evaluated']}")
    print(f"  Paragraphs with signal: {results['paragraphs_with_signal']}")
    if results["unmatched_prediction_ids"]:
        print(f"  ⚠ Unmatched prediction IDs: {results['unmatched_prediction_ids']}")
    print(f"{'─' * 44}")
    for mode in ("micro", "macro"):
        m = results[mode]
        print(f"  {mode.upper()}")
        print(f"    Precision : {m['precision']:.4f}")
        print(f"    Recall    : {m['recall']:.4f}")
        print(f"    F1        : {m['f1']:.4f}")
        if mode == "micro":
            print(f"    TP={m['tp']}  FP={m['fp']}  FN={m['fn']}")
        print()
    print(f"{'─' * 44}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate predicted targetIDs against ground-truth targetIds."
    )
    parser.add_argument(
        "--ground-truth", default="data.json",
        help="Ground-truth JSON file (default: data.json)"
    )
    parser.add_argument(
        "--predictions", default="output.json",
        help="Predictions JSON file (default: output.json)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Dump results as JSON instead of a formatted table"
    )
    args = parser.parse_args()

    results = evaluate(args.ground_truth, args.predictions)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_results(results)
