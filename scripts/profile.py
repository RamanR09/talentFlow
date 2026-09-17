"""Profile every cached table: fields, fill rate, types, distinct values, ranges.

Airtable omits empty fields from a record, so "filled" means the key is present.

Usage: python3 scripts/profile.py
"""
import json
from collections import Counter
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
MAX_DISTINCT_SHOWN = 25


def load(table):
    return json.loads((RAW / f"{table.replace(' ', '_')}.json").read_text())


def describe(values):
    kinds = Counter(type(v).__name__ for v in values)
    flat = []
    for v in values:
        flat.extend(v if isinstance(v, list) else [v])
    hashable = [json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for v in flat]
    distinct = Counter(hashable)
    out = f"types={dict(kinds)} distinct={len(distinct)}"
    scalars = [v for v in flat if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if scalars and len(scalars) == len(flat):
        out += f" min={min(scalars)} max={max(scalars)}"
    elif all(isinstance(v, str) for v in flat) and flat:
        out += f" min={min(flat)!r} max={max(flat)!r}"
    if len(distinct) <= MAX_DISTINCT_SHOWN:
        out += "\n        values: " + ", ".join(
            f"{k!r}x{n}" for k, n in sorted(distinct.items(), key=lambda kv: (-kv[1], str(kv[0]))))
    return out


def main():
    manifest = json.loads((RAW / "_manifest.json").read_text())
    for table in manifest["tables"]:
        records = load(table)
        print(f"\n=== {table}: {len(records)} records ===")
        fields = Counter()
        for r in records:
            fields.update(r["fields"].keys())
        for field, n in sorted(fields.items()):
            values = [r["fields"][field] for r in records if field in r["fields"]]
            print(f"  {field:<28} filled {n:>3}/{len(records)}  {describe(values)}")


if __name__ == "__main__":
    main()
