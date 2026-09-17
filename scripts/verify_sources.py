#!/usr/bin/env python3
"""Independent verification of source-of-hire numbers. Standard library only."""
import json
import re
from collections import Counter, defaultdict

D = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "data", "raw") + "/"


def load(n):
    with open(D + n + '.json') as f:
        return json.load(f)


C = load('Candidates')
A = load('Applications')
O = load('Job_Openings')
cand = {c['id']: c['fields'] for c in C}
opening = {o['id']: o['fields'] for o in O}
GROUPS = ['Job Board', 'Referral', 'Other']


def grp(source):
    return source if source in ('Job Board', 'Referral') else 'Other'


def person_key(cf):
    name = ' '.join((cf.get('Full Name') or '').lower().split())
    phone = re.sub(r'\D', '', cf.get('Phone') or '')
    return (name, phone)


# ---- flatten applications
apps = []
for a in A:
    f = a['fields']
    cl, ol = f.get('Candidate', []), f.get('Opening', [])
    assert len(cl) == 1 and len(ol) == 1, a['id']
    cf = cand[cl[0]]
    of = opening[ol[0]]
    rec = grp(cf.get('Source'))
    hasref = bool(f.get('Referred By'))
    apps.append(dict(
        rid=a['id'], appid=f.get('Application ID'), cid=cl[0], candid=cf.get('Candidate ID'),
        oid=ol[0], req=of.get('Req ID'), ostatus=of.get('Status'), stage=f.get('Stage'),
        applied=f.get('Applied On') or '', closed=f.get('Closed On'), source=cf.get('Source'),
        rec=rec, hasref=hasref, ev='Referral' if hasref else rec,
        hired=f.get('Stage') == 'Hired', person=person_key(cf), status=f.get('Status')))
for x in apps:
    x['strict'] = x['hired'] and x['ostatus'] != 'Cancelled'


def table(label, rows, gkey, hkey='hired'):
    print(label)
    tr = th = 0
    for g in GROUPS:
        r = [x for x in rows if x[gkey] == g]
        h = sum(1 for x in r if x[hkey])
        tr += len(r)
        th += h
        print('  %-10s rows=%4d hires=%3d' % (g, len(r), h))
    print('  %-10s rows=%4d hires=%3d' % ('TOTAL', tr, th))
    return tr, th


print('=== INPUT ===')
print('candidates=%d applications=%d openings=%d' % (len(C), len(A), len(O)))
print('hired rows=%d' % sum(x['hired'] for x in apps))
print('opening status:', dict(Counter(o['fields'].get('Status') for o in O)))
print('candidate Source:', dict(Counter(c['fields'].get('Source') for c in C)))

# ---- Rule D
bygrp = defaultdict(list)
for x in apps:
    bygrp[(x['person'], x['oid'])].append(x)
dropped, kept_ids = [], set()
ruleD_notes = []
for k, rows in bygrp.items():
    if len(rows) == 1:
        kept_ids.add(rows[0]['rid'])
        continue
    hired = [r for r in rows if r['hired']]
    if hired:
        if len(hired) > 1:
            ruleD_notes.append('MULTI-HIRED in group %s: %s' % (k, [r['appid'] for r in hired]))
        pool = hired
    else:
        pool = rows
    mx = max(r['applied'] for r in pool)
    top = [r for r in pool if r['applied'] == mx]
    if len(top) > 1:
        ruleD_notes.append('TIE on Applied On in group %s: %s' % (k, [(r['appid'], r['rid']) for r in top]))
    keep = sorted(top, key=lambda r: (r['appid'], r['rid']))[-1]
    kept_ids.add(keep['rid'])
    for r in rows:
        if r['rid'] != keep['rid']:
            dropped.append((r, keep))
surv = [x for x in apps if x['rid'] in kept_ids]

print()
print('=== SCENARIOS ===')
tot = {}
tot['S0'] = table('S0 all rows, recorded group', apps, 'rec')
tot['S1'] = table('S1 all rows, evidence group', apps, 'ev')
tot['S2'] = table('S2 Rule D survivors, recorded group', surv, 'rec')
tot['S3'] = table('S3 Rule D survivors, evidence group', surv, 'ev')
tot['S4'] = table('S4 Rule D survivors, evidence group, STRICT hires', surv, 'ev', 'strict')

