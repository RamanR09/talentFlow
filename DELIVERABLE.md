# TalentFlow Q3 roadmap: Acme data review

## 1. Memo (one page)

**To:** Head of Product. **From:** PM, TalentFlow. **About:** Acme's two asks for next quarter.

**Do not bring the job-board integration forward.** Job boards are Acme's biggest source of applications, but they turn 2.8% of them into hires. All other sources together turn 14.6%.

**Do not build a feature to move offer acceptance.** The 72% counts 5 stale pending offers as failures. On decided offers it is 83.9% (26 of 31). The true rate sits between 72.2% and 86.1%.

**Spend the quarter fixing what the product records.** Both of the VP's numbers are correct arithmetic on records the product let go wrong.

**What sits under the verdicts**

- Referral cannot be sized from this data. On 34 of the 37 applications that carry a referral signal, the two signals contradict each other. That includes 10 of the 26 hires.
- There are only 5 declined offers. Pay and speed look the same for accepted and declined offers. That is too small to act on.
- 66 of 105 active applications sit on openings that are not open.

**What we are building, in order of the decision each one unblocks**

| Rank | Build | Size | Decision it unblocks |
|---|---|---|---|
| 1 | Attribution and identity | Around 2 weeks | Which channels to invest in. The VP wants this made now and the data cannot support it. |
| 2 | Offer lifecycle and the acceptance dashboard | Around 1.5 weeks | The number the board is asking about. |
| 3 | Pipeline hygiene | Around 2 weeks | None is waiting on it, so it gives first if something slips. |

That is 5.5 of the 6 weeks, with 0.5 held as buffer. The sizes have not been checked with engineering.

**What we are not building**

- The job-board integration. Volume is not the constraint.
- Anything on comp or negotiation. 5 declines is too small to act on.
- Anything that depends on interview scores. 8 of 36 offers went out on 1 recorded interview, and that interview said no.

**What I trust and what I do not**

I ran 77 checks. 46 came back clean, and the counts of applications, hires and offers hold. I do not trust three things: where a candidate came from, the status of an offer, and the status of an opening. Section 5 shows how each one moved the answers.

**What is next**

- Ask Acme's recruiters how the 5 stale offers ended. One answer turns the range into a single number for the board.
- Tell the VP and the board that at 31 decided offers a year the interval is 25 points wide. A move of a few points will not be visible within a year.
- Find out why 4 of 26 hires sit on Cancelled openings, and whether the 84 of 300 candidates created after their first application are an import artefact.
- Re-run the channel comparison one quarter after attribution ships. That is the first point at which referral can be sized.

## 2. D1 Verdicts on the VP's two claims

### Claim 1: bring the job-board integration forward

The VP is right that job boards are the biggest channel, but only on applications, not on hires. Job boards bring 236 of 350 applications (67.4%) and 7 of 26 hires (26.9%). That is how she got to 26.9%. Referral brings the same 7 of 26 hires from 13 applications. What decides this is conversion. As recorded, job boards turn 3.0% of applications into hires. On my best estimate it is 2.8% (6 of 217). That estimate removes repeat applications and counts referred applications as referrals. On the same basis all other sources together convert at 14.6% (19 of 130), which is 5.3 times higher. Job boards stay between 1.8% and 3.0% in every scenario I ran, and the intervals never touch. Those 7 job-board hires took 189 screens and 90 interviews. More job-board volume means more load on the team, not more hires.

The real finding under her claim is attribution. Referral cannot be sized from this data. 37 applications carry a referral signal, and on 34 of them (91.9%) the two signals contradict each other. The source field says one thing and the referrer field says another. That covers 10 of the 26 hires (38.5%), which is every hire with any referral signal. Until the product records source properly, no channel decision here is safe.

**Verdict: build something different. Build source attribution, not the job-board integration. Deciding number: job boards convert 2.8% of applications into hires (6 of 217), against 14.6% for all other sources together (19 of 130).**

### Claim 2: offer acceptance is around 72% and needs to move

