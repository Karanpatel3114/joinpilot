---
name: erp-data
description: Generate, extend or debug JoinPilot's synthetic ERP dataset (customer master, product master and texts, sales order headers and items, customer open items for receivables and aging) with SAP-style or friendly names, planted data-quality issues and generator-written gold answers. Use this for any work in backend/joinpilot/synth/, data/, docs/data-model.md, new test schemas, or whenever realistic ERP test data is needed.
---

# Synthetic ERP data

The spec is docs/data-model.md. Read it before changing the generator.

## Principles
- **Deterministic:** the same seed, size and naming mode always produce byte-identical output. A test checks this with a hash.
- **Known ground truth:** the generator knows the true keys and joins, so it writes the gold files itself. Gold is never edited by hand.
- **Realistic difficulty:** planted issues make join discovery and checks non-trivial: leading-zero key mismatches, orphan keys, duplicate customers, null keys, a language fan-out trap and string-typed dates.
- **Generic:** SAP-style names (for example KUNNR, MATNR, VBELN) are a public naming style only. Nothing comes from any real company, client or project.

## Interface
```
uv run python -m joinpilot.synth.generate --seed 1 --size S --naming sap --out data/generated/erp_s1_sap
```
- Sizes: S, M and L (row counts in docs/data-model.md).
- Naming: `sap` (cryptic) or `friendly` (readable).
- Output: one Parquet file per table, plus `manifest.json` with the seed, size, naming, row counts and data fingerprint.
- Gold output: `data/gold/<dataset_id>/joins.json`, `kpis.json` and `qa.jsonl`.

## When you change the generator
1. Update docs/data-model.md first if a table, column or planted issue changes.
2. Keep the planted-issue rates in config, not inline.
3. Regenerate the gold files and run the determinism and gold-consistency tests.
4. Commit generator code and gold together. Generated data itself stays gitignored.