print()
print('=== RULE D ===')
multi = [r for r in bygrp.values() if len(r) > 1]
print('(person,opening) groups=%d, groups with >1 row=%d, rows in those groups=%d, dropped=%d, survivors=%d' % (
    len(bygrp), len(multi), sum(len(r) for r in multi), len(dropped), len(surv)))
print('sizes of multi-row groups:', dict(Counter(len(r) for r in multi)))
print('multi-row groups spanning >1 candidate record: %d; within a single candidate record: %d' % (
    sum(1 for r in multi if len({x['cid'] for x in r}) > 1), sum(1 for r in multi if len({x['cid'] for x in r}) == 1)))
for n in ruleD_notes:
    print('  NOTE', n)
print('dropped rows (rid | AppID | cand | req | stage | applied | rec/ev || kept AppID rid stage applied):')
for r, k in sorted(dropped, key=lambda t: (t[0]['appid'], t[0]['rid'])):
    print('  %s | %s | %s | %s | %s | %s | %s/%s || %s %s %s %s' % (
        r['rid'], r['appid'], r['candid'], r['req'], r['stage'], r['applied'], r['rec'], r['ev'],
        k['appid'], k['rid'], k['stage'], k['applied']))
print('dropped by stage:', dict(Counter(r['stage'] for r, _ in dropped)))
print('dropped by recorded group:', dict(Counter(r['rec'] for r, _ in dropped)))
print('dropped by evidence group:', dict(Counter(r['ev'] for r, _ in dropped)))
print('dropped rows that are hires: %d' % sum(r['hired'] for r, _ in dropped))

print()
print('=== HIRES ON CANCELLED OPENINGS ===')
hc = [x for x in apps if x['hired'] and x['ostatus'] == 'Cancelled']
print('count=%d' % len(hc))
for x in sorted(hc, key=lambda x: x['appid']):
    print('  %s | %s | %s | %s | rec=%s ev=%s | survives Rule D=%s' % (
        x['appid'], x['rid'], x['req'], x['candid'], x['rec'], x['ev'], x['rid'] in kept_ids))
print('hires by opening status:', dict(Counter(x['ostatus'] for x in apps if x['hired'])))

# ---- People level
print()
print('=== PEOPLE LEVEL ===')
people = defaultdict(list)
for c in C:
    people[person_key(c['fields'])].append(c)
apps_by_cid = defaultdict(list)
for x in apps:
    apps_by_cid[x['cid']].append(x)
print('distinct people=%d' % len(people))
print('people with >1 candidate row=%d (row-count dist: %s)' % (
    sum(1 for v in people.values() if len(v) > 1), dict(Counter(len(v) for v in people.values()))))

p0 = {}
p1 = {}
phired = {}
ambiguous = []
for k, rows in people.items():
    hired_rows = [c for c in rows if any(x['hired'] for x in apps_by_cid[c['id']])]
    pool = hired_rows if hired_rows else rows
    if len({grp(c['fields'].get('Source')) for c in hired_rows}) > 1:
        ambiguous.append(k)
    base = sorted(pool, key=lambda c: (c['fields'].get('Created On') or '', c['fields'].get('Candidate ID')))[0]
    p0[k] = grp(base['fields'].get('Source'))
    anyref = any(c['fields'].get('Source') == 'Referral' for c in rows) or any(
        x['hasref'] for c in rows for x in apps_by_cid[c['id']])
    p1[k] = 'Referral' if anyref else p0[k]
    phired[k] = bool(hired_rows)
print('people whose hired applications sit on candidate rows of different groups (P0 ambiguity)=%d' % len(ambiguous))
for label, m in (('P0', p0), ('P1', p1)):
    print(label)
    tp = th = 0
    for g in GROUPS:
        n = sum(1 for k in m if m[k] == g)
        h = sum(1 for k in m if m[k] == g and phired[k])
        tp += n
        th += h
        print('  %-10s people=%4d hired=%3d' % (g, n, h))
    print('  %-10s people=%4d hired=%3d' % ('TOTAL', tp, th))
