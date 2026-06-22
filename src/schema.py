"""
Schema: the extraction contract.

Structured output is only useful if its shape is known up front. A schema declares
the fields to pull, their type, and whether they are required — both to build the
VLM prompt (so the model returns exactly this shape) and to validate what comes back.

Schemas are plain dicts (no pydantic dependency) so this module is stdlib-only and
the validator/evaluator can run anywhere. Two financial schemas ship built in; callers
can pass their own.
"""
from typing import Dict, List

# Field types the validator understands.
TYPES = ("string", "number", "date", "currency", "integer")


class Field:
    __slots__ = ("name", "type", "required", "description")

    def __init__(self, name: str, type: str = "string", required: bool = False,
                 description: str = ""):
        if type not in TYPES:
            raise ValueError(f"unknown field type {type!r}; expected one of {TYPES}")
        self.name = name
        self.type = type
        self.required = required
        self.description = description


class Schema:
    """A named set of fields plus an optional `totals` coherence rule."""

    def __init__(self, name: str, fields: List[Field], totals: Dict[str, List[str]] = None):
        self.name = name
        self.fields = fields
        # totals maps a total field -> the line-item fields that must sum to it.
        # e.g. {"total_revenue": ["product_revenue", "service_revenue"]}
        self.totals = totals or {}

    def field_names(self) -> List[str]:
        return [f.name for f in self.fields]

    def required_names(self) -> List[str]:
        return [f.name for f in self.fields if f.required]

    def as_prompt_spec(self) -> str:
        """Render the schema as a compact spec the VLM can follow."""
        lines = [f"Schema: {self.name}", "Return JSON with exactly these fields:"]
        for f in self.fields:
            req = "required" if f.required else "optional"
            desc = f" — {f.description}" if f.description else ""
            lines.append(f"  - {f.name} ({f.type}, {req}){desc}")
        if self.totals:
            lines.append("Coherence: these totals must equal the sum of their parts:")
            for total, parts in self.totals.items():
                lines.append(f"  - {total} = {' + '.join(parts)}")
        return "\n".join(lines)


# --- Built-in financial schemas -------------------------------------------------

INCOME_STATEMENT = Schema(
    name="income_statement",
    fields=[
        Field("period", "string", required=True, description="reporting period, e.g. FY2023"),
        Field("total_revenue", "currency", required=True),
        Field("cost_of_revenue", "currency"),
        Field("gross_profit", "currency"),
        Field("operating_expenses", "currency"),
        Field("operating_income", "currency"),
        Field("net_income", "currency", required=True),
        Field("currency", "string", required=True, description="ISO code, e.g. USD"),
    ],
    totals={
        # gross_profit = total_revenue - cost_of_revenue is a *difference*, not a sum,
        # so it is checked separately by the validator's identity rules, not here.
    },
)

GENERIC_TABLE = Schema(
    name="generic_table",
    fields=[
        Field("title", "string", description="table caption or heading"),
        Field("columns", "string", required=True, description="JSON array of column headers"),
        Field("rows", "string", required=True, description="JSON array of row arrays"),
    ],
)

BUILTINS: Dict[str, Schema] = {
    INCOME_STATEMENT.name: INCOME_STATEMENT,
    GENERIC_TABLE.name: GENERIC_TABLE,
}


def get_schema(name: str) -> Schema:
    if name not in BUILTINS:
        raise KeyError(f"no built-in schema {name!r}; available: {list(BUILTINS)}")
    return BUILTINS[name]
