#!/usr/bin/env python3
"""Engineer B: offer acceptance rate, implemented from DELIVERABLE.md section 4 only."""
import copy
import json
import math
import re
from collections import OrderedDict, defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

RAW = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "data", "raw") + "/"
Z95 = 1.959963984540054
MIN_N = 20
ACCEPTED = ("Accepted", "Reneged")
KNOWN = ("Accepted", "Reneged", "Declined", "Pending", "Withdrawn")


def load(name):
    with open(RAW + name) as fh:
        return json.load(fh)


def pdate(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def offer_num(oid):
    m = re.search(r"(\d+)\s*$", oid or "")
    return (int(m.group(1)) if m else -1, oid or "")


def pct(n, d):
    q = (Decimal(n) * 100 / Decimal(d)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return "%s%%" % q


def pctf(x):
    q = Decimal(repr(x * 100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return "%s%%" % q


def wilson(k, n):
    p = k / n
    z2 = Z95 * Z95
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def normalise(records):
    out = []
    for r in records:
        f = r.get("fields", {})
        link = f.get("Application") or []
        out.append({
            "rec": r["id"],
            "oid": f.get("Offer ID"),
            # join key = linked record id; an unlinked offer is its own group
            "app": link[0] if link else "NOLINK:" + r["id"],
            "status": f.get("Status"),
            "offered": pdate(f.get("Offered On")),
            "decision": pdate(f.get("Decision On")),
            "has_decision": bool(f.get("Decision On")),
        })
    return out


def classify(offers, asof):
    """Returns list of dicts with 'cls' and 'reasons'. Offers dated after asof are 'future' (invisible)."""
    rows = [dict(o) for o in offers]
    # 1. undated offers are Broken, and never take part in superseding
    dated = defaultdict(list)
    for o in rows:
        o["reasons"] = []
        if o["offered"] is None:
            o["cls"] = "broken"
            o["reasons"].append("no Offered On")
            if o["status"] == "Pending" and o["has_decision"]:
                o["reasons"].append("Pending with a Decision On")
            if o["status"] not in KNOWN:
                o["reasons"].append("Status not in spec: %r" % o["status"])
        elif o["offered"] > asof:
            o["cls"] = "future"
        else:
            dated[o["app"]].append(o)
    # 2. one counted offer per application: latest Offered On, tie -> highest Offer ID
    for app, lst in dated.items():
        lst.sort(key=lambda o: (o["offered"], offer_num(o["oid"])))
        for o in lst[:-1]:
            o["cls"] = "superseded"
            o["superseded_by"] = lst[-1]["oid"]
        o = lst[-1]
        st = o["status"]
        if st == "Pending" and o["has_decision"]:
            o["cls"] = "broken"
            o["reasons"].append("Pending with a Decision On")
        elif st not in KNOWN:
            o["cls"] = "broken"
            o["reasons"].append("Status not in spec: %r" % st)
        elif st == "Pending":
            days = (asof - o["offered"]).days
            o["days_open"] = days
            if days <= 30:
                o["cls"] = "pending"
            else:
                o["cls"] = "unresolved"
                o["reasons"].append("Unresolved: Pending, no Decision On, open %d days" % days)
        elif st in ACCEPTED:
            o["cls"] = "accepted"
        elif st == "Declined":
            o["cls"] = "declined"
        elif st == "Withdrawn":
            o["cls"] = "withdrawn"
    return rows


def dashboard(offers, asof, title):
    start = asof - timedelta(days=364)  # 365 calendar dates, both ends included
    rows = classify(offers, asof)

    def inwin(o):
        return o["offered"] is not None and start <= o["offered"] <= asof

    win = [o for o in rows if inwin(o)]
    undated = [o for o in rows if o["offered"] is None]
    cnt = lambda c: sum(1 for o in win if o["cls"] == c)
    num = cnt("accepted")
    declined = cnt("declined")
    den = num + declined
    pending = cnt("pending")
    unresolved = cnt("unresolved")
    broken_dated = cnt("broken")
    broken = broken_dated + len(undated)  # undated cannot be placed in a window: always shown
    withdrawn = cnt("withdrawn")
    superseded = cnt("superseded")
    pend_with_dec = sum(1 for o in win if o["cls"] == "broken"
                        and "Pending with a Decision On" in o["reasons"])
    k = unresolved + pend_with_dec
    fix = [o for o in win if o["cls"] in ("unresolved", "broken")] + undated
    fix.sort(key=lambda o: offer_num(o["oid"]))
    warn = [o for o in win if o["cls"] in ("accepted", "declined") and not o["has_decision"]]

    if den == 0:
        state = "Empty"
    elif den < MIN_N:
        state = "Insufficient data"
    elif k > 0:
        state = "Ambiguous"
    elif broken > 0:
        state = "Ambiguous (SPEC GAP: broken offers exist but none is Unresolved or Pending-with-Decision; spec names no state)"
    else:
        state = "Normal"

    print("=" * 78)
    print(title)
    print("-" * 78)
    print("as-of            : %s" % asof)
    print("window           : %s to %s (inclusive, %d dates)" % (start, asof, (asof - start).days + 1))
    print("offers in table  : %d (dated after as-of, ignored: %d; dated before window: %d)" % (
        len(rows), sum(1 for o in rows if o["cls"] == "future"),
        sum(1 for o in rows if o["offered"] is not None and o["offered"] < start)))
    print("numerator        : %d (accepted incl. reneged)" % num)
    print("denominator      : %d (decided = numerator + %d declined)" % (den, declined))
    print("STATE            : %s" % state)
    if state.startswith("Empty"):
        print("display          : No decided offers")
    elif state.startswith("Insufficient"):
        print("display          : Insufficient data  (%d of %d; minimum n is %d)" % (num, den, MIN_N))
    else:
        lo, hi = wilson(num, den)
        amber = " [AMBER]" if state.startswith("Ambiguous") else ""
        print("rate             : %s (%d of %d)%s" % (pct(num, den), num, den, amber))
        print("95%% Wilson       : %s to %s" % (pctf(lo), pctf(hi)))
        if state.startswith("Ambiguous"):
            print("ambiguous range  : %s (%d of %d, all %d declined) to %s (%d of %d, all %d accepted)" % (
                pct(num, den + k), num, den + k, k, pct(num + k, den + k), num + k, den + k, k))
            print("                   -> link to fix list (%d offers)" % len(fix))
    print("Pending          : %d" % pending)
    print("Unresolved       : %d" % unresolved)
    print("Broken           : %d (of which Pending-with-Decision in window: %d, undated: %d)" % (
        broken, pend_with_dec, len(undated)))
    print("Withdrawn        : %d" % withdrawn)
    print("superseded       : %d" % superseded)
    print("fix list (%d):" % len(fix))
    for o in fix:
        print("   %s  offered=%s status=%s  reason: %s" % (
            o["oid"], o["offered"], o["status"], "; ".join(o["reasons"])))
    sup = [o for o in win if o["cls"] == "superseded"]
    for o in sup:
        print("   (superseded, not on fix list) %s offered=%s status=%s superseded by %s" % (
            o["oid"], o["offered"], o["status"], o["superseded_by"]))
    if warn:
        print("data warning: decided offers with no Decision On: %s" % ", ".join(o["oid"] for o in warn))
    return {"num": num, "den": den, "state": state}


def quarterly(offers, asof, title):
    rows = classify(offers, asof)
    q = OrderedDict()
    keys = ("accepted", "declined", "decided", "pending", "unresolved", "broken", "withdrawn", "superseded")
    for o in sorted(rows, key=lambda o: (o["offered"] is None, o["offered"] or date.min)):
        if o["cls"] == "future":
            continue
        label = "undated" if o["offered"] is None else "%d-Q%d" % (o["offered"].year, (o["offered"].month - 1) // 3 + 1)
        b = q.setdefault(label, dict.fromkeys(keys, 0))
        b[o["cls"]] += 1
        if o["cls"] in ("accepted", "declined"):
            b["decided"] += 1
    print("=" * 78)
    print(title)
    print("-" * 78)
    print("%-9s" % "quarter" + "".join("%11s" % k for k in keys))
    tot = dict.fromkeys(keys, 0)
    for label, b in q.items():
        print("%-9s" % label + "".join("%11d" % b[k] for k in keys))
        for k in keys:
            tot[k] += b[k]
    print("%-9s" % "total" + "".join("%11d" % tot[k] for k in keys))
    print("largest quarter by decided: %d" % max(b["decided"] for b in q.values()))


def add(offers, oid, app, status, offered=None, decision=None):
    new = copy.deepcopy(offers)
    new.append({"rec": "recNEW" + oid, "oid": oid, "app": app, "status": status,
                "offered": pdate(offered), "decision": pdate(decision), "has_decision": bool(decision)})
    return new


def change(offers, oid, status):
    new = copy.deepcopy(offers)
    for o in new:
        if o["oid"] == oid:
            o["status"] = status
    return new


def main():
    raw = load("Offers.json")
    offers = normalise(raw)
    A = date(2026, 9, 17)
    app12 = next(o["app"] for o in offers if o["oid"] == "OFF-00012")
    per_app = defaultdict(int)
    for o in offers:
        per_app[o["app"]] += 1
    print("real offers: %d; applications with >1 offer: %d; offers without a link: %d" % (
        len(offers), sum(1 for v in per_app.values() if v > 1),
        sum(1 for o in offers if o["app"].startswith("NOLINK"))))

    dashboard(offers, A, "1. REAL DATA as-of 2026-09-17")
    dashboard(offers, date(2026, 2, 1), "2. REAL DATA as-of 2026-02-01")
    quarterly(offers, A, "3. QUARTERLY VIEW as-of 2026-09-17 (counts only)")

    dashboard(add(offers, "OFF-90001", app12, "Accepted", "2026-08-20", "2026-08-25"), A,
              "4a. + OFF-90001 Accepted 2026-08-20 on OFF-00012's application")
    dashboard(change(offers, "OFF-00024", "Reneged"), A, "4b-i. OFF-00024 -> Reneged")
    dashboard(change(offers, "OFF-00024", "Declined"), A, "4b-ii. OFF-00024 -> Declined")
    dashboard(add(offers, "OFF-90002", "recSYNTH1", "Withdrawn", "2026-09-01"), A,
              "4c. + OFF-90002 Withdrawn 2026-09-01 (recSYNTH1)")
    dashboard(add(offers, "OFF-90003", "recSYNTH2", "Accepted", None, "2026-09-05"), A,
              "4d. + OFF-90003 Accepted, no Offered On (recSYNTH2)")
    dashboard(add(offers, "OFF-90004", app12, "Accepted", None, "2026-08-25"), A,
              "4e. + OFF-90004 Accepted, no Offered On, on OFF-00012's application")
    dashboard(add(offers, "OFF-90005", "recSYNTH3", "Expired", "2026-07-01"), A,
              "4f. + OFF-90005 Expired 2026-07-01 (recSYNTH3)")
    dashboard(add(offers, "OFF-90006", "recSYNTH4", "Pending", "2026-08-18"), A,
              "4g-i. + OFF-90006 Pending 2026-08-18 (30 days)")
    dashboard(add(offers, "OFF-90006", "recSYNTH4", "Pending", "2026-08-17"), A,
              "4g-ii. + OFF-90006 Pending 2026-08-17 (31 days)")
    dashboard(add(offers, "OFF-90007", "recSYNTH5", "Accepted", "2025-09-18"), A,
              "4h-i. + OFF-90007 Accepted 2025-09-18")
    dashboard(add(offers, "OFF-90007", "recSYNTH5", "Accepted", "2025-09-17"), A,
              "4h-ii. + OFF-90007 Accepted 2025-09-17")

    claim_checks(raw, offers, A)


def claim_checks(raw, offers, A):
    """Independent checks of the spec's 'In this data' / 'Effect' claims. Not part of the metric."""
    print("=" * 78)
    print("CLAIM CHECKS (not part of the metric; Applications / Job_Openings read only here)")
    print("-" * 78)
    apps = {r["id"]: r.get("fields", {}) for r in load("Applications.json")}
    jobs = {r["id"]: r.get("fields", {}) for r in load("Job_Openings.json")}
    rows = classify(offers, A)
    decided = [o for o in rows if o["cls"] in ("accepted", "declined")]
    print("pending with decision date: %d of %d" % (
        sum(1 for o in offers if o["status"] == "Pending" and o["has_decision"]), len(offers)))
    print("pending, no decision, >30d: %s" % [o["oid"] for o in rows if o["cls"] == "unresolved"])
    print("max days offered->decision among decided: %s" % max(
        (o["decision"] - o["offered"]).days for o in decided if o["decision"]))
    gaps = []
    for o in offers:
        ad = pdate(apps.get(o["app"], {}).get("Offered On"))
        if o["offered"] and ad != o["offered"]:
            gaps.append((o["oid"], str(o["offered"]), str(ad), abs((ad - o["offered"]).days) if ad else None))
    print("offered date differs Offers vs Applications: %d -> %s" % (len(gaps), gaps))
    dec = [o for o in offers if o["status"] == "Declined"]
    print("declined offers whose application Stage is 'Offer': %d of %d (stages: %s)" % (
        sum(1 for o in dec if apps.get(o["app"], {}).get("Stage") == "Offer"), len(dec),
        sorted(set(str(apps.get(o["app"], {}).get("Stage")) for o in dec))))
    stages = defaultdict(int)
    for o in offers:
        stages[str(apps.get(o["app"], {}).get("Stage"))] += 1
    print("application Stage across the 36 offers: %s" % dict(stages))
    for label in ("Hired", "Offer Accepted", "Accepted"):
        if stages.get(label):
            print("   stage-based rate using %r / all offers: %s (%d of %d)" % (
                label, pct(stages[label], len(offers)), stages[label], len(offers)))
    acc_all = sum(1 for o in offers if o["status"] in ACCEPTED)
    print("accepted / all 36 offers (pending inside): %s (%d of %d)" % (pct(acc_all, len(offers)), acc_all, len(offers)))
    # per person
    by_cand = defaultdict(list)
    for o in decided:
        c = (apps.get(o["app"], {}).get("Candidate") or ["?" + o["app"]])[0]
        by_cand[c].append(o)
    multi = {c: [(x["oid"], x["cls"]) for x in v] for c, v in by_cand.items() if len(v) > 1}
    print("candidates with >1 decided offer: %d -> %s" % (len(multi), multi))
    pa = sum(1 for v in by_cand.values() if any(x["cls"] == "accepted" for x in v))
    print("one per person (accepted if any accepted): %s (%d of %d)" % (pct(pa, len(by_cand)), pa, len(by_cand)))
    # opening status
    ost = defaultdict(int)
    keep = []
    for o in offers:
        op = (apps.get(o["app"], {}).get("Opening") or [None])[0]
        s = jobs.get(op, {}).get("Status")
        ost[str(s)] += 1
        o["_open"] = s
    print("opening Status across the 36 offers: %s" % dict(ost))
    keep = [o for o in decided if next(x for x in offers if x["rec"] == o["rec"])["_open"] != "Cancelled"]
    ka = sum(1 for o in keep if o["cls"] == "accepted")
    print("decided, dropping Cancelled openings: %s (%d of %d)" % (pct(ka, len(keep)), ka, len(keep)))
    # Application ID uniqueness
    ids = defaultdict(list)
    for rid, f in apps.items():
        ids[f.get("Application ID")].append(rid)
    shared = [o["oid"] for o in offers if len(ids[apps.get(o["app"], {}).get("Application ID")]) > 1]
    print("offers whose Application ID is shared by >1 application record: %d -> %s" % (len(shared), shared))
    print("decided offers with no Decision On: %d of %d" % (sum(1 for o in decided if not o["has_decision"]), len(decided)))


if __name__ == "__main__":
    main()