print('people moved by P1 vs P0:', dict(Counter((p0[k], p1[k]) for k in p0 if p0[k] != p1[k])))
print('  of which hired:', dict(Counter((p0[k], p1[k]) for k in p0 if p0[k] != p1[k] and phired[k])))

print('people whose candidate rows disagree on three-way group:')
dis = [(k, rows) for k, rows in people.items() if len({grp(c['fields'].get('Source')) for c in rows}) > 1]
print('  count=%d' % len(dis))
for k, rows in sorted(dis, key=lambda t: t[1][0]['fields']['Candidate ID']):
    rows = sorted(rows, key=lambda c: c['fields'].get('Created On'))
    print('  %s: %s | hired=%s P0=%s P1=%s' % (k[0], ', '.join('%s[%s,%s]' % (
        c['fields']['Candidate ID'], c['fields'].get('Source'), c['fields'].get('Created On')) for c in rows),
        phired[k], p0[k], p1[k]))
disraw = [k for k, rows in people.items() if len({c['fields'].get('Source') for c in rows}) > 1]
print('  (people whose rows disagree on RAW Source value=%d)' % len(disraw))

print('people with >1 hired application:')
mh = []
for k, rows in people.items():
    hs = [x for c in rows for x in apps_by_cid[c['id']] if x['hired']]
    if len(hs) > 1:
        mh.append((k, hs))
print('  count=%d' % len(mh))
for k, hs in sorted(mh):
    print('  %s: %s' % (k[0], '; '.join('%s/%s/%s/%s/opening %s' % (
        x['appid'], x['rid'], x['req'], x['candid'], x['ostatus']) for x in hs)))
print('hired application rows=%d, hired people=%d' % (sum(x['hired'] for x in apps), sum(phired.values())))

# ---- Matrix
print()
print('=== REFERRAL CONSISTENCY MATRIX (all rows) ===')
cells = {}
for s in (True, False):
    for r in (True, False):
        rows = [x for x in apps if (x['source'] == 'Referral') == s and x['hasref'] == r]
        cells[(s, r)] = rows
        print('  SourceReferral=%-5s ReferredBy=%-5s rows=%4d distinct_candidates=%4d hires=%3d' % (
            s, r, len(rows), len({x['cid'] for x in rows}), sum(x['hired'] for x in rows)))
print('  cell sums: rows=%d hires=%d' % (sum(len(v) for v in cells.values()),
                                          sum(x['hired'] for v in cells.values() for x in v)))
print('  NOTE distinct candidates summed over cells=%d vs %d candidates with applications (a candidate can sit in 2 cells)' % (
    sum(len({x['cid'] for x in v}) for v in cells.values()), len({x['cid'] for x in apps})))
rb = cells[(False, True)]
print('Referred By present, Source not Referral: by original Source (rows / distinct cands / hires):')
for s in sorted({x['source'] for x in rb}):
    r = [x for x in rb if x['source'] == s]
    print('  %-12s rows=%3d cands=%3d hires=%3d' % (s, len(r), len({x['cid'] for x in r}), sum(x['hired'] for x in r)))
print('  hire Application IDs:', sorted((x['appid'], x['rid'], x['source']) for x in rb if x['hired']))
sn = cells[(True, False)]
print('Source Referral, no Referred By: Candidate IDs:', sorted({x['candid'] for x in sn}))
print('  rows:', sorted((x['candid'], x['appid'], x['stage']) for x in sn))
print('Source Referral AND Referred By rows:', sorted((x['candid'], x['appid'], x['stage']) for x in cells[(True, True)]))
refcands = [c for c in C if c['fields'].get('Source') == 'Referral']
print('Source=Referral candidates=%d; with >=1 Referred By app=%d; with none=%d' % (
    len(refcands), sum(1 for c in refcands if any(x['hasref'] for x in apps_by_cid[c['id']])),
    sum(1 for c in refcands if not any(x['hasref'] for x in apps_by_cid[c['id']]))))

