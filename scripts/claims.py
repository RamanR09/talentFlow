"""Rebuild the VP's two claims from the cached base, with sensitivity to data problems.

Claim 1: job boards are the biggest channel and bring 26.9% of hires.
Claim 2: offer acceptance rate is about 72%.

Every figure prints its numerator / denominator. Intervals are 95% Wilson.

Usage: python3 scripts/claims.py
"""
import json
from collections import Counter, defaultdict
from datetime import date
from math import sqrt
from pathlib import Path
from statistics import median

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def load(table):
    recs = json.loads((RAW / f"{table.replace(' ', '_')}.json").read_text())
    return {r["id"]: r["fields"] for r in recs}


PEOPLE, OPEN, CAND, APP, INT, OFF, DEPT = (load(t) for t in (
    "People", "Job Openings", "Candidates", "Applications", "Interviews", "Offers", "Departments"))
PULLED = date.fromisoformat(json.loads((RAW / "_manifest.json").read_text())["pulled_at"][:10])


def one(f, k):
    v = f.get(k) or []
    return v[0] if v else None


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rate(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100*k/n:.1f}%  (95% CI {100*lo:.1f}-{100*hi:.1f}%)" if n else f"{k}/0"


def days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def source_table(title, source_of_app):
    apps, hires, cands = Counter(), Counter(), defaultdict(set)
    for rid, f in APP.items():
        s = source_of_app(rid)
        apps[s] += 1
        cands[s].add(one(f, "Candidate"))
        hires[s] += f["Stage"] == "Hired"
    total_apps, total_hires = sum(apps.values()), sum(hires.values())
    print(f"\n{title}  [applications={total_apps}, hires={total_hires}]")
    print(f"  {'source':<12}{'cands':>6}{'apps':>6}{'app share':>11}{'hires':>7}{'hire share':>12}   hires per application")
    for s, n in apps.most_common():
        print(f"  {s:<12}{len(cands[s]):>6}{n:>6}{100*n/total_apps:>10.1f}%{hires[s]:>7}"
              f"{100*hires[s]/total_hires:>11.1f}%   {rate(hires[s], n)}")
    jb, rest = "Job Board", [s for s in apps if s != "Job Board"]
    print(f"  Job Board  : {rate(hires[jb], apps[jb])}")
    print(f"  All others : {rate(sum(hires[s] for s in rest), sum(apps[s] for s in rest))}")
    return apps, hires


print("=" * 100)
print("CLAIM 1 - 'job boards are our biggest channel and bring in 26.9% of our hires'")
print("=" * 100)
print("Source lives on the Candidates table (300 rows). Hire = Application with Stage='Hired' (26 rows,")
print("identical to the 26 Offers with Status='Accepted' - audit checks F1/F2).")

source_table("1a. As recorded: candidate Source", lambda r: CAND[one(APP[r], "Candidate")]["Source"])
source_table("1b. Re-attributed: an application with a 'Referred By' link counts as Referral",
             lambda r: "Referral" if APP[r].get("Referred By") else CAND[one(APP[r], "Candidate")]["Source"])

print("\n1c. Hires row by row (26)")
for rid, f in sorted(APP.items(), key=lambda kv: kv[1]["Application ID"]):
    if f["Stage"] == "Hired":
        c = CAND[one(f, "Candidate")]
        o = OPEN[one(f, "Opening")]
        print(f"  {f['Application ID']} {c['Candidate ID']} source={c['Source']:<11} "
              f"referred_by={'yes' if f.get('Referred By') else 'no ':<3} req={o['Req ID']} {o['Status']:<9} "
              f"{o['Level']:<6} applied={f['Applied On']} closed={f['Closed On']}")

print("\n1d. Hires on openings whose Status is Cancelled (should those count as hires?)")
hc = [f for f in APP.values() if f["Stage"] == "Hired" and OPEN[one(f, "Opening")]["Status"] == "Cancelled"]
print("  ", len(hc), "of 26:", Counter(CAND[one(f, "Candidate")]["Source"] for f in hc))

