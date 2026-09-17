"""Check that every number written in DELIVERABLE.md also appears in output/findings.csv.

Headings are skipped (section numbers, D1-D5, Q3). Exits 1 if any number is unsupported.

Usage: python3 scripts/check_deliverable.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUMBER = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?(?![A-Za-z0-9]|\.\d)")

findings = (ROOT / "output" / "findings.csv").read_text()
allowed = set(NUMBER.findall(findings)) | set(re.findall(r"(\d+(?:\.\d+)?)x\b", findings))  # "5.3x" -> 5.3
missing = []
for n, line in enumerate((ROOT / "DELIVERABLE.md").read_text().splitlines(), 1):
    if line.startswith("#"):
        continue
    for token in NUMBER.findall(line):
        if token not in allowed:
            missing.append((n, token, line.strip()[:90]))

body_numbers = sum(len(NUMBER.findall(l)) for l in (ROOT / "DELIVERABLE.md").read_text().splitlines()
                   if not l.startswith("#"))
print(f"numbers checked in DELIVERABLE.md: {body_numbers}; not found in findings.csv: {len(missing)}")
for n, token, text in missing:
    print(f"  line {n}: {token}   <- {text}")
sys.exit(1 if missing else 0)