# ---- Notes
print()
print('=== NOTES CHECK ===')
ri = [c for c in C if 'Referred internally' in (c['fields'].get('Notes') or '')]
print('Notes contain "Referred internally": %d' % len(ri))
print('  of those Source == Referral: %d' % sum(1 for c in ri if c['fields'].get('Source') == 'Referral'))
print('  of those with >=1 application with Referred By: %d' % sum(
    1 for c in ri if any(x['hasref'] for x in apps_by_cid[c['id']])))
print('  of those with Source Referral OR Referred By: %d' % sum(
    1 for c in ri if c['fields'].get('Source') == 'Referral' or any(x['hasref'] for x in apps_by_cid[c['id']])))
print('  Source breakdown:', dict(Counter(c['fields'].get('Source') for c in ri)))
print('  hires among their applications: %d' % sum(x['hired'] for c in ri for x in apps_by_cid[c['id']]))
print('  (rate of that note among all candidates by Source):', {
    s: '%d/%d' % (sum(1 for c in ri if c['fields'].get('Source') == s), n)
    for s, n in Counter(c['fields'].get('Source') for c in C).items()})
t2 = [c for c in C if 'Applied to two openings' in (c['fields'].get('Notes') or '')]
print('Notes contain "Applied to two openings": %d' % len(t2))
print('  of those with >1 linked application (Candidate.Applications link): %d' % sum(
    1 for c in t2 if len(c['fields'].get('Applications', [])) > 1))
print('  of those with >1 application (via Applications.Candidate): %d' % sum(
    1 for c in t2 if len(apps_by_cid[c['id']]) > 1))
print('  candidates overall with >1 application: %d' % sum(1 for c in C if len(apps_by_cid[c['id']]) > 1))

# ---- Sanity
print()
print('=== SANITY ===')
NA, NH = len(apps), sum(x['hired'] for x in apps)
print('S0 %s == (%d,%d): %s' % (tot['S0'], NA, NH, tot['S0'] == (NA, NH)))
print('S1 %s == (%d,%d): %s' % (tot['S1'], NA, NH, tot['S1'] == (NA, NH)))
ns, nsh = len(surv), sum(x['hired'] for x in surv)
print('S2 %s == (%d,%d): %s' % (tot['S2'], ns, nsh, tot['S2'] == (ns, nsh)))
print('S3 %s == (%d,%d): %s' % (tot['S3'], ns, nsh, tot['S3'] == (ns, nsh)))
nss = sum(x['strict'] for x in surv)
print('S4 %s == (%d,%d): %s' % (tot['S4'], ns, nss, tot['S4'] == (ns, nss)))
print('all rows %d - dropped %d = survivors %d: %s' % (NA, len(dropped), ns, NA - len(dropped) == ns))
print('survivor hires %d - cancelled-opening hires among survivors %d = strict %d: %s' % (
    nsh, sum(1 for x in hc if x['rid'] in kept_ids), nss,
    nsh - sum(1 for x in hc if x['rid'] in kept_ids) == nss))
print('matrix rows sum == %d: %s ; hires sum == %d: %s' % (
    NA, sum(len(v) for v in cells.values()) == NA, NH, sum(x['hired'] for v in cells.values() for x in v) == NH))
print('S1 Referral rows == rows with ReferredBy + SourceReferral-without: %d == %d' % (
    sum(1 for x in apps if x['ev'] == 'Referral'), len(cells[(True, True)]) + len(cells[(False, True)]) + len(cells[(True, False)])))