print("\n1e. Speed and quality by source (as recorded)")
by = defaultdict(lambda: defaultdict(list))
for f in APP.values():
    s = CAND[one(f, "Candidate")]["Source"]
    if f["Stage"] == "Hired":
        by[s]["time_to_hire"].append(days(f["Applied On"], f["Closed On"]))
    by[s]["screened"].append(bool(f.get("Screened On")))
    by[s]["interviewed"].append(bool(f.get("Interviews")))
    by[s]["offered"].append(bool(f.get("Offers")))
for s, d in sorted(by.items(), key=lambda kv: -len(kv[1]["screened"])):
    n = len(d["screened"])
    tth = d["time_to_hire"]
    print(f"  {s:<12} apps={n:>3} screened={sum(d['screened']):>3} interviewed={sum(d['interviewed']):>3} "
          f"offered={sum(d['offered']):>3}  interview rate {100*sum(d['interviewed'])/n:>5.1f}%  "
          f"median days apply->hire={median(tth) if tth else 'n/a'} (n={len(tth)})")

print("\n1f. Why job-board applications end (Rejected/Withdrawn), vs all other sources")
for label, pred in [("Job Board", lambda s: s == "Job Board"), ("Others", lambda s: s != "Job Board")]:
    rs = Counter(f.get("Rejection Reason") for f in APP.values()
                 if f["Stage"] in ("Rejected", "Withdrawn") and pred(CAND[one(f, "Candidate")]["Source"]))
    tot = sum(rs.values())
    print(f"  {label:<10} n={tot}: " + ", ".join(f"{k} {v} ({100*v/tot:.0f}%)" for k, v in rs.most_common()))

print("\n1g. Are the 26 hire rows 26 people? Candidates with more than one Hired application")
hired_by_cand = defaultdict(list)
for rid, f in APP.items():
    if f["Stage"] == "Hired":
        hired_by_cand[one(f, "Candidate")].append(f)
print(f"  hire rows=26, distinct candidate records hired={len(hired_by_cand)}")
repeat_rows = 0
for c, rows in hired_by_cand.items():
    if len(rows) > 1:
        repeat_rows += len(rows) - 1
        for f in sorted(rows, key=lambda f: f["Applied On"]):
            o = OPEN[one(f, "Opening")]
            print(f"    {CAND[c]['Candidate ID']} {CAND[c]['Full Name']} source={CAND[c]['Source']} {f['Application ID']} "
                  f"{o['Req ID']} {o['Title']} ({o['Level']}, headcount {o['Headcount']}) applied={f['Applied On']} hired={f['Closed On']}")
src_people = Counter(CAND[c]["Source"] for c in hired_by_cand)
tot = len(hired_by_cand)
print(f"  Counting each hired person once ({tot} people): " +
      ", ".join(f"{s} {n} ({100*n/tot:.1f}%)" for s, n in src_people.most_common()))
print(f"  Offer acceptance with the {repeat_rows} repeat-hire offers removed: "
      f"all offers {rate(26 - repeat_rows, 36 - repeat_rows)}; decided only {rate(26 - repeat_rows, 31 - repeat_rows)}")

print("\n" + "=" * 100)
print("CLAIM 2 - 'our offer acceptance rate is sitting at around 72%'")
print("=" * 100)
st = Counter(f["Status"] for f in OFF.values())
print("Offers table: 36 rows ->", dict(st))
A, D, P = st["Accepted"], st["Declined"], st["Pending"]
print(f"  2a. Accepted / all offers (pending counted as not accepted): {rate(A, A + D + P)}   <- matches the VP's ~72%")
print(f"  2b. Accepted / decided offers (Accepted + Declined):          {rate(A, A + D)}")
print(f"  2c. Worst case, all {P} pending decline:                        {rate(A, A + D + P)}")
print(f"  2d. Best case, all {P} pending accept:                          {rate(A + P, A + D + P)}")

