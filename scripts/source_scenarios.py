"""Source counts (Job Board / Referral / Other) under each way of resolving the data ambiguities.

Ambiguities handled
  R  referral evidence conflicts: Candidates.Source says one thing, Applications.'Referred By' another
  D  repeat applications: the same person applying to the same opening more than once
  P  duplicate people: candidate rows with the same normalised name and phone
  H  repeat hires: one person with more than one Hired application
  C  hires recorded on openings whose Status is Cancelled

Scenarios (application level)
  S0 as recorded          all 350 rows, group = Candidates.Source
  S1 referral evidence    all 350 rows, Referral if Source=Referral OR the application has Referred By
  S2 de-duplicated        repeat applications removed (rule D), group as S0
  S3 combined             rule D rows with S1 grouping
  S4 combined, strict     S3, and a hire on a Cancelled opening is not counted as a hire (rule C)
People level: each person (rule P) counted once, hired once (rule H).

Every table is asserted to reconcile to its total. Results also saved to output/source_scenarios.json.

Usage: python3 scripts/source_scenarios.py
"""
import json
import re
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
GROUPS = ["Job Board", "Referral", "Other"]


def load(table):
    recs = json.loads((RAW / f"{table.replace(' ', '_')}.json").read_text())
    return {r["id"]: r["fields"] for r in recs}


OPEN, CAND, APP = load("Job Openings"), load("Candidates"), load("Applications")


def one(f, k):
    v = f.get(k) or []
    return v[0] if v else None


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def group3(source):
    return source if source in ("Job Board", "Referral") else "Other"


def person_key(cand_rid):
    f = CAND[cand_rid]
    return (re.sub(r"\s+", " ", f["Full Name"].strip().lower()), re.sub(r"\D", "", f["Phone"]))


def recorded(app_rid):
    return group3(CAND[one(APP[app_rid], "Candidate")]["Source"])


def evidence(app_rid):
    return "Referral" if APP[app_rid].get("Referred By") else recorded(app_rid)


def is_hire(app_rid):
    return APP[app_rid]["Stage"] == "Hired"


def is_hire_strict(app_rid):
    return is_hire(app_rid) and OPEN[one(APP[app_rid], "Opening")]["Status"] != "Cancelled"


# Rule D: one row per (person, opening). Keep the Hired row if there is one, otherwise the latest.
by_person_opening = defaultdict(list)
for rid, f in APP.items():
    by_person_opening[(person_key(one(f, "Candidate")), one(f, "Opening"))].append(rid)
DEDUPED, DROPPED = [], []
for rids in by_person_opening.values():
    keep = sorted(rids, key=lambda r: (is_hire(r), APP[r]["Applied On"], r))[-1]
    DEDUPED.append(keep)
    DROPPED.extend(r for r in rids if r != keep)

out = {"scenarios": {}, "people": {}, "misidentified": {}}


def table(code, title, rows, label, hire=is_hire):
    apps, hires = Counter(), Counter()
    for r in rows:
        apps[label(r)] += 1
        hires[label(r)] += hire(r)
    n, h = sum(apps.values()), sum(hires.values())
    assert n == len(rows) and set(apps) <= set(GROUPS)
    print(f"\n{code}  {title}   [application rows={n}, hires={h}]")
    print(f"  {'group':<10}{'apps':>6}{'% of apps':>11}{'hires':>7}{'% of hires':>12}   hires per application (95% CI)")
    res = {"applications": n, "hires": h, "groups": {}}
    for g in GROUPS:
        lo, hi = wilson(hires[g], apps[g])
        print(f"  {g:<10}{apps[g]:>6}{100*apps[g]/n:>10.1f}%{hires[g]:>7}{100*hires[g]/h:>11.1f}%   "
              f"{hires[g]}/{apps[g]} = {100*hires[g]/apps[g]:.1f}%  ({100*lo:.1f}-{100*hi:.1f}%)")
        res["groups"][g] = {"apps": apps[g], "hires": hires[g]}
    non_jb_a, non_jb_h = n - apps["Job Board"], h - hires["Job Board"]
    lo, hi = wilson(non_jb_h, non_jb_a)
    print(f"  {'Non-JB':<10}{non_jb_a:>6}{100*non_jb_a/n:>10.1f}%{non_jb_h:>7}{100*non_jb_h/h:>11.1f}%   "
          f"{non_jb_h}/{non_jb_a} = {100*non_jb_h/non_jb_a:.1f}%  ({100*lo:.1f}-{100*hi:.1f}%)")
    jb_lo, jb_hi = wilson(hires["Job Board"], apps["Job Board"])
    ratio = (non_jb_h / non_jb_a) / (hires["Job Board"] / apps["Job Board"])
    print(f"  Non-JB converts at {ratio:.1f}x Job Board. Job Board interval tops out at {100*jb_hi:.1f}%, "
          f"Non-JB interval starts at {100*lo:.1f}%: {'no overlap' if lo > jb_hi else 'OVERLAP'}")
    res["non_jb"] = {"apps": non_jb_a, "hires": non_jb_h, "ratio_vs_job_board": round(ratio, 1),
                     "job_board_ci_high": round(100 * jb_hi, 1), "non_jb_ci_low": round(100 * lo, 1)}
    out["scenarios"][code] = res