The 72% is real arithmetic, but it is not the acceptance rate. It is 26 accepted out of all 36 offers (72.2%), and it counts 5 pending offers as not accepted. Those 5 are not live offers. 4 of the 5 already carry a decision date. They have been open 41 to 243 days, and no decided offer in this data took more than 20 days. Nobody updated the status. On decided offers only, acceptance is 83.9% (26 of 31). The interval is wide, 67.4% to 92.9%, because the base is small. We do not know how the 5 stale offers ended, so the true rate sits between 72.2% and 86.1%.

There is no lever in this data to move the number. There are only 5 declines: 3 counter offer, 1 compensation, 1 location. Pay does not separate them. Accepted offers sit at a median 1.15 of expected pay and declined offers at 1.14. Speed does not either, at 5.5 days from final interview to offer against 6. Five declines is too small to act on, and a feature built on them would be a guess. The status problem also goes past the pending offers. All 5 declined offers still show their application at the Offer stage.

**Verdict: build something different. Fix the offer lifecycle and instrument the metric, not a feature to move the number. Deciding number: 5 stale pending offers swing the rate between 72.2% and 86.1%. On decided offers it is 83.9% (26 of 31).**

## 3. D2 The six engineer weeks

All three builds fix what the product records. None adds volume or a new feature. They take 5.5 of the 6 weeks, with 0.5 held as buffer.

### Building, in order

Ranked by the decision each build unblocks, not by records touched. Attribution is first because the VP wants the channel decision made this quarter and this data cannot support it. Offer lifecycle is second because it fixes the number the board is asking about. Hygiene is third: it touches the most records, but nobody is waiting on it to decide anything, which is also why it is the one that gives if something slips.

| Rank | What | Size in weeks | Deciding number |
|---|---|---|---|
| 1 | Attribution and identity. Source is captured per application. Referral is set automatically when a referrer is linked. A duplicate check runs on name and phone. | Around 2 (1.5 to 2.5) | 34 of 37 applications with a referral signal contradict themselves (91.9%). That covers 10 of 26 hires (38.5%). 12 of 300 candidate rows are 6 people entered twice, and 3 of those rows hold a hire. A match on email would catch 0 of the 12. |
| 2 | Offer lifecycle and the section 4 dashboard. Status cannot stay Pending once a decision date exists. An alert fires when an offer is open past 20 days, the longest genuine decision in this data. At 30 days the offer is marked Unresolved, as in section 4. | Around 1.5 (1 to 2) | 10 of 36 offers (27.8%) carry a wrong status. 5 are stale pending offers, 4 of them with a decision date. 5 of 5 declined offers still show their application at the Offer stage. Together they swing the rate between 72.2% and 86.1%. |
| 3 | Pipeline hygiene. Active applications on openings that are not open get flagged. Headcount is reconciled with hires. | Around 2 (1.5 to 2.5) | 66 of 105 active applications (62.9%) sit on openings that are not open, 55 of them on filled ones. 68 of 105 (64.8%) have not moved in over 90 days. 10 of 24 openings disagree with their own hires. |

### Not building

| What | Why not |
|---|---|
| Job-board integration | Conversion is the reason. Job boards convert 2.8% of applications into hires against 14.6% for all other sources. Volume is not the constraint. The 7 job-board hires already took 189 screens and 90 interviews. |
| Anything on comp or negotiation to move acceptance | 5 declines is not a base to build on. Accepted and declined offers look the same on pay (1.15 against 1.14 of expected) and on speed (5.5 days against 6). |
| Anything that depends on interview scores | 8 of 36 offers (22.2%) went out on 1 recorded interview, and that interview said no. Either the interview record is incomplete or the process lets this happen. I cannot build on interview scores until that is understood. |

The builds add up to 5.5 weeks. The other 0.5 week is buffer, and I would rather state it than pretend the plan is exactly 6. The sizes are rough and have not been checked with engineering. If a build runs to the top of its range, the buffer goes first. After that the headcount reconciliation in build 3 moves out, because it is ranked last.

## 4. D3 Metrics spec, offer acceptance rate

Offer acceptance rate is accepted offers over decided offers, on a trailing twelve months, read only from the Offers table. Pending offers sit beside the rate as a count and never inside it. Putting them inside is how the 72 got made.

### Definition

