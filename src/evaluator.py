"""
Evaluator: score extracted fields against a gold (hand-labeled) record.

You cannot tune an extraction pipeline you cannot measure. This mirrors the RAGAS-style
eval harness in rag-knowledge-engine, but for extraction: given a page's gold answer,
compute field-level accuracy so a prompt or model change is provably better, not vibes.

Metrics (all 0.0–1.0):
  field_accuracy — fraction of gold fields extracted correctly (numeric within tolerance,
                   strings case/space-insensitive)
  precision      — of the fields the model filled, how many were right (penalizes guessing)
  recall         — of the gold fields, how many the model got (penalizes omissions)

Pure stdlib (no numpy). Numeric comparison reuses the validator's tolerant parse.
"""
from typing import Dict, List

from .validator import _to_number


def _norm_str(v) -> str:
    return " ".join(str(v).strip().lower().split())


def _values_match(got, gold, tolerance: float) -> bool:
    g_num, gold_num = _to_number(got), _to_number(gold)
    if gold_num is not None and g_num is not None:
        scale = max(abs(g_num), abs(gold_num), 1.0)
        return abs(g_num - gold_num) / scale <= tolerance
    return _norm_str(got) == _norm_str(gold)


class Evaluator:
    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance

    def evaluate(self, extracted: Dict, gold: Dict) -> Dict:
        """
        Compare extracted fields to gold. Returns metrics + a per-field breakdown.

        Only fields present in `gold` are scored — gold defines the ground truth set.
        """
        per_field: List[Dict] = []
        correct = filled = 0
        gold_keys = list(gold.keys())

        for key in gold_keys:
            got = extracted.get(key)
            is_filled = got not in (None, "")
            ok = is_filled and _values_match(got, gold[key], self.tolerance)
            if is_filled:
                filled += 1
            if ok:
                correct += 1
            per_field.append({
                "field": key, "gold": gold[key], "got": got, "correct": ok,
            })

        n = len(gold_keys) or 1
        return {
            "field_accuracy": round(correct / n, 4),
            "precision": round(correct / filled, 4) if filled else 0.0,
            "recall": round(correct / n, 4),
            "correct": correct,
            "total": len(gold_keys),
            "per_field": per_field,
        }
