"""Pull every table from the Acme Airtable base once and cache it to data/raw/.

Read-only: only GET requests are made. Reads AIRTABLE_TOKEN / AIRTABLE_BASE from
the environment or a .env file in the project root.

Usage: python3 scripts/pull.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
TABLES = [
    "Departments", "People", "Job Openings", "Candidates",
    "Applications", "Interviews", "Offers", "Findings",
]
MIN_INTERVAL = 0.25  # 4 requests/second, under the 5/second limit
LOCKOUT_WAIT = 31    # a 429 locks the base out for 30 seconds


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


_last_request = 0.0


def get(url, token):
    global _last_request
    while True:
        wait = MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code == 429:
                print(f"  429 received, waiting {LOCKOUT_WAIT}s", file=sys.stderr)
                time.sleep(LOCKOUT_WAIT)
                continue
            raise


def pull_table(base, table, token):
    records, offset, pages = [], None, 0
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        url = (f"https://api.airtable.com/v0/{base}/{urllib.parse.quote(table)}"
               f"?{urllib.parse.urlencode(params)}")
        data = get(url, token)
        records.extend(data.get("records", []))
        pages += 1
        offset = data.get("offset")
        if not offset:
            return records, pages


def main():
    load_env()
    token = os.environ.get("AIRTABLE_TOKEN")
    base = os.environ.get("AIRTABLE_BASE", "appYePRAI75PMbQNQ")
    if not token:
        sys.exit("AIRTABLE_TOKEN is not set (env var or .env)")
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {"base": base, "pulled_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
    for table in TABLES:
        records, pages = pull_table(base, table, token)
        ids = [r["id"] for r in records]
        assert len(ids) == len(set(ids)), f"duplicate record ids returned for {table}"
        path = RAW / f"{table.replace(' ', '_')}.json"
        path.write_text(json.dumps(records, indent=1, sort_keys=True))
        manifest["tables"][table] = {"records": len(records), "pages": pages, "file": path.name}
        print(f"{table:<14} {len(records):>5} records  {pages:>2} pages")
    (RAW / "_manifest.json").write_text(json.dumps(manifest, indent=1))
    print("total requests:", sum(t["pages"] for t in manifest["tables"].values()))


if __name__ == "__main__":
    main()
