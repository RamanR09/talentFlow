#!/usr/bin/env python3
"""Engineer C: offer acceptance rate, built only from section 4 of DELIVERABLE.md."""
import json, copy, math, collections
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

RAW = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "data", "raw") + "/"
Z = 1.96
MIN_N = 20


def load(name):
    with open(RAW + name) as f:
        return json.load(f)


def d(s):
    return date.fromisoformat(s) if s else None


def pct(num, den):
    """Percentage rounded half up to 1 decimal, from exact integers."""
    return str((Decimal(num) * 100 / Decimal(den)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def pct_float(x):
    return str(Decimal(repr(x * 100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def wilson(k, n):
    p = k / n
    z2 = Z * Z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return pct_float(centre - half), pct_float(centre + half)


def oid(o):
    return o["fields"].get("Offer ID", "")


def app_key(o):
    # AMBIGUITY (not hit): empty or multi link. Choice: whole link tuple; empty -> own record id.
    link = o["fields"].get("Application") or []
    return tuple(link) if link else ("NOAPP", o["id"])


def compute(offers, asof, supersede=True):
    asof = d(asof) if isinstance(asof, str) else asof
    first = asof - timedelta(days=364)
    fix = []  # (offer id, class, reason)
    warnings = []

    # Step 1
    dated, undated = [], []
    for o in offers:
        (dated if o["fields"].get("Offered On") else undated).append(o)
    for o in undated:
        fix.append((oid(o), "Broken", "no Offered On"))

    # Step 2
    superseded = []
    if supersede:
        groups = collections.defaultdict(list)
        for o in dated:
            groups[app_key(o)].append(o)
        kept = []
        for g in groups.values():
            g.sort(key=lambda o: (d(o["fields"]["Offered On"]), oid(o)))
            kept.append(g[-1])
            superseded.extend(g[:-1])
    else:
        kept = list(dated)

    # Step 3
    inwin = [o for o in kept if first <= d(o["fields"]["Offered On"]) <= asof]
    outside = len(kept) - len(inwin)

    # Step 4
    c = collections.Counter()
    range_k = 0
    quarters = collections.Counter()
    for o in inwin:
        f = o["fields"]
        st = f.get("Status")
        off = d(f["Offered On"])
        has_dec = bool(f.get("Decision On"))
        q = "%dQ%d" % (off.year, (off.month - 1) // 3 + 1)
        if st in ("Accepted", "Reneged"):
            c["accepted"] += 1
            c["decided"] += 1
            quarters[q] += 1
            if st == "Reneged":
                c["reneged"] += 1
            if not has_dec:
                warnings.append((oid(o), "decided offer with no Decision On"))
        elif st == "Declined":
            c["decided"] += 1
            quarters[q] += 1
            if not has_dec:
                warnings.append((oid(o), "decided offer with no Decision On"))
        elif st == "Withdrawn":
            c["withdrawn"] += 1
        elif st == "Pending":
            if has_dec:
                c["broken_window"] += 1
                range_k += 1
                fix.append((oid(o), "Broken", "Status Pending with Decision On %s" % f["Decision On"]))
            else:
                days = (asof - off).days
                if days <= 30:
                    c["pending"] += 1
                else:
                    c["unresolved"] += 1
                    range_k += 1
                    fix.append((oid(o), "Unresolved", "Pending, no Decision On, offered %d days before as-of" % days))
        else:
            c["broken_window"] += 1
            fix.append((oid(o), "Broken", "Status %r not named in the definition table" % st))

    acc, dec = c["accepted"], c["decided"]
    broken_total = c["broken_window"] + len(undated)
    res = dict(first=first, last=asof, acc=acc, dec=dec, pending=c["pending"], unresolved=c["unresolved"],
               broken_window=c["broken_window"], broken_undated=len(undated), broken=broken_total,
               withdrawn=c["withdrawn"], reneged=c["reneged"], superseded=len(superseded),
               superseded_ids=sorted(oid(o) for o in superseded), outside=outside,
               fix=sorted(fix), warnings=warnings, quarters=dict(sorted(quarters.items())),
               rate=None, ci=None, rng=None)
    if dec:
        res["rate"] = pct(acc, dec)
        res["ci"] = wilson(acc, dec)
    if dec == 0:
        res["state"] = "Empty (No decided offers)"
    elif dec < MIN_N:
        res["state"] = "Insufficient data"
    elif c["unresolved"] or broken_total:
        res["state"] = "Ambiguous"
        if range_k:
            res["rng"] = (pct(acc, dec + range_k), pct(acc + range_k, dec + range_k), range_k)
    else:
        res["state"] = "Normal"
    return res


def show(label, r):
    print("=" * 78)
    print(label)
    print("  window: %s .. %s (%d days)" % (r["first"], r["last"], (r["last"] - r["first"]).days + 1))
    print("  numerator=%d denominator=%d  ('%d of %d')" % (r["acc"], r["dec"], r["acc"], r["dec"]))
    shown = r["state"] in ("Normal", "Ambiguous")
    if r["rate"] is None:
        print("  rate: undefined (0 decided)   interval: undefined")
    else:
        print("  rate=%s%%  interval=%s%% .. %s%%   [%s on dashboard]" % (
            r["rate"], r["ci"][0], r["ci"][1], "SHOWN" if shown else "computed but NOT shown"))
    print("  Pending=%d Unresolved=%d Broken=%d (in-window %d + undated %d) Withdrawn=%d superseded=%d %s" % (
        r["pending"], r["unresolved"], r["broken"], r["broken_window"], r["broken_undated"],
        r["withdrawn"], r["superseded"], r["superseded_ids"] if r["superseded_ids"] else ""))
    print("  (Reneged inside numerator=%d; kept offers outside window=%d)" % (r["reneged"], r["outside"]))
    print("  STATE: %s" % r["state"])
    if r["rng"]:
        print("  range: %s%% .. %s%%  (over %d Unresolved / Pending-with-decision offers)" % r["rng"])
    else:
        print("  range: none shown")
    print("  fix list (%d):" % len(r["fix"]))
    for x in r["fix"]:
        print("     %s | %s | %s" % x)
    for w in r["warnings"]:
        print("  data warning: %s %s" % w)


def mk(offer_id, app, status, offered=None, decided=None):
    f = {"Offer ID": offer_id, "Application": [app], "Status": status}
    if offered:
        f["Offered On"] = offered
    if decided:
        f["Decision On"] = decided
    return {"id": "recNEW" + offer_id[-5:], "fields": f}


def main():
    real = load("Offers.json")
    by_id = {oid(o): o for o in real}
    clean = [o for o in real if o["fields"].get("Status") != "Pending"]
    A = "2026-09-17"

    def with_status(offers, offer_id, status):
        out = copy.deepcopy(offers)
        for o in out:
            if oid(o) == offer_id:
                o["fields"]["Status"] = status
        return out

    show("CASE 1  real offers, as-of 2026-09-17", compute(real, A))
    show("CASE 2  clean set (%d offers), as-of 2026-09-17" % len(clean), compute(clean, A))
    show("CASE 3  clean + OFF-90003 (Accepted, undated, decided 2026-09-05) on recSYNTH2",
         compute(clean + [mk("OFF-90003", "recSYNTH2", "Accepted", None, "2026-09-05")], A))
    app24 = by_id["OFF-00024"]["fields"]["Application"][0]
    show("CASE 4  clean + OFF-90008 (Pending, offered 2026-09-10) on OFF-00024's application",
         compute(clean + [mk("OFF-90008", app24, "Pending", "2026-09-10")], A))
    for dt in ("2025-09-18", "2025-09-17"):
        show("CASE 5  clean + OFF-90007 (Accepted, offered=decided=%s) on recSYNTH5" % dt,
             compute(clean + [mk("OFF-90007", "recSYNTH5", "Accepted", dt, dt)], A))
    show("CASE 6  real offers, as-of 2026-02-01", compute(real, "2026-02-01"))
    show("CASE 7  real offers, as-of 2025-06-01", compute(real, "2025-06-01"))
    app12 = by_id["OFF-00012"]["fields"]["Application"][0]
    c8 = real + [mk("OFF-90001", app12, "Accepted", "2026-08-20", "2026-08-25")]
    show("CASE 8  real + OFF-90001 (Accepted 2026-08-20/25) on OFF-00012's application", compute(c8, A))
    for st in ("Reneged", "Expired"):
        show("CASE 9  real, OFF-00024 Status -> %s" % st, compute(with_status(real, "OFF-00024", st), A))
    for dt in ("2026-08-18", "2026-08-17"):
        show("CASE 10 clean + OFF-90009 (Pending, offered %s) on recSYNTH6" % dt,
             compute(clean + [mk("OFF-90009", "recSYNTH6", "Pending", dt)], A))

    # ------------------------------------------------------------------ PART B
    print("\n" + "#" * 78 + "\nPART B CHECKS\n" + "#" * 78)
    apps = {a["id"]: a for a in load("Applications.json")}
    all_apps = list(apps.values())
    openings = {j["id"]: j for j in load("Job_Openings.json")}
    cands = {c["id"]: c for c in load("Candidates.json")}
    base = compute(real, A)

    def fa(o):
        return apps[o["fields"]["Application"][0]]["fields"]

    pend_dec = [oid(o) for o in real if o["fields"].get("Status") == "Pending" and o["fields"].get("Decision On")]
    print("B1 Pending with Decision On: %d of %d %s" % (len(pend_dec), len(real), pend_dec))
    print("   rate %s (%d of %d), range %s" % (base["rate"], base["acc"], base["dec"], base["rng"]))
    unres = [(oid(o), (d(A) - d(o["fields"]["Offered On"])).days) for o in real
             if o["fields"].get("Status") == "Pending" and not o["fields"].get("Decision On")]
    print("B2 Pending, no Decision On (id, days open):", unres)
    decided = [o for o in real if o["fields"].get("Status") in ("Accepted", "Declined", "Reneged")]
    lags = sorted(((d(o["fields"]["Decision On"]) - d(o["fields"]["Offered On"])).days, oid(o))
                  for o in decided if o["fields"].get("Decision On"))
    print("   decision lag days among decided: min %s max %s; count >20: %d" % (
        lags[0], lags[-1], sum(1 for l in lags if l[0] > 20)))
    diffs = [(oid(o), o["fields"].get("Offered On"), fa(o).get("Offered On")) for o in real
             if o["fields"].get("Offered On") != fa(o).get("Offered On")]
    print("B3 Offered On differs Offers vs Applications: %d of %d" % (len(diffs), len(real)))
    for x in diffs:
        gap = (d(x[2]) - d(x[1])).days if x[1] and x[2] else None
        print("     %s offers=%s applications=%s gap=%s" % (x[0], x[1], x[2], gap))
    alt = copy.deepcopy(real)
    for o in alt:
        v = fa(o).get("Offered On")
        if v:
            o["fields"]["Offered On"] = v
    ra = compute(alt, A)
    print("   using Applications.Offered On instead: %s%% (%d of %d) P=%d U=%d B=%d state=%s range=%s" % (
        ra["rate"], ra["acc"], ra["dec"], ra["pending"], ra["unresolved"], ra["broken"], ra["state"], ra["rng"]))
    decl = [o for o in real if o["fields"].get("Status") == "Declined"]
    print("B4 Declined offers: %d; their application Stage: %s" % (
        len(decl), collections.Counter(fa(o).get("Stage") for o in decl)))
    print("   Stage x Offer Status over all offers:",
          dict(collections.Counter((fa(o).get("Stage"), o["fields"].get("Status")) for o in real)))
    stages = collections.Counter(fa(o).get("Stage") for o in real)
    print("   application-stage reading: Hired=%d of %d offers -> %s%%" % (
        stages["Hired"], len(real), pct(stages["Hired"], len(real))))
    # B5 per person
    def person(o):
        return tuple(fa(o).get("Candidate") or [])
    per = collections.defaultdict(list)
    for o in decided:
        per[person(o)].append(o)
    multi = {k: v for k, v in per.items() if len(v) > 1}
    print("B5 people (Candidate link) with decided offers: %d; with >=2 decided offers: %d" % (len(per), len(multi)))
    for k, v in multi.items():
        names = [cands[c]["fields"].get("Full Name") for c in k if c in cands]
        print("     %s %s: %s" % (k, names, [(oid(o), o["fields"]["Offered On"], o["fields"]["Status"]) for o in
                                          sorted(v, key=lambda o: (o["fields"]["Offered On"], oid(o)))]))
    latest = sum(1 for v in per.values()
                 if sorted(v, key=lambda o: (o["fields"]["Offered On"], oid(o)))[-1]["fields"]["Status"] in ("Accepted", "Reneged"))
    anyacc = sum(1 for v in per.values() if any(o["fields"]["Status"] in ("Accepted", "Reneged") for o in v))
    print("   per person, latest offer counts: %s%% (%d of %d)" % (pct(latest, len(per)), latest, len(per)))
    print("   per person, any acceptance counts: %s%% (%d of %d)" % (pct(anyacc, len(per)), anyacc, len(per)))
    # also by name/email in case one human has 2 candidate records
    pername = collections.defaultdict(set)
    for o in decided:
        for c in person(o):
            f = cands[c]["fields"]
            pername[(f.get("Full Name"), )].add(c)
    print("   distinct Full Names among decided-offer candidates: %d (candidate records: %d)" % (
        len(pername), len({c for v in pername.values() for c in v})))
    # B6 opening status
    def opening_status(o):
        op = fa(o).get("Opening") or []
        return openings[op[0]]["fields"].get("Status") if op else None
    print("B6 opening Status over all %d offers: %s" % (len(real), dict(collections.Counter(opening_status(o) for o in real))))
    print("   over decided offers: %s" % dict(collections.Counter(opening_status(o) for o in decided)))
    nc = [o for o in real if opening_status(o) != "Cancelled"]
    r6 = compute(nc, A)
    print("   dropping Cancelled-opening offers: %s%% (%d of %d)" % (r6["rate"], r6["acc"], r6["dec"]))
    # B7 application id uniqueness
    idc = collections.Counter(a["fields"].get("Application ID") for a in all_apps)
    dup = {k: v for k, v in idc.items() if v > 1}
    print("B7 Application IDs used by >1 application record: %d ids %s" % (len(dup), dup if len(dup) < 10 else "..."))
    hit = [(oid(o), fa(o).get("Application ID"), idc[fa(o).get("Application ID")]) for o in real
           if idc[fa(o).get("Application ID")] > 1]
    print("   offers whose application's ID is shared: %d of %d %s" % (len(hit), len(real), hit))
    links = collections.Counter(len(o["fields"].get("Application") or []) for o in real)
    print("   offers by number of Application links:", dict(links))
    print("   applications with >1 offer:", sum(1 for v in collections.Counter(app_key(o) for o in real).values() if v > 1))
    # B8
    r8 = compute(c8, A)
    r8n = compute(c8, A, supersede=False)
    print("B8 revised offer test: with rule %s%% (%d of %d); without rule %s%% (%d of %d)" % (
        r8["rate"], r8["acc"], r8["dec"], r8n["rate"], r8n["acc"], r8n["dec"]))
    # B9
    r9 = compute(with_status(real, "OFF-00024", "Declined"), A)
    r9r = compute(with_status(real, "OFF-00024", "Reneged"), A)
    print("B9 renege: Status Reneged -> %s%% (%d of %d); overwritten with Declined -> %s%% (%d of %d)" % (
        r9r["rate"], r9r["acc"], r9r["dec"], r9["rate"], r9["acc"], r9["dec"]))
    # B10
    r10a = compute(with_status(real, "OFF-00021", "Withdrawn"), A)
    r10b = compute(real + [mk("OFF-90010", "recSYNTH7", "Withdrawn", "2026-08-01")], A)
    r10c = compute(with_status(real, "OFF-00007", "Withdrawn"), A)
    for lab, r in (("OFF-00021 (live, no decision date) -> Withdrawn", r10a), ("extra Withdrawn offer added", r10b),
                   ("OFF-00007 (Pending w/ Decision On) -> Withdrawn", r10c)):
        print("B10 %s: %s%% (%d of %d) CI %s W=%d U=%d B=%d state=%s range=%s fix=%d" % (
            lab, r["rate"], r["acc"], r["dec"], r["ci"], r["withdrawn"], r["unresolved"], r["broken"], r["state"],
            r["rng"], len(r["fix"])))
    # B11
    r11 = compute(real + [mk("OFF-90011", app24, "Accepted", None, "2026-09-05")], A)
    print("B11 undated offer on OFF-00024's application (which has a second, dated offer): %s%% (%d of %d), superseded=%d, fix=%s" % (
        r11["rate"], r11["acc"], r11["dec"], r11["superseded"], [x for x in r11["fix"] if x[0] == "OFF-90011"]))
    nodate = [oid(o) for o in real if not o["fields"].get("Offered On")]
    print("    real offers with no Offered On: %d of %d" % (len(nodate), len(real)))
    # B12
    nd = [oid(o) for o in decided if not o["fields"].get("Decision On")]
    print("B12 decided offers with no Decision On: %d of %d %s" % (len(nd), len(decided), nd))
    negl = [(oid(o)) for o in real if o["fields"].get("Decision On") and o["fields"].get("Offered On")
            and d(o["fields"]["Decision On"]) < d(o["fields"]["Offered On"])]
    print("    offers with Decision On before Offered On:", negl)
    # closing sentence
    print("CLOSING: %s%% (%d of %d), interval %s%% to %s%%, state %s, range %s, offers to fix %d" % (
        base["rate"], base["acc"], base["dec"], base["ci"][0], base["ci"][1], base["state"], base["rng"], len(base["fix"])))
    # quarterly claim (dashboard table)
    print("QUARTERLY decided per quarter, counted offers in the 2026-09-17 window:", base["quarters"])
    wide = compute(real, "2026-09-17")
    qa = collections.Counter()
    for o in decided:
        off = d(o["fields"]["Offered On"])
        qa["%dQ%d" % (off.year, (off.month - 1) // 3 + 1)] += 1
    print("QUARTERLY decided per quarter, all offers no window:", dict(sorted(qa.items())))
    offs = sorted(o["fields"]["Offered On"] for o in real if o["fields"].get("Offered On"))
    print("Offered On range in real data: %s .. %s" % (offs[0], offs[-1]))


if __name__ == "__main__":
    main()
