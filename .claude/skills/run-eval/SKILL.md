---
name: run-eval
description: Run JoinPilot's evaluation suite (join discovery against gold, view validity and SIT pass rate, KPI correctness, text-to-SQL accuracy, the SQL red-team set, latency and cost), save the results with date and commit hash, and compare them with the previous run. Use this after any change to profiling, joins, agent prompts, sqlgen, checks, kpi or qa, before updating README numbers, and whenever the owner asks how well JoinPilot works.
---

# Run evaluation

The full plan is in docs/eval-plan.md. The honesty rules are in `.claude/rules/data-and-eval.md`.

## Steps

1. Make sure the working tree is committed, so the results map to one commit hash.
2. Run the dev split: `uv run python -m eval.run_all --split dev`. Run the test split only when the owner explicitly says "final run".
3. The script writes `eval/results/<YYYY-MM-DD>-<shorthash>-<split>/` with `metrics.json` and `metrics.md`, and updates `eval/results/latest-<split>.md`. Each file records seeds, the data fingerprint, the commit hash and the date.
4. Ask the `eval-analyst` subagent to compare the run with the previous one: what improved, what regressed, and whether any change looks suspicious.
5. Summarize for the owner in plain language: the headline numbers next to the baselines, the biggest change since the last run, and the main remaining failure type.
6. Commit the results with `commit-step` (type `chore(eval)` or `docs(eval)`). Update the README results table only from these files, and include the date and commit.

## Never
- Tune thresholds or prompts on the test split.
- Report a number that isn't in a results file.
- Drop failed cases from the denominator.
