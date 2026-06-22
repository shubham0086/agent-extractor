"""
Validator: does the extracted JSON hold together?

Extraction accuracy is not just "did the model return a number" — it is "is the number
right." For financial documents you get a free, powerful correctness signal: the numbers
must be internally consistent. Subtotals must equal the sum of their line items; the
income-statement identities must hold. A VLM that misreads one cell usually breaks one of
these, so coherence checks catch silent extraction errors no schema-shape check can.

Three layers, cheapest first:
  1. required-field presence
  2. type coercion (currency/number/integer parse cleanly; dates look like dates)
  3. arithmetic coherence (schema `totals` sums + built-in statement identities)

Pure stdlib. Returns a structured report; never raises on bad data.
"""
import re
from typing import Dict, List, Optional

from .schema import Schema

# Identities checked when the relevant fields are present (income statement).
_IDENTITIES = [
    # (result, left, minus_right) -> result == left - minus_right
    ("gross_profit", "total_revenue", "cost_of_revenue"),
    ("operating_income", "gross_profit", "operating_expenses"),
]

_DATE_RE = re.compile(r"\b(19|20)\d{2}\b")  # a 4-digit year is enough for FYxxxx / dates


def _to_number(value) -> Optional[float]:
    """Coerce an extracted value to a number, honoring (parens) = negative."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


class Validator:
    def __init__(self, tolerance: float = 0.01):
        # relative tolerance for arithmetic checks (rounding in filings)
        self.tolerance = tolerance

    def validate(self, fields: Dict, schema: Schema) -> Dict:
        """
        Return {ok, errors[], warnings[], checked[]}.

        ok is True only when there are zero errors. Type mismatches and broken
        identities are errors; a missing optional field is nothing; a coherence
        rule that can't run (a part is null) is a warning, not a failure.
        """
        errors: List[str] = []
        warnings: List[str] = []
        checked: List[str] = []

        # 1. required presence
        for name in schema.required_names():
            if fields.get(name) in (None, ""):
                errors.append(f"missing required field: {name}")

        # 2. type coercion
        for f in schema.fields:
            if fields.get(f.name) in (None, ""):
                continue
            val = fields[f.name]
            if f.type in ("number", "currency", "integer"):
                n = _to_number(val)
                if n is None:
                    errors.append(f"{f.name}: '{val}' is not a {f.type}")
                elif f.type == "integer" and n != int(n):
                    warnings.append(f"{f.name}: {val} is not a whole number")
            elif f.type == "date":
                if not _DATE_RE.search(str(val)):
                    warnings.append(f"{f.name}: '{val}' does not look like a date")

        # 3a. schema-declared totals (sum of parts)
        for total, parts in schema.totals.items():
            self._check_sum(fields, total, parts, errors, warnings, checked)

        # 3b. built-in statement identities (difference form)
        for result, left, right in _IDENTITIES:
            self._check_identity(fields, result, left, right, errors, warnings, checked)

        return {
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "checked": checked,
        }

    def _check_sum(self, fields, total, parts, errors, warnings, checked):
        t = _to_number(fields.get(total))
        part_nums = [_to_number(fields.get(p)) for p in parts]
        if t is None or any(p is None for p in part_nums):
            warnings.append(f"could not check {total} = sum({parts}): a value is missing")
            return
        s = sum(part_nums)
        checked.append(f"{total} == sum({'+'.join(parts)})")
        if not self._close(t, s):
            errors.append(f"{total} ({t}) != sum of parts ({s})")

    def _check_identity(self, fields, result, left, right, errors, warnings, checked):
        r = _to_number(fields.get(result))
        a = _to_number(fields.get(left))
        b = _to_number(fields.get(right))
        if r is None or a is None or b is None:
            return  # silent: identity simply doesn't apply when a field is absent
        checked.append(f"{result} == {left} - {right}")
        if not self._close(r, a - b):
            errors.append(f"{result} ({r}) != {left} - {right} ({a - b})")

    def _close(self, a: float, b: float) -> bool:
        if a == b:
            return True
        scale = max(abs(a), abs(b), 1.0)
        return abs(a - b) / scale <= self.tolerance