# ---- Critique checks
print()
print('=== CRITIQUE CHECKS ===')
# link symmetry
fwd = {(c['id'], a) for c in C for a in c['fields'].get('Applications', [])}
bwd = {(x['cid'], x['rid']) for x in apps}
print('Candidate<->Application link symmetric: %s (fwd=%d bwd=%d)' % (fwd == bwd, len(fwd), len(bwd)))
print('candidates with zero applications: %d' % sum(1 for c in C if not apps_by_cid[c['id']]))
# duplicate App IDs
dup = {k: v for k, v in Counter(x['appid'] for x in apps).items() if v > 1}
print('duplicate Application IDs: %s' % dup)
for k in sorted(dup):
    for x in apps:
        if x['appid'] == k:
            print('   %s %s cand=%s person=%s req=%s stage=%s applied=%s rec=%s ev=%s droppedByD=%s' % (
                k, x['rid'], x['candid'], x['person'][0], x['req'], x['stage'], x['applied'], x['rec'], x['ev'],
                x['rid'] not in kept_ids))
# exact duplicate application content
sig = Counter((x['cid'], x['oid'], x['stage'], x['applied'], x['closed']) for x in apps)
print('application rows identical on (candidate rec, opening, stage, applied, closed): %d extra rows' % sum(v - 1 for v in sig.values()))
sig2 = defaultdict(list)
for x in apps:
    sig2[(x['cid'], x['oid'])].append(x)
print('same candidate record + same opening, >1 row: %d groups' % sum(1 for v in sig2.values() if len(v) > 1))

# alternative person keys
def norm_name(cf):
    return ' '.join((cf.get('Full Name') or '').lower().split())


def alt(label, fn):
    g = defaultdict(list)
    for c in C:
        g[fn(c['fields'])].append(c)
    multi = {k: v for k, v in g.items() if len(v) > 1}
    # how many of these clusters are NOT already merged under the official key
    new = {k: v for k, v in multi.items() if len({person_key(c['fields']) for c in v}) > 1}
    print('%s: distinct=%d, keys with >1 row=%d, of which spanning >1 official person=%d' % (
        label, len(g), len(multi), len(new)))
    return new


n_email = alt('key=email lowercased', lambda f: (f.get('Email') or '').strip().lower())
n_phone = alt('key=phone digits only', lambda f: re.sub(r'\D', '', f.get('Phone') or ''))
n_phone10 = alt('key=last 10 phone digits', lambda f: re.sub(r'\D', '', f.get('Phone') or '')[-10:])
n_name = alt('key=normalized name only', norm_name)
n_nameci = alt('key=name letters only (strip punctuation/space)', lambda f: re.sub(r'[^a-z]', '', (f.get('Full Name') or '').lower()))
for label, new in (('email', n_email), ('phone', n_phone), ('phone10', n_phone10), ('name', n_name), ('name-letters', n_nameci)):
    for k, v in sorted(new.items())[:40]:
        print('   [%s] %s -> %s' % (label, k, [(c['fields']['Candidate ID'], c['fields']['Full Name'], c['fields']['Phone'],
                                                 c['fields'].get('Email'), c['fields'].get('Source'),
                                                 sum(x['hired'] for x in apps_by_cid[c['id']])) for c in v]))
# raw-name variants within official people
var = sum(1 for rows in people.values() if len({c['fields']['Full Name'] for c in rows}) > 1)
varp = sum(1 for rows in people.values() if len({c['fields']['Phone'] for c in rows}) > 1)
print('official people whose rows differ in raw Full Name string=%d; in raw Phone string=%d' % (var, varp))
exact = defaultdict(list)
for c in C:
    exact[(c['fields']['Full Name'], c['fields']['Phone'])].append(c)
print('people under EXACT raw (name, phone) match: %d (vs %d normalized)' % (len(exact), len(people)))
# multi-row people: same opening or different?
mp = {k: v for k, v in people.items() if len(v) > 1}
same = diff = 0
for k, rows in mp.items():
    ops = [x['oid'] for c in rows for x in apps_by_cid[c['id']]]
    if len(ops) != len(set(ops)):
        same += 1
    else:
        diff += 1
print('multi-row people: with a repeated opening=%d, all openings distinct=%d' % (same, diff))
print('multi-row people: email same across rows=%d, differs=%d' % (
    sum(1 for v in mp.values() if len({(c['fields'].get('Email') or '').lower() for c in v}) == 1),
    sum(1 for v in mp.values() if len({(c['fields'].get('Email') or '').lower() for c in v}) > 1)))