| Item | Rule |
|---|---|
| Unit | One offer, not one person. One counted offer per application: the latest by Offers.Offered On, ties broken by the highest Offer ID. Earlier offers on that application are superseded. A superseded offer drops out of every count and off the fix list, whatever its status. |
| Numerator | Counted offers in the window with Status Accepted or Reneged. |
| Denominator | The numerator plus counted offers in the window with Status Declined. |
| Shown beside the rate, never inside it | Pending, Unresolved, Broken and Withdrawn, each as a count. |
| Pending | Status Pending, no Decision On, offered 30 days ago or less. |
| Unresolved | Status Pending, no Decision On, offered more than 30 days ago. Days are the as-of date minus Offers.Offered On. |
| Broken | Status Pending with a Decision On. Or no Offered On. Or a Status not named in this table. Excluded and put on a fix list. |
| Withdrawn | The company pulled the offer before the candidate decided. |
| Reneged | The candidate accepted and then did not start. It stays an accepted offer. |
| Source of truth | Offers.Status and Offers.Offered On only. Never Applications.Stage or Applications.Offered On. Join offers to applications by the record link, never by Application ID. |
| Attribution date | Offers.Offered On. An offer belongs to the window its offered date falls in. |
| Window | From the as-of date minus 364 days to the as-of date, both days included. That is 365 days. The as-of date is today in the account's time zone. |
| Minimum n | 20 decided offers in the window. |
| Output | Percentage rounded half up to 1 decimal. The 95% Wilson interval with z = 1.96 and no continuity correction, bounds rounded the same way. The counts as "accepted of decided". |

### What the dashboard shows

| State | When | What appears |
|---|---|---|
| Normal | 20 or more decided. No offer is Unresolved or Broken. | Rate, interval, counts, pending count. |
| Ambiguous | 20 or more decided. At least one offer is Unresolved or Broken. | Rate and interval, marked amber, with a link to the fix list. A range appears only when an offer is Unresolved or is Pending with a Decision On: the rate if all of those were declined, and the rate if all were accepted. Other broken offers have no place in the window, so they are on the fix list only. |
| Insufficient data | Fewer than 20 decided. | The words "Insufficient data" and the counts. No percentage. |
| Empty | No decided offers. Checked before Insufficient data. | The words "No decided offers" and the counts. |
| Past as-of date | Someone picks an earlier date. | The same rules, run on today's statuses. The screen says "Based on current statuses". History is not rebuilt. |
| Quarterly view | Always. | Counts per calendar quarter of Offers.Offered On. Never a percentage. The largest quarter in this data has 12 decided offers. |

### Order of steps

Every implementation runs these in this order.

| Step | What happens |
|---|---|
| 1 | Offers with no Offered On go to the fix list as Broken. They take no part in step 2. |
| 2 | Among dated offers, keep the latest per application. The rest are superseded and drop out of every count and off the fix list, whatever their status. |
| 3 | Apply the window to the kept offers. |
| 4 | Classify each kept offer in the window by the definition table. |

### Edge cases

The first seven are in this data today. The last five are cases I used to break the spec.

| Case | In this data | Rule | Effect |
|---|---|---|---|
| Pending offer that carries a decision date | 4 of 36 | Broken. Excluded. Fix list. | Inside the range, not the rate. |
| Pending, no decision date, open more than 30 days | 1 of 36 (OFF-00021) | Unresolved. Excluded. Fix list. | Inside the range, not the rate. No decided offer took more than 20 days. |
| Offered date differs between Offers and Applications | 3 of 36, gaps of 5, 7 and 11 days | Use Offers. | None today. A gap can move an offer across a window edge. |
| Declined offer whose application still says Offer stage | 5 of 5 declined | Read Offers.Status only. | Reading the application stage gives 72.2% (26 of 36). |
| Same person with two decided offers | 3 people | Each offer counts. The unit is the offer. | Counting per person gives 82.1% (23 of 28) if the latest offer counts, or 85.7% (24 of 28) if any acceptance counts. |
| Offer on a Cancelled or On Hold opening | 6 of 36 Cancelled, 2 of 36 On Hold | A candidate decision counts whatever the opening status is. | Dropping the Cancelled ones would give 88.0% (22 of 25). |
| Application ID is not unique | 1 of 36 offers joins to a shared ID | Join by record link. | A join on Application ID attaches the offer to two applications. |
| Revised offer on the same application | 0 of 36 | Latest offer counts. Earlier ones are superseded. | Test: 87.1% (27 of 31). Without the rule the application counts twice, 84.4% (27 of 32). |
| Accept, then renege before the start date | No field for it today | Status becomes Reneged and stays in the numerator. Never overwrite Accepted with Declined. Renege rate is its own metric. | Test: overwriting moved 83.9% to 80.6% (25 of 31) and rewrote a past period. |
| Company cancels the opening while an offer is live | None today | Status becomes Withdrawn. Outside the rate. Shown as a count. | Test: rate unchanged. |
| Offer with no offered date | 0 of 36 | Broken. No fallback to the Applications date. Fix list. | Test: excluded and listed. Fixed on the way: an undated offer used to vanish when its application had a second offer. |
| Decided offer with no decision date | 0 of 31 | Still counted. The offered date places it. Data warning. | None. |