print("=" * 96)
print("PART 1 - APPLICATION-LEVEL COUNTS BY SCENARIO")
print("=" * 96)
table("S0", "As recorded", list(APP), recorded)
table("S1", "Referral evidence (Source=Referral OR Referred By link)", list(APP), evidence)
table("S2", "De-duplicated (repeat person+opening applications removed), as recorded", DEDUPED, recorded)
table("S3", "Combined: de-duplicated + referral evidence", DEDUPED, evidence)
table("S4", "Combined, strict: S3 and hires on Cancelled openings not counted", DEDUPED, evidence, is_hire_strict)

print(f"\n  Rule D removed {len(DROPPED)} repeat application rows:")
for r in DROPPED:
    f = APP[r]
    c = CAND[one(f, "Candidate")]
    print(f"    {r} {f['Application ID']} {c['Candidate ID']} {c['Full Name']} {OPEN[one(f,'Opening')]['Req ID']} "
          f"applied={f['Applied On']} stage={f['Stage']} recorded={recorded(r)}")
cancelled_hires = [r for r in APP if is_hire(r) and not is_hire_strict(r)]
print(f"  Rule C: hires on Cancelled openings = {len(cancelled_hires)}: "
      + ", ".join(f"{APP[r]['Application ID']}({evidence(r)})" for r in cancelled_hires))

print("\n" + "=" * 96)
print("PART 2 - PEOPLE-LEVEL COUNTS (each person once, hired once)")
print("=" * 96)
people = defaultdict(list)
for rid in CAND:
    people[person_key(rid)].append(rid)
print(f"  candidate rows={len(CAND)} -> distinct people={len(people)} "
      f"({sum(len(v) > 1 for v in people.values())} people entered twice)")


def person_apps(rids):
    return [a for c in rids for a in CAND[c].get("Applications", [])]


def person_recorded(rids):
    hired = [one(APP[a], "Candidate") for a in person_apps(rids) if is_hire(a)]
    basis = hired[0] if hired else sorted(rids, key=lambda c: CAND[c]["Created On"])[0]
    return group3(CAND[basis]["Source"])


def person_evidence(rids):
    if any(CAND[c]["Source"] == "Referral" for c in rids) or any(APP[a].get("Referred By") for a in person_apps(rids)):
        return "Referral"
    return person_recorded(rids)


for code, title, fn in [("P0", "As recorded (duplicate pair -> source of the hired row, else the earlier row)", person_recorded),
                        ("P1", "Referral evidence (any Source=Referral row or any Referred By link)", person_evidence)]:
    ppl, hired = Counter(), Counter()
    for rids in people.values():
        g = fn(rids)
        ppl[g] += 1
        hired[g] += any(is_hire(a) for a in person_apps(rids))
    n, h = sum(ppl.values()), sum(hired.values())
    assert n == len(people)
    print(f"\n{code}  {title}   [people={n}, people hired={h}]")
    print(f"  {'group':<10}{'people':>7}{'% people':>10}{'hired':>7}{'% of hired':>12}   hired per person (95% CI)")
    res = {"people": n, "hired": h, "groups": {}}
    for g in GROUPS:
        lo, hi = wilson(hired[g], ppl[g])
        print(f"  {g:<10}{ppl[g]:>7}{100*ppl[g]/n:>9.1f}%{hired[g]:>7}{100*hired[g]/h:>11.1f}%   "
              f"{hired[g]}/{ppl[g]} = {100*hired[g]/ppl[g]:.1f}%  ({100*lo:.1f}-{100*hi:.1f}%)")
        res["groups"][g] = {"people": ppl[g], "hired": hired[g]}
    out["people"][code] = res

