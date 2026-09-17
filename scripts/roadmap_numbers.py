"""Records touched by each roadmap item (DELIVERABLE.md section 3), from the cached base.

Usage: python3 scripts/roadmap_numbers.py
"""
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def load(table):
    return {r["id"]: r["fields"] for r in json.loads((RAW / f"{table}.json").read_text())}


OPEN, CAND, APP, INT, OFF = (load(t) for t in ("Job_Openings", "Candidates", "Applications", "Interviews", "Offers"))
PULLED = date.fromisoformat(json.loads((RAW / "_manifest.json").read_text())["pulled_at"][:10])


def one(f, k):
    return (f.get(k) or [None])[0]


def share(k, n):
    return f"{k}/{n} = {100 * k / n:.1f}%"


print("BUILD 1 - attribution and identity")
sig = [r for r, f in APP.items() if f.get("Referred By") or CAND[one(f, "Candidate")]["Source"] == "Referral"]
bad = [r for r in sig if bool(APP[r].get("Referred By")) != (CAND[one(APP[r], "Candidate")]["Source"] == "Referral")]
print("  applications with a referral signal whose two signals contradict:", share(len(bad), len(sig)),
      "| as a share of all applications:", share(len(bad), len(APP)))
print("  hires among them:", share(sum(APP[r]["Stage"] == "Hired" for r in bad), sum(f["Stage"] == "Hired" for f in APP.values())))
multi = sum(len(f.get("Applications", [])) > 1 for f in CAND.values())
print("  candidates with more than one application (Source is stored once per candidate):", share(multi, len(CAND)))
key = lambda f: (re.sub(r"\s+", " ", f["Full Name"].strip().lower()), re.sub(r"\D", "", f["Phone"]))
groups = defaultdict(list)
for c, f in CAND.items():
    groups[key(f)].append(c)
dup_rows = [c for g in groups.values() if len(g) > 1 for c in g]
dup_hire = sum(any(APP[a]["Stage"] == "Hired" for a in CAND[c].get("Applications", [])) for c in dup_rows)
print("  duplicate candidate rows (same name and phone):", share(len(dup_rows), len(CAND)),
      f"| people: {sum(len(g) > 1 for g in groups.values())} | rows holding a hire: {dup_hire}")
emails = Counter(f["Email"].lower() for f in CAND.values())
print("  duplicate rows a match on email would catch:", sum(emails[CAND[c]["Email"].lower()] > 1 for c in dup_rows), f"of {len(dup_rows)}")

print("\nBUILD 2 - offer lifecycle")
pend = [f for f in OFF.values() if f["Status"] == "Pending"]
with_dec = sum(bool(f.get("Decision On")) for f in pend)
over20 = sum((PULLED - date.fromisoformat(f["Offered On"])).days > 20 for f in pend)
over30 = sum((PULLED - date.fromisoformat(f["Offered On"])).days > 30 for f in pend)
print(f"  pending offers: {len(pend)}/{len(OFF)}; with a decision date: {with_dec}; open more than 20 days: {over20}; "
      f"more than 30 days: {over30}")
dec_stage = [f for f in OFF.values() if f["Status"] == "Declined" and APP[one(f, "Application")]["Stage"] == "Offer"]
n_dec = sum(f["Status"] == "Declined" for f in OFF.values())
print(f"  declined offers whose application still says Offer stage: {len(dec_stage)}/{n_dec}")
print("  offers with a status problem (stale pending + declined at Offer stage):", share(len(pend) + len(dec_stage), len(OFF)))

print("\nBUILD 3 - pipeline hygiene")
active = [f for f in APP.values() if f["Status"] == "Active"]
not_open = [f for f in active if OPEN[one(f, "Opening")]["Status"] != "Open"]
print("  active applications on openings that are not Open:", share(len(not_open), len(active)),
      dict(Counter(OPEN[one(f, "Opening")]["Status"] for f in not_open)))


def idle(f):
    last = max(f[k] for k in ("Applied On", "Screened On", "First Interview On", "Final Interview On", "Offered On") if f.get(k))
    return (PULLED - date.fromisoformat(last)).days


print("  active applications idle more than 30 days:", share(sum(idle(f) > 30 for f in active), len(active)),
      "| more than 90 days:", share(sum(idle(f) > 90 for f in active), len(active)))
print("  active applications as a share of all applications:", share(len(active), len(APP)))
hires = Counter(one(f, "Opening") for f in APP.values() if f["Stage"] == "Hired")
wrong = {o for o, f in OPEN.items() if hires[o] > f["Headcount"]
         or (f["Status"] == "Filled" and hires[o] < f["Headcount"])
         or (f["Status"] != "Filled" and hires[o] >= f["Headcount"])}
print("  openings whose Status or Headcount disagrees with their hires:", share(len(wrong), len(OPEN)))
pc = [f for f in APP.values() if f.get("Rejection Reason") == "Position Cancelled"]
print("  'Position Cancelled' rejections on openings that are not Cancelled:",
      f"{sum(OPEN[one(f, 'Opening')]['Status'] != 'Cancelled' for f in pc)}/{len(pc)}")

print("\nNOT BUILDING 3 - interview scores")
offered = [f for f in APP.values() if f.get("Offers")]
NEG, POS = {"No Hire", "Strong No Hire"}, {"Hire", "Strong Hire"}
rows = []
for f in offered:
    recs = [INT[i].get("Recommendation") for i in f["Interviews"]]
    given = [r for r in recs if r]
    rows.append((f, recs, given))
print("  applications with an offer:", len(offered), "| with no recorded recommendation at all:",
      sum(not g for _, _, g in rows))
all_neg = [(f, g) for f, _, g in rows if g and all(r in NEG for r in g)]
print("  offers where every recorded recommendation was No Hire or Strong No Hire:", share(len(all_neg), len(offered)))
print("    number of interviews behind those offers:", dict(Counter(len(g) for _, g in all_neg)))
print("    outcome of those offers:", dict(Counter(OFF[one(f, "Offers")]["Status"] for f, _ in all_neg)))
any_neg = sum(any(r in NEG for r in g) for _, _, g in rows)
print("  offers with at least one No Hire or Strong No Hire:", share(any_neg, len(offered)))
iv = [f for f in APP.values() if f.get("Interviews")]
pos_no_offer = sum(1 for f in iv if not f.get("Offers") and f["Status"] == "Closed"
                   and [INT[i].get("Recommendation") for i in f["Interviews"] if INT[i].get("Recommendation")]
                   and all(INT[i].get("Recommendation") in POS for i in f["Interviews"] if INT[i].get("Recommendation")))
print("  closed applications with only Hire or Strong Hire recommendations and no offer:", pos_no_offer)
