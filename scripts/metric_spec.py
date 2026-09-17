"""Reference implementation of the offer acceptance rate spec (DELIVERABLE.md section 4).

Runs the spec on the cached Offers table as of the pull date, then breaks it with
synthetic edge cases: revised offer, accept then renege, cancelled opening, missing offered date.

Usage: python3 scripts/metric_spec.py
"""
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import sqrt
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
WINDOW_DAYS = 365        # trailing window, inclusive of the as-of date
UNRESOLVED_AFTER = 30    # days a Pending offer may stay open
MIN_DECIDED = 20         # below this the dashboard shows counts, not a percentage
NUMERATOR = {"Accepted", "Reneged"}          # Reneged = accepted, then did not start
DENOMINATOR = NUMERATOR | {"Declined"}
KNOWN = DENOMINATOR | {"Pending", "Withdrawn"}  # Withdrawn = company pulled the offer before a decision


def load(table):
    return json.loads((RAW / f"{table}.json").read_text())


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def half_up(x):
    """Round half up to 1 decimal, as the spec says (Python's default is half even)."""
    return str(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def pct(k, n):
    return half_up(Decimal(100 * k) / Decimal(n)) + "%"


def classify(f, as_of):
    """State of one offer. Uses only the Offers row, never the application's Stage."""
    if not f.get("Offered On"):
        return "broken: no offered date"
    if f["Status"] not in KNOWN:
        return "broken: unknown status"
    if f["Status"] == "Pending":
        if f.get("Decision On"):
            return "broken: pending with decision date"
        age = (as_of - date.fromisoformat(f["Offered On"])).days
        return "unresolved" if age > UNRESOLVED_AFTER else "pending"
    return f["Status"].lower()


def compute(offers, as_of):
    """offers: list of {'id', 'fields'}. Returns the numbers the dashboard needs."""
    # One counted offer per application: the latest by Offers.Offered On, tie broken by highest Offer ID.
    # An offer with no Offered On cannot be ordered, so it goes straight to the fix list.
    by_app = defaultdict(list)
    counted, superseded = [r for r in offers if not r["fields"].get("Offered On")], []
    for r in offers:
        if r["fields"].get("Offered On"):
            by_app[r["fields"]["Application"][0]].append(r)
    for rows in by_app.values():
        rows = sorted(rows, key=lambda r: (r["fields"]["Offered On"], r["fields"]["Offer ID"]))
        counted.append(rows[-1])
        superseded.extend(rows[:-1])
    start = as_of - timedelta(days=WINDOW_DAYS - 1)
    states = Counter()
    listed = []
    for r in counted:
        f = r["fields"]
        state = classify(f, as_of)
        if state == "broken: no offered date":
            states[state] += 1
            listed.append((f["Offer ID"], state))
            continue
        if not start <= date.fromisoformat(f["Offered On"]) <= as_of:
            continue
        states[state] += 1
        if state.startswith("broken") or state == "unresolved":
            listed.append((f["Offer ID"], state))
    acc = states["accepted"] + states["reneged"]
    decided = acc + states["declined"]
    stuck = states["unresolved"] + states["broken: pending with decision date"]
    return {"window": (start, as_of), "states": states, "accepted": acc, "decided": decided,
            "stuck": stuck, "listed": sorted(listed), "superseded": len(superseded)}


def dashboard(res):
    s, acc, n, stuck = res["states"], res["accepted"], res["decided"], res["stuck"]
    print(f"    window {res['window'][0]} to {res['window'][1]} | accepted {acc}, declined {s['declined']}, "
          f"pending {s['pending']}, unresolved {s['unresolved']}, "
          f"broken {sum(v for k, v in s.items() if k.startswith('broken'))}, withdrawn {s['withdrawn']}, "
          f"superseded {res['superseded']}")
    if n == 0:
        print("    DASHBOARD: 'No decided offers in this window' + counts")
    elif n < MIN_DECIDED:
        print(f"    DASHBOARD: 'Insufficient data' ({n} decided, needs {MIN_DECIDED}) + counts. No percentage.")
    else:
        lo, hi = wilson(acc, n)
        line = f"    DASHBOARD: {pct(acc, n)} ({acc} of {n}), 95% interval {half_up(100*lo)}% to {half_up(100*hi)}%"
        if res["listed"]:   # any Unresolved or Broken offer makes the state Ambiguous
            line += f" | AMBIGUOUS: {len(res['listed'])} offers need fixing"
            if stuck:       # the range covers only offers that have a place in the window
                line += f"; if all declined {pct(acc, n + stuck)}, if all accepted {pct(acc + stuck, n + stuck)}"
            else:
                line += "; no range (the broken offers have no place in the window)"
        else:
            line += " | NORMAL"
        print(line)
    for oid, why in res["listed"]:
        print(f"      fix list: {oid} {why}")


OFFERS = load("Offers")
APPS = {r["id"]: r["fields"] for r in load("Applications")}
OPEN = {r["id"]: r["fields"] for r in load("Job_Openings")}
AS_OF = date.fromisoformat(json.loads((RAW / "_manifest.json").read_text())["pulled_at"][:10])

print("=" * 96)
print(f"A. THE SPEC ON THE REAL DATA ({len(OFFERS)} offers), as of {AS_OF}")
print("=" * 96)
real = compute(OFFERS, AS_OF)
dashboard(real)

print("\n  Quarterly view (calendar quarter of Offers.Offered On): counts only, never a percentage")
q = defaultdict(Counter)
for r in OFFERS:
    f = r["fields"]
    d = f["Offered On"]
    q[f"{d[:4]}-Q{(int(d[5:7]) - 1) // 3 + 1}"][classify(f, AS_OF)] += 1
for k in sorted(q):
    c = q[k]
    print(f"    {k}: accepted {c['accepted']}, declined {c['declined']}, decided {c['accepted'] + c['declined']}, "
          f"pending {c['pending']}, unresolved {c['unresolved']}, broken {c['broken: pending with decision date']}")
print("    largest quarter by decided offers:", max(c["accepted"] + c["declined"] for c in q.values()),
      f"(minimum for a percentage is {MIN_DECIDED})")

print("\n  What happens if an engineer reads the application instead of the offer")
offered_apps = [a for a in APPS.values() if a.get("Offers")]
hired = sum(a["Stage"] == "Hired" for a in offered_apps)
print(f"    Application Stage=Hired / applications with an offer: {hired}/{len(offered_apps)} = {pct(hired, len(offered_apps))}")
mism = [(r["fields"]["Offer ID"], r["fields"]["Offered On"], APPS[r["fields"]["Application"][0]].get("Offered On"))
        for r in OFFERS if r["fields"]["Offered On"] != APPS[r["fields"]["Application"][0]].get("Offered On")]
print(f"    Offered On differs between the two tables on {len(mism)}/{len(OFFERS)} offers:")
for oid, o, a in mism:
    print(f"      {oid}: Offers {o}, Applications {a}, gap {abs((date.fromisoformat(o) - date.fromisoformat(a)).days)} days")

print("\n  Offers by the status of their opening")
by_open = defaultdict(Counter)
for r in OFFERS:
    f = r["fields"]
    by_open[OPEN[APPS[f["Application"][0]]["Opening"][0]]["Status"]][f["Status"]] += 1
for k, c in by_open.items():
    print(f"    {k:<10} {dict(c)}")
canc = by_open["Cancelled"]
a_x, d_x = real["accepted"] - canc["Accepted"], real["states"]["declined"] - canc["Declined"]
print(f"    offers on Cancelled openings: {sum(canc.values())}/{len(OFFERS)}; on On Hold openings: "
      f"{sum(by_open['On Hold'].values())}/{len(OFFERS)}")
print(f"    rate if offers on Cancelled openings were dropped: {a_x}/{a_x + d_x} = {pct(a_x, a_x + d_x)} "
      f"(spec keeps them: {pct(real['accepted'], real['decided'])})")

print("\n  Other checks the spec relies on")
per_app = Counter(r["fields"]["Application"][0] for r in OFFERS)
print(f"    applications with more than one offer today: {sum(v > 1 for v in per_app.values())}/{len(per_app)}")
print(f"    offers with no Offered On: {sum(not r['fields'].get('Offered On') for r in OFFERS)}/{len(OFFERS)}")
print(f"    decided offers with no Decision On: "
      f"{sum(r['fields']['Status'] != 'Pending' and not r['fields'].get('Decision On') for r in OFFERS)}/{real['decided']}")
dup_ids = {k for k, v in Counter(a["Application ID"] for a in APPS.values()).items() if v > 1}
print(f"    offers whose application has a non-unique Application ID (join must use the record link): "
      f"{sum(APPS[r['fields']['Application'][0]]['Application ID'] in dup_ids for r in OFFERS)}/{len(OFFERS)}")

print("\n  People with more than one decided offer (the unit question: offer or person)")
CAND = {r["id"]: r["fields"] for r in load("Candidates")}
by_person = defaultdict(list)
for r in OFFERS:
    f = r["fields"]
    if f["Status"] in DENOMINATOR:
        by_person[APPS[f["Application"][0]]["Candidate"][0]].append(f)
multi = {c: v for c, v in by_person.items() if len(v) > 1}
for c, v in multi.items():
    print(f"    {CAND[c]['Candidate ID']} {CAND[c]['Full Name']}: " + ", ".join(
        f"{f['Offer ID']} {f['Status']} {f['Offered On']}" for f in sorted(v, key=lambda f: f['Offered On'])))
n_people = len(by_person)
any_acc = sum(any(f["Status"] in NUMERATOR for f in v) for v in by_person.values())
last_acc = sum(sorted(v, key=lambda f: f["Offered On"])[-1]["Status"] in NUMERATOR for v in by_person.values())
print(f"    decided offers {real['decided']} -> people with a decided offer {n_people}; "
      f"people with two decided offers {len(multi)}")
print(f"    per person, any acceptance counts: {any_acc}/{n_people} = {pct(any_acc, n_people)}; "
      f"per person, latest offer counts: {last_acc}/{n_people} = {pct(last_acc, n_people)}; "
      f"per offer (the spec): {pct(real['accepted'], real['decided'])}")

print("\n" + "=" * 96)
print("B. BREAKING THE SPEC - synthetic rows added to the real 36")
print("=" * 96)


def synth(oid, app, status, offered=None, decision=None):
    f = {"Offer ID": oid, "Application": [app], "Status": status}
    if offered:
        f["Offered On"] = offered
    if decision:
        f["Decision On"] = decision
    return {"id": oid, "fields": f}


declined = next(r for r in OFFERS if r["fields"]["Status"] == "Declined")
app_d = declined["fields"]["Application"][0]
print(f"\n  B1. Revised offer: {declined['fields']['Offer ID']} was Declined; a second, higher offer on the same "
      "application is Accepted")
dashboard(compute(OFFERS + [synth("OFF-90001", app_d, "Accepted", "2026-08-20", "2026-08-25")], AS_OF))
print(f"      -> the first offer is superseded, the application counts once, as Accepted. Without the rule it "
      f"would count twice: {real['accepted'] + 1}/{real['decided'] + 1} = {pct(real['accepted'] + 1, real['decided'] + 1)}.")
print("    same application, but the undated offer is the newer one (must reach the fix list, not vanish):")
dashboard(compute(OFFERS + [synth("OFF-90004", app_d, "Accepted", None, "2026-08-25")], AS_OF))

accepted = next(r for r in OFFERS if r["fields"]["Status"] == "Accepted")
print(f"\n  B2. Accept then renege: {accepted['fields']['Offer ID']} was Accepted, candidate does not start")
flipped = [dict(r, fields=dict(r["fields"], Status="Declined")) if r is accepted else r for r in OFFERS]
print("    if the recruiter overwrites Status to Declined (wrong: history changes):")
dashboard(compute(flipped, AS_OF))
reneged = [dict(r, fields=dict(r["fields"], Status="Reneged")) if r is accepted else r for r in OFFERS]
print("    with Status=Reneged (spec: still an accepted offer; renege is a separate count):")
dashboard(compute(reneged, AS_OF))

print("\n  B3. Offer on a cancelled opening, company pulls a live offer before the candidate decides")
dashboard(compute(OFFERS + [synth("OFF-90002", "recSYNTH1", "Withdrawn", "2026-09-01")], AS_OF))
print("      -> Withdrawn is outside the rate and shown as a count. "
      "A candidate decision on a cancelled opening still counts (see A).")

print("\n  B4. Offer with no offered date")
dashboard(compute(OFFERS + [synth("OFF-90003", "recSYNTH2", "Accepted", None, "2026-09-05")], AS_OF))
print("      -> cannot be placed in a window: excluded and put on the fix list, no fallback to the Applications date.")

print("\n  B5. A year with fewer than 20 decided offers (as of 2026-02-01)")
dashboard(compute(OFFERS, date(2026, 2, 1)))

print("\n" + "=" * 96)
print("C. TESTS FOR THE GAPS THE SECOND ENGINEER FOUND")
print("=" * 96)
clean = [r for r in OFFERS if r["fields"]["Status"] != "Pending"]
print("\n  C1. State with 20+ decided and nothing wrong (the 5 pending offers removed)")
dashboard(compute(clean, AS_OF))
print("\n  C2. Same, plus one undated Accepted offer: Ambiguous, fix list, no range")
dashboard(compute(clean + [synth("OFF-90003", "recSYNTH2", "Accepted", None, "2026-09-05")], AS_OF))
app_a = accepted["fields"]["Application"][0]
print(f"\n  C3. Step order: a later Pending offer on the application of {accepted['fields']['Offer ID']} (Accepted) "
      "supersedes it, whatever its status")
dashboard(compute(clean + [synth("OFF-90008", app_a, "Pending", "2026-09-10")], AS_OF))
print("\n  C4. Window edge: an Accepted offer dated the as-of date minus 364 days is in, minus 365 days is out")
for d in (AS_OF - timedelta(days=364), AS_OF - timedelta(days=365)):
    print(f"    offered {d}:")
    dashboard(compute(clean + [synth("OFF-90007", "recSYNTH5", "Accepted", d.isoformat(), d.isoformat())], AS_OF))
print("\n  C5. Past as-of date 2026-02-01, run on today's statuses (screen says 'Based on current statuses')")
dashboard(compute(OFFERS, date(2026, 2, 1)))
print("\n  C6. Empty is checked before Insufficient data (as of 2025-06-01, before any offer)")
dashboard(compute(OFFERS, date(2025, 6, 1)))
