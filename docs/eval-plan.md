# Evaluation plan

The goal is honest numbers that show what JoinPilot does well and where it fails, always next to simple baselines.

## 1. Join discovery
- **Unit:** a directed column pair (from, to), compared with `joins.json`.
- **Metrics:** precision, recall and F1; normalization accuracy (did it detect the BSID leading-zero mismatch?); fan-out flag recall (did it flag MAKT?); decoy rejection rate.
- **Systems compared:**
  1. Name-only baseline: exact or fuzzy name match plus type compatibility.
  2. Overlap-only baseline: inclusion ratio at or above a threshold.
  3. LLM-only ablation: schema text with no profiling evidence.
  4. JoinPilot deterministic: candidates and scoring, with no LLM.
  5. JoinPilot full: with LLM ranking and evidence.

## 2. Views and SIT checks
- **Metrics:** share of generated views that parse, pass the guard and execute; share of SIT checks passing on the first try and after repair; average repair attempts.
- **Approval modes:**
  - *Approve-all:* every proposed join is accepted, with no human.
  - *Oracle review:* the evaluation harness approves only true joins, simulating a perfect reviewer.
  - Only the harness may read gold for this; the app never does.

## 3. KPI correctness
- **Metric:** the share of KPI values matching `kpis.json`. Counts must match exactly. Sums must be within 0.01% relative error.

## 4. Question answering
- **Metric:** execution accuracy, meaning the returned rows equal the gold result set (order-insensitive unless the question asks for an order).
- **Sets:** the ERP question set (`qa.jsonl`) and, if used, a benchmark subset.
- **Safety:** the share of attacks in `eval/redteam/sql_attacks.jsonl` that are blocked (target 100%), and the share of harmless questions wrongly blocked.

## 5. Operations
- p50 and p95 latency per stage.
- Tokens and estimated cost per run.
- Time from upload to an approved model in approve-all mode.

## Procedure and honesty
- Run LLM-based evaluations 3 times on dev, and report the mean and the range. A change smaller than the range is noise.
- Tune only on dev. Run test only when the owner says "final run".
- Each results folder records the split, seeds, data fingerprint, commit hash and date.
- Keep failed cases in every denominator, and list the top failure types with example case IDs.
