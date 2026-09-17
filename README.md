# TalentFlow Q3 roadmap exercise

A product exercise. Acme's VP People made two claims from their recruiting data: job boards bring 26.9% of hires, and offer acceptance is around 72%. This repo checks both claims against Acme's Airtable base and decides how to spend 6 engineer-weeks.

**Start with [DELIVERABLE.md](DELIVERABLE.md).** Everything else is the evidence behind it.

## Where things are

| You want | Open |
|---|---|
| The one-page memo, verdicts, roadmap, metric spec and data review | [DELIVERABLE.md](DELIVERABLE.md) |
| Every number used, with its method and confidence | [output/findings.csv](output/findings.csv) |
| The raw output behind each number | [output/](output/) |
| The code that produced it | [scripts/](scripts/) |

### DELIVERABLE.md sections

| Section | What it answers |
|---|---|
| 1. Memo | What to do, in one page |
| 2. Verdicts | Are the VP's two claims true? |
| 3. The six engineer weeks | What gets built, what does not, and why |
| 4. Metrics spec | How offer acceptance rate must be computed |
| 5. What I would not trust | What is wrong in the data and how it moved the answers |

### Scripts

| Script | What it does | Output |
|---|---|---|
| `pull.py` | Pulls all 8 tables once and caches them. Read-only, rate-limited. | `data/raw/` |
| `profile.py` | Lists every field with fill rate and values. | printed |
| `audit.py` | Runs 77 data-quality checks in seven groups. | `output/audit.txt` |
| `claims.py` | Rebuilds the two claims and the funnel. | `output/claims.txt` |
| `source_scenarios.py` | Re-counts claim 1 under each cleaning rule. | `output/source_scenarios.txt` |
| `metric_spec.py` | Reference implementation of the section 4 spec, with edge-case tests. | `output/metric_spec.txt` |
| `roadmap_numbers.py` | Counts the records each roadmap item touches. | `output/roadmap_numbers.txt` |
| `check_deliverable.py` | Fails if DELIVERABLE.md uses a number that is not in findings.csv. | printed |
| `verify_sources.py` | Independent recount of the claim 1 scenarios, written without sight of the main code. | `output/verify_sources.txt` |
| `verify_metric_round1.py`, `verify_metric_round2.py` | Two independent builds of the metric from the spec text alone. This is the "two engineers" test. | `output/verify_metric_round2.txt` |

## Re-run it

Python 3.9 or later. Standard library only, nothing to install.

1. Create `.env` in the repo root:
   ```
   AIRTABLE_TOKEN=<your key>
   AIRTABLE_BASE=appYePRAI75PMbQNQ
   ```
2. Pull the data once: `python3 scripts/pull.py`
3. Run any script, for example: `python3 scripts/audit.py`

Every script after the pull reads only the cached files, so the numbers repeat exactly.

## What is not in this repo, and why

| Left out | Why |
|---|---|
| `data/raw/*.json` | The tables hold candidate names, emails and phone numbers. Step 2 re-creates them. `data/raw/_manifest.json` is included, so you can confirm your pull has the same record counts as mine (pulled 2026-09-17). |
| `.env` | Holds the API key. |
| The assessment pack | It contains the API key. |