# Rule D: dropped rows later than kept hired; gap days
import datetime


def dt(s):
    return datetime.date.fromisoformat(s)


gaps = [abs((dt(k['applied']) - dt(r['applied'])).days) for r, k in dropped]
print('Rule D gap in days between dropped and kept Applied On: min=%s max=%s sorted=%s' % (
    min(gaps) if gaps else None, max(gaps) if gaps else None, sorted(gaps)))
print('Rule D dropped rows where kept row is Hired but dropped row applied LATER: %d' % sum(
    1 for r, k in dropped if k['hired'] and r['applied'] > k['applied']))
print('Rule D dropped rows whose group differs from kept row: recorded=%d evidence=%d' % (
    sum(1 for r, k in dropped if r['rec'] != k['rec']), sum(1 for r, k in dropped if r['ev'] != k['ev'])))
print('Rule D dropped rows still active (Status Active): %d; kept rows Status: %s' % (
    sum(1 for r, _ in dropped if r['status'] == 'Active'), dict(Counter(k['stage'] for _, k in dropped))))
# hires vs headcount
hper = Counter(x['oid'] for x in apps if x['hired'])
print('openings with hires > Headcount:')
for oid, n in sorted(hper.items(), key=lambda t: opening[t[0]]['Req ID']):
    of = opening[oid]
    if n > (of.get('Headcount') or 0):
        hs = [x for x in apps if x['oid'] == oid and x['hired']]
        print('   %s status=%s headcount=%s hires=%d -> %s' % (of['Req ID'], of['Status'], of.get('Headcount'), n,
                                                              [(x['appid'], x['person'][0], x['rid'] in kept_ids) for x in hs]))
print('Filled openings with zero hires: %s' % sorted(of['Req ID'] for oid, of in opening.items()
                                                      if of.get('Status') == 'Filled' and hper.get(oid, 0) == 0))
print('hires by opening status (Rule D survivors):', dict(Counter(x['ostatus'] for x in surv if x['hired'])))
# date oddities
print('applications with Closed On < Applied On: %d (hires among them: %d)' % (
    sum(1 for x in apps if x['closed'] and x['closed'] < x['applied']),
    sum(1 for x in apps if x['closed'] and x['closed'] < x['applied'] and x['hired'])))
print('hired rows with no Closed On: %d; hired rows with Status Active: %d' % (
    sum(1 for x in apps if x['hired'] and not x['closed']), sum(1 for x in apps if x['hired'] and x['status'] == 'Active')))
print('applications with Applied On before candidate Created On: %d' % sum(
    1 for x in apps if x['applied'] < (cand[x['cid']].get('Created On') or '')))
opened = {oid: of.get('Opened On') for oid, of in opening.items()}
print('applications with Applied On before opening Opened On: %d (hires: %d)' % (
    sum(1 for x in apps if opened[x['oid']] and x['applied'] < opened[x['oid']]),
    sum(1 for x in apps if opened[x['oid']] and x['applied'] < opened[x['oid']] and x['hired'])))
# offers vs hired
try:
    OF = load('Offers')
    print('Offers status:', dict(Counter(o['fields'].get('Status') for o in OF)))
    offer_by_app = defaultdict(list)
    for o in OF:
        for a in o['fields'].get('Application', []):
            offer_by_app[a].append(o['fields'].get('Status'))
    print('hired rows with no linked Offer: %d; hired rows offer statuses: %s' % (
        sum(1 for x in apps if x['hired'] and not offer_by_app.get(x['rid'])),
        dict(Counter(tuple(sorted(map(str, offer_by_app.get(x['rid'], [])))) for x in apps if x['hired']))))
    print('non-hired rows with an Accepted offer: %s' % sorted(
        (x['appid'], x['stage']) for x in apps if not x['hired'] and 'Accepted' in offer_by_app.get(x['rid'], [])))
except Exception as e:  # noqa
    print('offers check skipped:', e)