print("\n  Pending offers in detail (pull date %s):" % PULLED)
for f in sorted((f for f in OFF.values() if f["Status"] == "Pending"), key=lambda f: f["Offered On"]):
    a = APP[one(f, "Application")]
    print(f"    {f['Offer ID']} offered={f['Offered On']} days_open={(PULLED - date.fromisoformat(f['Offered On'])).days:>3} "
          f"decision_on={f.get('Decision On', '-'):<10} proposed_start={f['Proposed Start Date']} "
          f"app={a['Application ID']} stage={a['Stage']}/{a['Status']} opening={OPEN[one(a,'Opening')]['Status']}")
dd = [days(f["Offered On"], f["Decision On"]) for f in OFF.values() if f["Status"] != "Pending"]
print(f"  Decided offers: days from offer to decision min={min(dd)} median={median(dd)} max={max(dd)} (n={len(dd)})")

print("\n  2e. Declined offers in detail (5):")
for f in (f for f in OFF.values() if f["Status"] == "Declined"):
    a = APP[one(f, "Application")]
    c = CAND[one(a, "Candidate")]
    o = OPEN[one(a, "Opening")]
    print(f"    {f['Offer ID']} reason={f['Decline Reason']:<14} base={f['Base CTC']:>8} expected={c['Expected CTC']:>8} "
          f"current={c['Current CTC']:>8} band=({o['Salary Band Min']}-{o['Salary Band Max']}) "
          f"bonus={f['Joining Bonus']} source={c['Source']} level={o['Level']} "
          f"days final-interview->offer={days(a['Final Interview On'], a['Offered On']) if a.get('Final Interview On') else 'n/a'}")

print("\n  2f. Does pay explain declines? Base CTC vs candidate Expected CTC, decided offers only")
for status in ("Accepted", "Declined"):
    ratios = [f["Base CTC"] / CAND[one(APP[one(f, "Application")], "Candidate")]["Expected CTC"]
              for f in OFF.values() if f["Status"] == status]
    below = sum(r < 1 for r in ratios)
    print(f"    {status:<9} n={len(ratios):>2} median base/expected={median(ratios):.2f}  offers below expectation: {below}/{len(ratios)}")

print("\n  2g. Does speed explain declines? Days from Final Interview On (or First) to Offered On")
for status in ("Accepted", "Declined", "Pending"):
    gaps = []
    for f in OFF.values():
        if f["Status"] == status:
            a = APP[one(f, "Application")]
            ref = a.get("Final Interview On") or a.get("First Interview On")
            gaps.append(days(ref, a["Offered On"]))
    print(f"    {status:<9} n={len(gaps):>2} median={median(gaps)} min={min(gaps)} max={max(gaps)}")

