"""Systematic data-quality audit of the cached Acme base.

Every check prints: affected rows / rows examined, plus example business IDs.
Checks are grouped: A uniqueness, B referential integrity, C completeness,
D validity, E time order, F cross-table agreement, G junk records.

Usage: python3 scripts/audit.py
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def load(table):
    recs = json.loads((RAW / f"{table.replace(' ', '_')}.json").read_text())
    return {r["id"]: r["fields"] for r in recs}


DEPT, PEOPLE, OPEN, CAND, APP, INT, OFF = (load(t) for t in (
    "Departments", "People", "Job Openings", "Candidates", "Applications", "Interviews", "Offers"))
PULLED = json.loads((RAW / "_manifest.json").read_text())["pulled_at"][:10]

results = []


def check(code, name, bad, total, label=lambda x: x, show=6):
    bad = list(bad)
    results.append((code, name, len(bad), total))
    flag = "OK  " if not bad else "FAIL"
    print(f"[{flag}] {code} {name}: {len(bad)}/{total}")
    if bad:
        print("         e.g. " + "; ".join(str(label(b)) for b in bad[:show]))


def one(fields, key):
    v = fields.get(key) or []
    return v[0] if v else None


def app_id(rid):
    return APP[rid].get("Application ID", rid)


def cand_of(app_rid):
    return CAND.get(one(APP[app_rid], "Candidate"), {})


# ---------------------------------------------------------------- A uniqueness
print("\n--- A. Uniqueness ---")
for code, table, data, key in [
    ("A1", "Departments", DEPT, "Code"), ("A2", "People", PEOPLE, "Work Email"),
    ("A3", "Job Openings", OPEN, "Req ID"), ("A4", "Candidates", CAND, "Candidate ID"),
    ("A5", "Applications", APP, "Application ID"), ("A6", "Interviews", INT, "Interview ID"),
    ("A7", "Offers", OFF, "Offer ID"),
]:
    counts = Counter(f.get(key) for f in data.values())
    dup_rows = [rid for rid, f in data.items() if counts[f.get(key)] > 1]
    check(code, f"{table}: rows sharing a {key}", dup_rows, len(data),
          label=lambda rid, d=data, k=key: d[rid].get(k))

dup_app_ids = sorted(k for k, n in Counter(f["Application ID"] for f in APP.values()).items() if n > 1)
for aid in dup_app_ids:
    rows = [(rid, f) for rid, f in APP.items() if f["Application ID"] == aid]
    print(f"         {aid}:")
    for rid, f in rows:
        print(f"           {rid} cand={CAND[one(f,'Candidate')]['Candidate ID']} "
              f"open={OPEN[one(f,'Opening')]['Req ID']} applied={f['Applied On']} stage={f['Stage']}")


def norm_phone(p):
    return re.sub(r"\D", "", p or "")


def norm_name(n):
    return re.sub(r"\s+", " ", (n or "").strip().lower())


for code, label_, keyfn in [
    ("A8", "Candidates sharing a phone number", lambda f: norm_phone(f.get("Phone"))),
    ("A9", "Candidates sharing a full name", lambda f: norm_name(f.get("Full Name"))),
    ("A10", "Candidates sharing an email (case-insensitive)", lambda f: (f.get("Email") or "").lower()),
]:
    counts = Counter(keyfn(f) for f in CAND.values())
    dup = [rid for rid, f in CAND.items() if counts[keyfn(f)] > 1]
    check(code, label_, dup, len(CAND), label=lambda rid: CAND[rid]["Candidate ID"], show=12)

groups = defaultdict(list)
for rid, f in CAND.items():
    groups[(norm_name(f.get("Full Name")), norm_phone(f.get("Phone")))].append(rid)
dup_groups = [g for g in groups.values() if len(g) > 1]
check("A11", "Candidate rows in a same-name-and-phone group (likely one person)",
      [r for g in dup_groups for r in g], len(CAND), label=lambda rid: CAND[rid]["Candidate ID"], show=12)
for g in dup_groups:
    print("         " + " | ".join(
        f"{CAND[r]['Candidate ID']} {CAND[r]['Full Name']} {CAND[r]['Email']} src={CAND[r]['Source']} "
        f"apps={[app_id(a)+':'+APP[a]['Stage'] for a in CAND[r].get('Applications', [])]}" for r in g))

pair = Counter((one(f, "Candidate"), one(f, "Opening")) for f in APP.values())
check("A12", "Applications where the same candidate applied to the same opening more than once",
      [rid for rid, f in APP.items() if pair[(one(f, "Candidate"), one(f, "Opening"))] > 1],
      len(APP), label=app_id)

# ------------------------------------------------------ B referential integrity
print("\n--- B. Referential integrity ---")
LINKS = [
    ("Applications", APP, "Candidate", CAND, True), ("Applications", APP, "Opening", OPEN, True),
    ("Applications", APP, "Recruiter", PEOPLE, True), ("Applications", APP, "Referred By", PEOPLE, False),
    ("Interviews", INT, "Application", APP, True), ("Interviews", INT, "Interviewer", PEOPLE, True),
    ("Offers", OFF, "Application", APP, True), ("Job Openings", OPEN, "Department", DEPT, True),
    ("Job Openings", OPEN, "Hiring Manager", PEOPLE, True), ("Job Openings", OPEN, "Recruiter", PEOPLE, True),
    ("People", PEOPLE, "Department", DEPT, True),
]
for i, (tname, data, key, target, required) in enumerate(LINKS, 1):
    broken = [rid for rid, f in data.items() if any(x not in target for x in f.get(key, []))]
    missing = [rid for rid, f in data.items() if required and not f.get(key)]
    multi = [rid for rid, f in data.items() if len(f.get(key, [])) > 1]
    check(f"B{i}", f"{tname}.{key}: broken / missing / multi-valued link",
          broken + missing + multi, len(data))

check("B12", "Applications whose Recruiter differs from the opening's Recruiter",
      [rid for rid, f in APP.items() if one(f, "Recruiter") != one(OPEN[one(f, "Opening")], "Recruiter")],
      len(APP), label=app_id)
for code, tname, data, key, role in [
    ("B13", "Applications", APP, "Recruiter", "Recruiter"),
    ("B14", "Interviews", INT, "Interviewer", "Interviewer"),
    ("B15", "Job Openings", OPEN, "Hiring Manager", "Hiring Manager"),
]:
    check(code, f"{tname}.{key} points at a person whose Role is not {role}",
          [rid for rid, f in data.items() if f.get(key) and PEOPLE[one(f, key)]["Role"] != role], len(data))
check("B16", "Applications with more than one Offer", [r for r, f in APP.items() if len(f.get("Offers", [])) > 1],
      len(APP), label=app_id)

# --------------------------------------------------------------- C completeness
print("\n--- C. Completeness (conditional fields) ---")
check("C1", "Stage=Rejected with no Rejection Reason",
      [r for r, f in APP.items() if f["Stage"] == "Rejected" and not f.get("Rejection Reason")], 200, label=app_id)
rr_other = [r for r, f in APP.items() if f.get("Rejection Reason") and f["Stage"] != "Rejected"]
check("C2", "Rejection Reason filled on a non-Rejected application", rr_other, len(APP),
      label=lambda r: f"{app_id(r)}:{APP[r]['Stage']}:{APP[r]['Rejection Reason']}", show=20)
print("         by stage/reason:", dict(Counter((APP[r]["Stage"], APP[r]["Rejection Reason"]) for r in rr_other)))
check("C3", "Status=Closed without Closed On, or Closed On with Status=Active",
      [r for r, f in APP.items() if (f["Status"] == "Closed") != bool(f.get("Closed On"))], len(APP), label=app_id)
print("         Stage x Status:", dict(sorted(Counter((f["Stage"], f["Status"]) for f in APP.values()).items())))
check("C4", "Application has Interviews linked but no First Interview On (or the reverse)",
      [r for r, f in APP.items() if bool(f.get("Interviews")) != bool(f.get("First Interview On"))], len(APP), label=app_id)
check("C5", "Application has Offered On but no Offer record (or the reverse)",
      [r for r, f in APP.items() if bool(f.get("Offers")) != bool(f.get("Offered On"))], len(APP), label=app_id)
check("C6", "Stage in Interview/Offer/Hired but no Screened On",
      [r for r, f in APP.items() if f["Stage"] in ("Interview", "Offer", "Hired") and not f.get("Screened On")],
      sum(f["Stage"] in ("Interview", "Offer", "Hired") for f in APP.values()), label=app_id)
check("C7", "Stage in Offer/Hired but no interview on record",
      [r for r, f in APP.items() if f["Stage"] in ("Offer", "Hired") and not f.get("Interviews")],
      sum(f["Stage"] in ("Offer", "Hired") for f in APP.values()), label=app_id)
check("C8", "Stage=Applied but has Screened On / interviews / offer",
      [r for r, f in APP.items() if f["Stage"] == "Applied"
       and (f.get("Screened On") or f.get("Interviews") or f.get("Offers"))], 45, label=app_id)
check("C9", "Offer decided (Accepted/Declined) with no Decision On",
      [r for r, f in OFF.items() if f["Status"] != "Pending" and not f.get("Decision On")], len(OFF),
      label=lambda r: OFF[r]["Offer ID"])
check("C10", "Offer Pending but has a Decision On date",
      [r for r, f in OFF.items() if f["Status"] == "Pending" and f.get("Decision On")], len(OFF),
      label=lambda r: f"{OFF[r]['Offer ID']} offered={OFF[r]['Offered On']} decision={OFF[r].get('Decision On')}")
check("C11", "Decline Reason does not match Status=Declined",
      [r for r, f in OFF.items() if (f["Status"] == "Declined") != bool(f.get("Decline Reason"))], len(OFF),
      label=lambda r: OFF[r]["Offer ID"])
check("C12", "Interview Outcome=Completed missing Completed On/Score/Recommendation",
      [r for r, f in INT.items() if f["Outcome"] == "Completed"
       and not (f.get("Completed On") and f.get("Score") is not None and f.get("Recommendation"))], 138,
      label=lambda r: INT[r]["Interview ID"])
check("C13", "Interview not Completed (No Show/Cancelled/Rescheduled) but has Score/Recommendation/Completed On",
      [r for r, f in INT.items() if f["Outcome"] != "Completed"
       and (f.get("Completed On") or f.get("Score") is not None or f.get("Recommendation"))], 22,
      label=lambda r: f"{INT[r]['Interview ID']}:{INT[r]['Outcome']}:{INT[r].get('Recommendation')}")

# ------------------------------------------------------------------ D validity
print("\n--- D. Validity ---")
check("D1", "Interview Score outside 1-5", [r for r, f in INT.items() if f.get("Score") is not None
      and not 1 <= f["Score"] <= 5], 142)
check("D2", "Opening Salary Band Min >= Max", [r for r, f in OPEN.items()
      if f["Salary Band Min"] >= f["Salary Band Max"]], len(OPEN))
check("D3", "Candidate Expected CTC below Current CTC",
      [r for r, f in CAND.items() if f["Expected CTC"] < f["Current CTC"]], len(CAND),
      label=lambda r: f"{CAND[r]['Candidate ID']} cur={CAND[r]['Current CTC']} exp={CAND[r]['Expected CTC']}")
check("D4", "Candidate Expected CTC more than 2x Current CTC",
      [r for r, f in CAND.items() if f["Expected CTC"] > 2 * f["Current CTC"]], len(CAND),
      label=lambda r: f"{CAND[r]['Candidate ID']} cur={CAND[r]['Current CTC']} exp={CAND[r]['Expected CTC']}")


def band(off):
    o = OPEN[one(APP[one(off, "Application")], "Opening")]
    return o["Salary Band Min"], o["Salary Band Max"]


check("D5", "Offer Base CTC outside the opening's salary band",
      [r for r, f in OFF.items() if not band(f)[0] <= f["Base CTC"] <= band(f)[1]], len(OFF),
      label=lambda r: f"{OFF[r]['Offer ID']} {OFF[r]['Status']} base={OFF[r]['Base CTC']} band={band(OFF[r])}", show=40)
check("D6", "Offer Base CTC below the candidate's Current CTC",
      [r for r, f in OFF.items() if f["Base CTC"] < cand_of(one(f, "Application"))["Current CTC"]], len(OFF),
      label=lambda r: f"{OFF[r]['Offer ID']} {OFF[r]['Status']}")
check("D7", "Candidate Years Experience negative or above 45",
      [r for r, f in CAND.items() if not 0 <= f["Years Experience"] <= 45], len(CAND))
phones = Counter(len(norm_phone(f["Phone"])) for f in CAND.values())
print("         phone digit-lengths:", dict(phones))
check("D8", "Candidate email not a plausible address",
      [r for r, f in CAND.items() if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]+", f["Email"])], len(CAND))

# ---------------------------------------------------------------- E time order
print("\n--- E. Time order (ISO dates compare as strings) ---")
SEQ = ["Applied On", "Screened On", "First Interview On", "Final Interview On", "Offered On", "Closed On"]


def out_of_order(f):
    present = [(k, f[k]) for k in SEQ if f.get(k)]
    return [(a, b) for (a, av), (b, bv) in zip(present, present[1:]) if av > bv]


ooo = [r for r, f in APP.items() if out_of_order(f)]
check("E1", "Application milestone dates out of order", ooo, len(APP),
      label=lambda r: f"{app_id(r)}:{APP[r]['Stage']}:{out_of_order(APP[r])}", show=8)
print("         which pair:", dict(Counter(p for r in ooo for p in out_of_order(APP[r]))))
print("         by stage:", dict(Counter(APP[r]["Stage"] for r in ooo)))
check("E2", "Applied On earlier than the opening's Opened On",
      [r for r, f in APP.items() if f["Applied On"] < OPEN[one(f, "Opening")]["Opened On"]], len(APP),
      label=lambda r: f"{app_id(r)} applied={APP[r]['Applied On']} opened={OPEN[one(APP[r],'Opening')]['Opened On']}")
check("E3", "Candidate Created On later than their first Applied On",
      [r for r, f in CAND.items() if f.get("Applications")
       and f["Created On"] > min(APP[a]["Applied On"] for a in f["Applications"])], len(CAND),
      label=lambda r: CAND[r]["Candidate ID"])
check("E4", "Interview Completed On earlier than Scheduled On",
      [r for r, f in INT.items() if f.get("Completed On") and f["Completed On"] < f["Scheduled On"]], 142,
      label=lambda r: INT[r]["Interview ID"])
check("E5", "Interview scheduled before the application's Applied On",
      [r for r, f in INT.items() if f["Scheduled On"] < APP[one(f, "Application")]["Applied On"]], len(INT),
      label=lambda r: INT[r]["Interview ID"])
check("E6", "Application First Interview On differs from earliest linked interview date",
      [r for r, f in APP.items() if f.get("Interviews")
       and f.get("First Interview On") != min(INT[i]["Scheduled On"] for i in f["Interviews"])], 143, label=app_id)
check("E7", "Offer.Offered On differs from Application.Offered On",
      [r for r, f in OFF.items() if f["Offered On"] != APP[one(f, "Application")].get("Offered On")], len(OFF),
      label=lambda r: OFF[r]["Offer ID"])
check("E8", "Offer Decision On earlier than Offered On",
      [r for r, f in OFF.items() if f.get("Decision On") and f["Decision On"] < f["Offered On"]], len(OFF),
      label=lambda r: f"{OFF[r]['Offer ID']} {OFF[r]['Status']} offered={OFF[r]['Offered On']} decision={OFF[r]['Decision On']}")
check("E9", "Offer Proposed Start Date earlier than Offered On",
      [r for r, f in OFF.items() if f["Proposed Start Date"] < f["Offered On"]], len(OFF),
      label=lambda r: OFF[r]["Offer ID"])
future = []
for tname, data in [("App", APP), ("Int", INT), ("Off", OFF), ("Cand", CAND), ("Open", OPEN)]:
    for rid, f in data.items():
        for k, v in f.items():
            if isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", v) and v > PULLED \
                    and k not in ("Proposed Start Date", "Target Close"):
                future.append(f"{tname}.{k}={v}")
check("E10", f"Event dates after the pull date ({PULLED})", future, "all date fields")
check("E11", "Interviewer interviewed before their own Joined On",
      [r for r, f in INT.items() if f["Scheduled On"] < PEOPLE[one(f, "Interviewer")]["Joined On"]], len(INT),
      label=lambda r: INT[r]["Interview ID"])
pend = [f for f in OFF.values() if f["Status"] == "Pending"]
print("         pending offers, days open at pull date:",
      sorted((f["Offer ID"], f["Offered On"]) for f in pend))

# ------------------------------------------------------ F cross-table agreement
print("\n--- F. Cross-table agreement ---")
offer_status = {one(f, "Application"): f["Status"] for f in OFF.values()}
print("         Application Stage x Offer Status:",
      dict(sorted(Counter((APP[a]["Stage"], APP[a]["Status"], s) for a, s in offer_status.items()).items())))
check("F1", "Stage=Hired without an Accepted offer",
      [r for r, f in APP.items() if f["Stage"] == "Hired" and offer_status.get(r) != "Accepted"], 26, label=app_id)
check("F2", "Accepted offer but application Stage is not Hired",
      [a for a, s in offer_status.items() if s == "Accepted" and APP[a]["Stage"] != "Hired"], 26,
      label=lambda a: f"{app_id(a)}:{APP[a]['Stage']}")
check("F3", "Stage=Offer without a Pending offer",
      [r for r, f in APP.items() if f["Stage"] == "Offer" and offer_status.get(r) != "Pending"], 10,
      label=lambda r: f"{app_id(r)}:{APP[r]['Status']}:{offer_status.get(r)}", show=10)
hires = Counter(one(f, "Opening") for f in APP.values() if f["Stage"] == "Hired")
check("F4", "Openings with more hires than Headcount",
      [r for r, f in OPEN.items() if hires[r] > f["Headcount"]], len(OPEN),
      label=lambda r: f"{OPEN[r]['Req ID']} hires={hires[r]} headcount={OPEN[r]['Headcount']}")
check("F5", "Openings marked Filled with fewer hires than Headcount",
      [r for r, f in OPEN.items() if f["Status"] == "Filled" and hires[r] < f["Headcount"]], 8,
      label=lambda r: f"{OPEN[r]['Req ID']} hires={hires[r]} headcount={OPEN[r]['Headcount']}", show=10)
check("F6", "Openings not marked Filled although hires >= Headcount",
      [r for r, f in OPEN.items() if f["Status"] != "Filled" and hires[r] >= f["Headcount"]], 16,
      label=lambda r: f"{OPEN[r]['Req ID']} {OPEN[r]['Status']} hires={hires[r]} headcount={OPEN[r]['Headcount']}")
print("         hires by opening status:", dict(Counter(OPEN[o]["Status"] for o in hires.elements())))
check("F7", "Active applications on openings that are Filled/Cancelled/On Hold",
      [r for r, f in APP.items() if f["Status"] == "Active" and OPEN[one(f, "Opening")]["Status"] != "Open"], 105,
      label=lambda r: f"{app_id(r)}:{OPEN[one(APP[r],'Opening')]['Status']}")
print("         active apps by opening status:",
      dict(Counter(OPEN[one(f, "Opening")]["Status"] for f in APP.values() if f["Status"] == "Active")))
check("F8", "Rejection Reason=Position Cancelled but the opening is not Cancelled",
      [r for r, f in APP.items() if f.get("Rejection Reason") == "Position Cancelled"
       and OPEN[one(f, "Opening")]["Status"] != "Cancelled"], 18,
      label=lambda r: f"{app_id(r)}:{OPEN[one(APP[r],'Opening')]['Status']}")
check("F9", "Offers (any status) on openings that are Cancelled/On Hold",
      [r for r, f in OFF.items() if OPEN[one(APP[one(f, 'Application')], 'Opening')]["Status"] in ("Cancelled", "On Hold")],
      len(OFF), label=lambda r: f"{OFF[r]['Offer ID']}:{OFF[r]['Status']}")

print("   -- Source vs referral evidence --")
ref_apps = [r for r, f in APP.items() if f.get("Referred By")]
check("F10", "Applications with Referred By whose candidate Source is not Referral",
      [r for r in ref_apps if cand_of(r)["Source"] != "Referral"], len(ref_apps),
      label=lambda r: f"{app_id(r)}:{cand_of(r)['Source']}:{APP[r]['Stage']}", show=30)
print("         Source of candidates on Referred-By applications:",
      dict(Counter(cand_of(r)["Source"] for r in ref_apps)))
check("F11", "Candidates with Source=Referral but no application has Referred By",
      [r for r, f in CAND.items() if f["Source"] == "Referral"
       and not any(APP[a].get("Referred By") for a in f.get("Applications", []))], 8,
      label=lambda r: CAND[r]["Candidate ID"])
note_ref = [r for r, f in CAND.items() if "Referred internally" in f.get("Notes", "")]
print("         Candidates whose Notes say 'Referred internally':", len(note_ref),
      "by Source:", dict(Counter(CAND[r]["Source"] for r in note_ref)),
      "| with a Referred By link:", sum(any(APP[a].get("Referred By") for a in CAND[r].get("Applications", [])) for r in note_ref))
note_conf = [r for r, f in CAND.items() if "conference" in f.get("Notes", "")]
print("         Notes 'Sourced from a conference list' by Source:", dict(Counter(CAND[r]["Source"] for r in note_conf)))
print("         Notes text looks randomly assigned if spread evenly over Source - compare with overall Source mix:",
      dict(Counter(f["Source"] for f in CAND.values())))

print("   -- Interview signal vs outcome --")
POSITIVE = {
    "Solid fundamentals. Needed a hint on the follow-up but recovered well.",
    "Reasonable answers throughout. No red flags.",
    "Good practical experience. Some gaps in scale but coachable.",
    "Excellent depth on system design. Explained trade-offs without prompting.",
    "Clear communicator, solved the problem two ways and compared them.",
    "Strongest candidate in this loop. Would hire on the spot.",
}
scored = [r for r, f in INT.items() if f.get("Recommendation")]
check("F12", "Interview feedback text contradicts the Recommendation",
      [r for r in scored if (INT[r]["Feedback"] in POSITIVE) != (INT[r]["Recommendation"] in ("Hire", "Strong Hire"))],
      len(scored), label=lambda r: f"{INT[r]['Interview ID']}:{INT[r]['Recommendation']}:{INT[r]['Score']}")
check("F13", "Recommendation contradicts Score (Hire/Strong Hire with score <3, or No Hire with score >=4)",
      [r for r in scored if (INT[r]["Recommendation"] in ("Hire", "Strong Hire") and INT[r]["Score"] < 3)
       or (INT[r]["Recommendation"] in ("No Hire", "Strong No Hire") and INT[r]["Score"] >= 4)],
      len(scored), label=lambda r: f"{INT[r]['Interview ID']}:{INT[r]['Recommendation']}:{INT[r]['Score']}")
score_by_rec = defaultdict(list)
for r in scored:
    score_by_rec[INT[r]["Recommendation"]].append(INT[r]["Score"])
print("         score range by recommendation:",
      {k: (min(v), max(v), len(v)) for k, v in score_by_rec.items()})
def recorded_recs(f):
    # A missing recommendation (no-show, cancelled, not filled in) is not a "no".
    return [INT[i]["Recommendation"] for i in f.get("Interviews", []) if INT[i].get("Recommendation")]


offered_apps = [r for r, f in APP.items() if f["Stage"] in ("Offer", "Hired")]
all_no = [r for r in offered_apps if recorded_recs(APP[r])
          and all(x in ("No Hire", "Strong No Hire") for x in recorded_recs(APP[r]))]
check("F14", "Offer/Hired applications where every recorded interview recommendation was No Hire / Strong No Hire",
      all_no, len(offered_apps), label=app_id, show=8)
print("         recorded recommendations behind each of those:",
      dict(Counter(len(recorded_recs(APP[r])) for r in all_no)),
      "| offered applications with no recorded recommendation at all:",
      sum(not recorded_recs(APP[r]) for r in offered_apps))

# ----------------------------------------------------------------------- G junk
print("\n--- G. Junk / test records ---")
junk = re.compile(r"\b(test|dummy|sample|fake|asdf|xxx|demo)\b", re.I)
check("G1", "Candidates whose name or email looks like a test record",
      [r for r, f in CAND.items() if junk.search(f["Full Name"]) or junk.search(f["Email"].split("@")[0])],
      len(CAND), label=lambda r: f"{CAND[r]['Candidate ID']} {CAND[r]['Full Name']} {CAND[r]['Email']}")
check("G2", "Openings whose title looks like a test record",
      [r for r, f in OPEN.items() if junk.search(f["Title"])], len(OPEN), label=lambda r: OPEN[r]["Title"])
print("         email domains:", dict(Counter(f["Email"].split("@")[1] for f in CAND.values())))
check("G3", "Candidates with no application", [r for r, f in CAND.items() if not f.get("Applications")], len(CAND))

print("\n=== SUMMARY: failed checks ===")
for code, name, n, total in results:
    if n:
        print(f"  {code:<4} {n:>4}/{total:<5} {name}")
print(f"  checks run: {len(results)}, failed: {sum(1 for r in results if r[2])}")