conflict = [rids for rids in people.values() if len({group3(CAND[c]["Source"]) for c in rids}) > 1]
print(f"\n  People whose duplicate rows disagree on Source: {len(conflict)}")
for rids in conflict:
    print("    " + " | ".join(f"{CAND[c]['Candidate ID']} {CAND[c]['Full Name']} {CAND[c]['Source']} "
                             f"hired={any(is_hire(a) for a in CAND[c].get('Applications', []))}" for c in rids))
repeat = {k: [a for a in person_apps(v) if is_hire(a)] for k, v in people.items()}
repeat = {k: v for k, v in repeat.items() if len(v) > 1}
print(f"  People with more than one Hired application (rule H): {len(repeat)} "
      f"-> {sum(len(v) for v in repeat.values())} hire rows for {len(repeat)} people")
for k, v in repeat.items():
    print("    " + k[0].title() + ": " + ", ".join(
        f"{APP[a]['Application ID']} {OPEN[one(APP[a],'Opening')]['Req ID']} hired {APP[a]['Closed On']}" for a in v))

print("\n" + "=" * 96)
print("PART 3 - WHERE REFERRAL IS NOT IDENTIFIED PROPERLY (all 350 application rows)")
print("=" * 96)
cells = Counter()
cell_hires = Counter()
cell_cands = defaultdict(set)
for r, f in APP.items():
    key = (recorded(r) == "Referral", bool(f.get("Referred By")))
    cells[key] += 1
    cell_hires[key] += is_hire(r)
    cell_cands[key].add(one(f, "Candidate"))
assert sum(cells.values()) == 350 and sum(cell_hires.values()) == 26
names = {(True, True): "A. Source=Referral AND Referred By link   (consistent referral)",
         (True, False): "B. Source=Referral, NO Referred By link    (referrer missing)",
         (False, True): "C. Referred By link, Source NOT Referral   (source mislabelled)",
         (False, False): "D. Neither                                 (consistent non-referral)"}
print(f"  {'cell':<68}{'apps':>5}{'cands':>7}{'hires':>7}")
for key in [(True, True), (True, False), (False, True), (False, False)]:
    print(f"  {names[key]:<68}{cells[key]:>5}{len(cell_cands[key]):>7}{cell_hires[key]:>7}")
    out["misidentified"][names[key][:1]] = {"apps": cells[key], "candidates": len(cell_cands[key]), "hires": cell_hires[key]}
bad_a = cells[(True, False)] + cells[(False, True)]
bad_h = cell_hires[(True, False)] + cell_hires[(False, True)]
any_ref = bad_a + cells[(True, True)]
print(f"\n  Applications with any referral signal: {any_ref}/350. Of those, inconsistent (B + C): "
      f"{bad_a}/{any_ref} = {100*bad_a/any_ref:.1f}%")
print(f"  Hires with any referral signal: {bad_h + cell_hires[(True, True)]}/26. Of those, inconsistent: "
      f"{bad_h}/{bad_h + cell_hires[(True, True)]}")
print(f"  Inconsistent referral rows as a share of everything: {bad_a}/350 applications = {100*bad_a/350:.1f}%, "
      f"{bad_h}/26 hires = {100*bad_h/26:.1f}%")
print("\n  Cell C by recorded Source:", dict(Counter(
    CAND[one(f, "Candidate")]["Source"] for r, f in APP.items() if f.get("Referred By") and recorded(r) != "Referral")))
print("  Cell C hires:", [(APP[r]["Application ID"], CAND[one(APP[r], "Candidate")]["Source"])
                          for r, f in APP.items() if f.get("Referred By") and recorded(r) != "Referral" and is_hire(r)])
print("  Cell B candidates:", sorted({CAND[c]["Candidate ID"] for c in cell_cands[(True, False)]}))
print("  Cell A candidates:", sorted({CAND[c]["Candidate ID"] for c in cell_cands[(True, True)]}))

print("\n  Third signal - Candidates.Notes = 'Referred internally...'")
note = [c for c, f in CAND.items() if "Referred internally" in f.get("Notes", "")]
linked = sum(any(APP[a].get("Referred By") for a in CAND[c].get("Applications", [])) for c in note)
src_ref = sum(CAND[c]["Source"] == "Referral" for c in note)
print(f"    candidates with that note: {len(note)}/300; of them Source=Referral: {src_ref}; with a Referred By link: {linked}")
two = [c for c, f in CAND.items() if "Applied to two openings" in f.get("Notes", "")]
print(f"    reliability test of Notes: 'Applied to two openings' note on {len(two)} candidates, "
      f"of whom {sum(len(CAND[c]['Applications']) > 1 for c in two)} actually have more than one application")

(ROOT / "output" / "source_scenarios.json").write_text(json.dumps(out, indent=1))