print("\n  2h. Acceptance by segment, decided offers (Accepted / Accepted+Declined). Tiny cells - read as counts.")
for seg, fn in [
    ("Level", lambda a: OPEN[one(a, "Opening")]["Level"]),
    ("Department", lambda a: DEPT[one(OPEN[one(a, "Opening")], "Department")]["Name"]),
    ("Source", lambda a: CAND[one(a, "Candidate")]["Source"]),
    ("Offer quarter", lambda a: a["Offered On"][:4] + "-Q" + str((int(a["Offered On"][5:7]) - 1) // 3 + 1)),
]:
    acc, dec, pen = Counter(), Counter(), Counter()
    for f in OFF.values():
        k = fn(APP[one(f, "Application")])
        {"Accepted": acc, "Declined": dec, "Pending": pen}[f["Status"]][k] += 1
    print(f"    by {seg}: " + "; ".join(
        f"{k} {acc[k]}/{acc[k]+dec[k]} (+{pen[k]} pending)" for k in sorted(set(acc) | set(dec) | set(pen))))

print("\n  2i. Offers touched by a data problem found in the audit")
bad = set()
for rid, f in OFF.items():
    a = APP[one(f, "Application")]
    o = OPEN[one(a, "Opening")]
    why = []
    if not o["Salary Band Min"] <= f["Base CTC"] <= o["Salary Band Max"]:
        why.append("base outside band")
    if f["Offered On"] != a.get("Offered On"):
        why.append("offer date mismatch")
    if f["Proposed Start Date"] < f["Offered On"]:
        why.append("start before offer")
    if f["Status"] == "Pending" and f.get("Decision On"):
        why.append("pending with decision date")
    if o["Status"] in ("Cancelled", "On Hold"):
        why.append(f"opening {o['Status']}")
    if why:
        bad.add(rid)
        print(f"    {f['Offer ID']} {f['Status']:<9} {', '.join(why)}")
clean = [f for rid, f in OFF.items() if rid not in bad]
cs = Counter(f["Status"] for f in clean)
print(f"    offers with at least one problem: {len(bad)}/36. On the remaining {len(clean)}: {dict(cs)}")
print(f"    acceptance on clean decided offers: {rate(cs['Accepted'], cs['Accepted'] + cs['Declined'])}")

print("\n" + "=" * 100)
print("FUNNEL - where the 350 applications go (for sizing the roadmap)")
print("=" * 100)
n = len(APP)
scr = sum(bool(f.get("Screened On")) for f in APP.values())
itv = sum(bool(f.get("Interviews")) for f in APP.values())
ofr = sum(bool(f.get("Offers")) for f in APP.values())
hir = sum(f["Stage"] == "Hired" for f in APP.values())
print(f"  applied {n} -> screened {scr} ({100*scr/n:.1f}%) -> interviewed {itv} ({100*itv/scr:.1f}% of screened) "
      f"-> offered {ofr} ({100*ofr/itv:.1f}% of interviewed) -> hired {hir} ({100*hir/ofr:.1f}% of offered)")
for label, a_key, b_key in [("applied -> screened", "Applied On", "Screened On"),
                            ("screened -> first interview", "Screened On", "First Interview On"),
                            ("first interview -> offer", "First Interview On", "Offered On"),
                            ("applied -> hired (hires only)", "Applied On", "Closed On")]:
    rows = [f for f in APP.values() if f.get(a_key) and f.get(b_key)
            and (b_key != "Closed On" or f["Stage"] == "Hired")]
    g = sorted(days(f[a_key], f[b_key]) for f in rows)
    print(f"  days {label:<30} n={len(g):>3} median={median(g):>5} p90={g[int(0.9*(len(g)-1))]:>4} max={g[-1]}")

print("\n  Active applications (105) - how long since their last recorded milestone, by stage")
for stage in ("Applied", "Screening", "Interview", "Offer"):
    ages = sorted((PULLED - date.fromisoformat(max(f[k] for k in
                  ("Applied On", "Screened On", "First Interview On", "Final Interview On", "Offered On") if f.get(k)))).days
                  for f in APP.values() if f["Status"] == "Active" and f["Stage"] == stage)
    print(f"    {stage:<10} n={len(ages):>3} median idle days={median(ages):>5} "
          f"idle>30d={sum(a > 30 for a in ages):>3} idle>90d={sum(a > 90 for a in ages):>3}")
act = [f for f in APP.values() if f["Status"] == "Active"]
print("    active applications by opening status:", dict(Counter(OPEN[one(f, "Opening")]["Status"] for f in act)))

io = Counter(f["Outcome"] for f in INT.values())
print(f"\n  Interviews (160): {dict(io)}; not completed = {rate(160 - io['Completed'], 160)}")
print("  Rejection/withdrawal reasons (all closed non-hires):",
      dict(Counter(f.get("Rejection Reason") for f in APP.values() if f["Stage"] in ("Rejected", "Withdrawn")).most_common()))
comp = [f for f in APP.values() if f.get("Rejection Reason") == "Comp Expectation"]
print("  'Comp Expectation' rejections by furthest point reached:",
      dict(Counter("interviewed" if f.get("Interviews") else "screened" if f.get("Screened On") else "applied" for f in comp)))