On the day of the pull this spec shows the VP 83.9% (26 of 31), interval 67.4% to 92.9%, marked ambiguous with a range of 72.2% to 86.1% and 5 offers to fix, instead of a bare 72.

## 5. D4 What in this data I would not trust

I would not trust three things in this data: where a candidate came from, the status of an offer, and the status of an opening. Those three changed both verdicts. Most of the other errors are real but did not touch the two questions.

### How I looked

I pulled all 8 tables once and ran 77 checks on the cached copy. 31 failed and 46 came back clean. Every check reports the rows affected over the rows examined. I then took each failure to the two claims and re-ran the claim with that problem cleaned out, to see if the answer moved. A second, independent recount of the scenario numbers matched mine exactly. One of my own checks was wrong. It counted a missing interview recommendation as a no. Fixed, the figure is 8 of 36.

| Group | What it asks | Run | Failed |
|---|---|---|---|
| A. Uniqueness | Is each ID, person and application there once? | 12 | 5 |
| B. Links | Does every link point at a real record of the right kind? | 16 | 1 |
| C. Completeness | Are the fields that a status implies filled in? | 13 | 3 |
| D. Validity | Are values possible? Pay inside the band, scores in range. | 8 | 3 |
| E. Time order | Do dates run in the order events can happen? | 11 | 7 |
| F. Cross-table agreement | Do two tables tell the same story about one event? | 14 | 12 |
| G. Junk records | Are there test or empty records? | 3 | 0 |

The failures cluster where two tables describe the same event. That is where this product lets records drift.

### Failures that changed an answer

| What is wrong | How much | Answer it changed | By how much |
|---|---|---|---|
| The two referral signals contradict each other | 34 of 37 applications with a referral signal (91.9%). 10 of 26 hires (38.5%). | Claim 1 | Referral cannot be sized. Job boards' share of hires moves between 19.0% and 28.0% depending on the rule. Their conversion stays between 1.8% and 3.0%. |
| Source is stored once per candidate | 50 of 300 candidates (16.7%) have more than one application | Claim 1, build 1 | This is the cause of the row above. It made source per application the first build. |
| Repeat applications and repeat hires | 6 of 350 applications repeat a person on an opening. 26 hire rows are 24 people. | Claim 1, claim 2 | Removing repeats takes 350 rows to 347 and 26 hires to 25. Job boards stay at 3.0%. Acceptance per person is 82.1% to 85.7% against 83.9% per offer. |
| Duplicate candidate records | 12 of 300 rows are 6 people. 3 of the rows hold a hire. | Claim 1, build 1 | Small on the numbers. It set the duplicate check on name and phone, because a match on email would catch 0 of the 12. |
| Pending offers that are not pending | 4 of 5 pending offers carry a decision date. All 5 have been open 41 to 243 days. | Claim 2 | This is the whole gap between 72.2% and 83.9%. The honest answer is a range, 72.2% to 86.1%. |
| Declined offers whose application still says Offer | 5 of 5 | Claim 2, section 4 | Reading the application stage gives 72.2% (26 of 36). The spec reads the Offers table only. |
| Hires and offers on Cancelled openings | 4 of 26 hires. 6 of 36 offers. | Claim 1, claim 2 | Not counting those hires takes job boards to 1.8%. Dropping those offers would give 88.0% (22 of 25). I kept both in and said so. |
| Pay data on offers | 7 of 36 offers have base pay outside the band. 13 of 36 are below the candidate's current pay. | Claim 2 | It weakens the pay comparison (1.15 against 1.14). One more reason the 5 declines are too small to act on. |
| Offered date differs between Offers and Applications | 3 of 36, gaps of 5, 7 and 11 days | Section 4 | No number moved today. The spec takes the date from Offers. |
| Application ID is not unique | 8 of 350 rows share 4 IDs | Section 4 | 1 of 36 offers joins to a shared ID. The spec joins on the record link. |
| Offers made on one interview that said no | 8 of 36 offers (22.2%) | Section 3 | It put interview scores on the not-building list. |
| Opening status disagrees with the pipeline | 66 of 105 active applications sit on openings that are not open. 10 of 24 openings disagree with their own hires. 18 of 18 "Position Cancelled" rejections are on openings that were not cancelled. | Section 3 | It made pipeline hygiene the third build. |

