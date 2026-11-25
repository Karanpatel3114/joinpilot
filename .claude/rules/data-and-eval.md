# Data and evaluation rules

## Data sources
- The synthetic ERP generator in `backend/joinpilot/synth/` (seeded and deterministic) is the main dataset. Its spec is docs/data-model.md.
- TPC-H, generated with DuckDB's tpch extension.
- Optionally a public text-to-SQL benchmark subset (for example BIRD mini-dev or Spider), only if its license allows it. Store it in `data/benchmarks/<name>/` with its LICENSE file and source link.
- Never use real company data. Never reproduce any client's or employer's data, names, schemas or business logic. SAP-style table and column names are used only as a public, generic naming style.

## Gold answers
- `data/gold/` holds the ground truth the generator knows: join graphs, KPI values and question answers. The generator writes it; it is never edited by hand.
- Only `eval/` scripts read gold files. The `joinpilot` package never imports from them, and gold content never appears in prompts, fixtures for app code, or the UI.
- Claude Code is denied read access to `data/gold/` in settings. During M1 the owner may lift this temporarily to debug the generator.

## Splits
- Dev: seeds and schemas used to tune heuristics, thresholds and prompts.
- Test: different seeds, both naming modes and TPC-H. Used only for final reporting, when the owner says "final run".
- Every results file records the split, seeds, a fingerprint of the data, the git commit hash and the date.

## Honest reporting
- Always report baselines next to JoinPilot's numbers, and include failures and limitations.
- Never tune on the test split. If a test result prompts a change, document it and rerun dev first.
- Any number in the README must come from a file in `eval/results/` and name its date and commit.