# referred-by validity
try:
    P = {p['id']: p['fields'] for p in load('People')}
    rbs = [r for a in A for r in a['fields'].get('Referred By', [])]
    print('Referred By links: %d, resolving to a People record: %d, distinct referrers: %d' % (
        len(rbs), sum(1 for r in rbs if r in P), len(set(rbs))))
except Exception as e:  # noqa
    print('people check skipped:', e)
# person-level referral inconsistency
pc = 0
for k, rows in people.items():
    xs = [x for c in rows for x in apps_by_cid[c['id']]]
    if any(x['hasref'] for x in xs) and not all(x['hasref'] for x in xs):
        pc += 1
print('people with Referred By on some but not all of their applications: %d' % pc)
cc = sum(1 for c in C if any(x['hasref'] for x in apps_by_cid[c['id']]) and not all(x['hasref'] for x in apps_by_cid[c['id']]))
print('candidate records with Referred By on some but not all applications: %d' % cc)
# effect of "Referred internally" notes as evidence
ri_ids = {c['id'] for c in ri}
ev2 = [x for x in surv if x['ev'] != 'Referral' and x['cid'] in ri_ids]
print('Rule D survivors not evidence-Referral but candidate Notes say "Referred internally": rows=%d hires=%d (by rec group: %s; hires by rec group: %s)' % (
    len(ev2), sum(x['hired'] for x in ev2), dict(Counter(x['rec'] for x in ev2)),
    dict(Counter(x['rec'] for x in ev2 if x['hired']))))
# Source whitespace / case variants
print('raw Source values with surrounding whitespace or case variants: %s' % sorted(
    {repr(c['fields'].get('Source')) for c in C if (c['fields'].get('Source') or '') != (c['fields'].get('Source') or '').strip()
     or (c['fields'].get('Source') or '').strip().lower() in ('job board', 'referral') and c['fields'].get('Source') not in ('Job Board', 'Referral')}))
print('Other group composition (candidates):', dict(Counter(c['fields'].get('Source') for c in C if grp(c['fields'].get('Source')) == 'Other')))
print('Other group hires by raw Source (all rows):', dict(Counter(x['source'] for x in apps if x['hired'] and x['rec'] == 'Other')))
print('Hires by raw Source, all rows:', dict(Counter(x['source'] for x in apps if x['hired'])))
print('Hires by raw Source, S4 basis (survivor, strict, recorded source):', dict(Counter(x['source'] for x in surv if x['strict'])))

print()
print('=== EXTRA ===')
print('multi-row people detail:')
for k, rows in sorted(mp.items()):
    for c in sorted(rows, key=lambda c: c['fields']['Created On']):
        print('  %s | %s | %s | created %s | apps: %s' % (k[0], c['fields']['Candidate ID'], c['fields'].get('Source'),
              c['fields']['Created On'], [(x['appid'], x['req'], x['stage'], x['applied'], 'REF' if x['hasref'] else '-') for x in apps_by_cid[c['id']]]))
pstrict = {k: any(x['strict'] for c in rows for x in apps_by_cid[c['id']]) for k, rows in people.items()}
print('people with a strict hire: %d; by P0: %s; by P1: %s' % (sum(pstrict.values()),
      dict(Counter(p0[k] for k in p0 if pstrict[k])), dict(Counter(p1[k] for k in p1 if pstrict[k]))))
sr = [x for x in apps if x['source'] == 'Referral']
print('Source=Referral: hires on candidates WITH Referred By=%d of %d rows; WITHOUT=%d of %d rows' % (
    sum(x['hired'] for x in cells[(True, True)]), len(cells[(True, True)]), sum(x['hired'] for x in cells[(True, False)]), len(cells[(True, False)])))
alt_p0 = {}
for k, rows in people.items():
    base = sorted(rows, key=lambda c: (c['fields'].get('Created On') or '', c['fields'].get('Candidate ID')))[0]
    alt_p0[k] = grp(base['fields'].get('Source'))
print('P0 variant using earliest Created On for everyone: people %s ; hired %s' % (
    dict(Counter(alt_p0.values())), dict(Counter(alt_p0[k] for k in alt_p0 if phired[k]))))