Taken together, 15 of 36 offers carry at least one problem. On the offers with none, acceptance is 85.0% (17 of 20). So the mid-eighties reading does not depend on the bad rows.

### Failures that did not matter for these two questions

None of these feeds a source, a hire or an offer status. Many sit in the lowest-numbered records.

| What is wrong | How much |
|---|---|
| Candidate created after their first application | 84 of 300. Median gap 103 days, longest 345. |
| Interview dates that cannot be right | Completed before scheduled on 4 of 142. Scheduled before the application on 9 of 160. First interview date differs from the earliest interview on 13 of 143. |
| Interviews that did not happen but carry a score | 4 of 22 |
| Rejection reason on an application that was not rejected | 4 of 350. 14 withdrawn rows also use the field. |
| Expected pay below current pay | 4 of 300 candidates |
| Applied before the opening was opened | 3 of 350 |
| Proposed start date before the offer date | 3 of 36 |
| Application recruiter differs from the opening's recruiter | 4 of 350 |
| Free-text notes | 38 candidates are noted as referred, and only 4 of them have any structured referral signal. I did not use notes as evidence. |

### How the claim 1 numbers moved under each cleaning rule

Each cell is applications / hires. Referral carries no rate, because it cannot be sized.

| Cleaning rule | All rows | Job Board | Referral | Other |
|---|---|---|---|---|
| As recorded | 350 / 26 | 236 / 7 (3.0%) | 13 / 7 | 101 / 12 (11.9%) |
| A linked referrer counts as a referral | 350 / 26 | 219 / 6 (2.7%) | 37 / 10 | 94 / 10 (10.6%) |
| Repeat applications removed | 347 / 25 | 234 / 7 (3.0%) | 12 / 6 | 101 / 12 (11.9%) |
| Both rules together, my best estimate | 347 / 25 | 217 / 6 (2.8%) | 36 / 9 | 94 / 10 (10.6%) |
| Both rules, hires on Cancelled openings not counted | 347 / 21 | 217 / 4 (1.8%) | 36 / 7 | 94 / 10 (10.6%) |

Job Board and Other barely move. Referral moves from 12 applications to 37 and from 6 hires to 10. Only 3 applications carry both referral signals, and they produced 0 hires.

### What came back clean

This matters as much as the failures. It is why I trust the counts of applications, hires and offers.

| Check | Result |
|---|---|
| Every link points at a real record | 0 broken across 11 link fields |
| Application milestone dates in order | 350 of 350 |
| Hired applications match accepted offers | 26 of 26 |
| Applications with more than one offer | 0 of 36 |
| Offers with no offered date | 0 of 36 |
| Decided offers with no decision date | 0 of 31 |
| Test or junk records, and dates in the future | None |

### What I would check with more time

| Question | Why it matters |
|---|---|
| Why do 4 of 26 hires sit on Cancelled openings? | If the openings were cancelled after the hire, the hires stand. If the status is wrong, build 3 is bigger than it looks. |
| Are the 84 of 300 candidates created after their first application an import artefact, or something worse? | An import date is harmless. If records are being re-created, the duplicate count is an undercount. |
| How did the 5 stale offers actually end? | Acme's recruiters know. One answer turns the range of 72.2% to 86.1% into a single number. |
