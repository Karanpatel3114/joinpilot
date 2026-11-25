# JoinPilot: build plan

Each task is one commit, using the message shown. Work top to bottom with the `next-task` skill. Each milestone has its own branch and pull request (see .claude/rules/git-commits.md). Tick a task's box in the same commit that completes it.

**Resume checkpoints**
- After M6, add JoinPilot to the resumes with real evaluation numbers.
- After M11, add the live link.

---

## M0: Bootstrap (branch `m0-bootstrap`)
Done when: an empty but runnable API and console exist, and CI runs on every push.

M0.1 is the repository's first commit, made directly on `main`. Create `m0-bootstrap` from `main` after it.

- [x] M0.1 `chore: add project spec, plan and Claude Code configuration`
- [x] M0.2 `build: initialize uv project with Python 3.12, ruff, mypy and pytest`
- [x] M0.3 `chore: add env example, settings module and domain errors`
- [x] M0.4 `feat(api): add FastAPI app with health endpoint and test`
- [x] M0.5 `build(web): scaffold Vite React TypeScript Tailwind console with lint, typecheck and Vitest`
- [x] M0.6 `ci: add GitHub Actions workflow for backend and web checks`
- [x] M0.7 `docs: add README skeleton and MIT license`

## M1: Synthetic ERP data (branch `m1-erp-data`)
Done when: the generator produces deterministic datasets in both naming modes, with gold answers and passing tests.

- [x] M1.1 `feat(synth): generate customer and product master tables from a seed`
- [x] M1.2 `feat(synth): generate sales order headers and items`
- [x] M1.3 `feat(synth): generate customer open items with due dates`
- [x] M1.4 `feat(synth): add SAP-style and friendly naming modes`
- [x] M1.5 `feat(synth): plant data-quality issues with configurable rates`
- [x] M1.6 `feat(synth): write gold join graph, KPI values and question answers`
- [x] M1.7 `test(synth): add determinism and gold consistency tests`
- [x] M1.8 `feat(data): add TPC-H loader with its gold foreign-key graph`
- [x] M1.9 `docs(data): document tables, planted issues and licenses`

## M2: Profiling (branch `m2-profiling`)
Done when: any uploaded table gets column statistics, candidate keys and overlap scores through the API.

- [x] M2.1 `feat(profiling): load CSV and Parquet uploads into a per-project DuckDB file`
- [x] M2.2 `feat(profiling): compute column statistics`
- [x] M2.3 `feat(profiling): detect single and two-column candidate keys`
- [x] M2.4 `feat(profiling): compute inclusion scores between columns with sampling`
- [x] M2.5 `feat(profiling): normalize key values and record the normalization`
- [x] M2.6 `feat(profiling): profile a project and assign stable evidence ids`
- [x] M2.7 `feat(api): add project, upload and profile endpoints`
- [x] M2.8 `test(profiling): add property-based tests for statistics and keys`

## M3: Join candidates and baseline evaluation (branch `m3-join-candidates`)
Done when: deterministic join candidates are scored and evaluated against gold, with baselines.

- [x] M3.1 `feat(joins): generate candidate joins from names, types and overlap`
- [x] M3.2 `feat(joins): score candidates and infer cardinality and fan-out risk`
- [x] M3.3 `feat(eval): measure join discovery precision, recall and F1 against gold`
- [x] M3.4 `feat(eval): add name-only and overlap-only baselines and a results writer`
- [x] M3.5 `docs(eval): record baseline results and decisions`

## M4: Agent with LangGraph (branch `m4-agent`)
Done when: the agent turns a requirement and candidates into a ranked, explained join graph that cites evidence, and is evaluated against baselines.

- [x] M4.1 `feat(llm): add provider interface with Gemini and fake providers`
- [x] M4.2 `feat(llm): log tokens, latency and cost with retries and backoff`
- [x] M4.3 `feat(agent): add LangGraph state and graph skeleton`
- [x] M4.4 `feat(agent): parse requirements into entities, measures and filters`
- [x] M4.5 `feat(agent): rank and explain joins with evidence citations`
- [x] M4.6 `feat(agent): reject explanations with unknown or contradicting evidence`
- [x] M4.7 `feat(eval): compare the agent with baselines and an LLM-only ablation`
- [x] M4.8 `feat(obs): add optional Langfuse tracing`

## M5: Persistence and human approval (branch `m5-approval`)
Done when: runs persist in Postgres, pause for approval, and resume in a background worker.

- [x] M5.1 `feat(db): add Postgres models and Alembic migrations`
- [x] M5.2 `build(infra): add docker-compose with Postgres, pgvector and Redis`
- [x] M5.3 `refactor(services): store projects in the database instead of JSON files`
- [x] M5.4 `feat(agent): add Postgres checkpointer and approval interrupt`
- [x] M5.5 `feat(api): add run, proposal, approval and resume endpoints`
- [x] M5.6 `feat(jobs): run agent steps in an arq worker with status polling`
- [ ] M5.7 `feat(db): add pgvector glossary search from business terms to columns`

## M6: View generation and automated SIT (branch `m6-views-checks`)
Done when: approved joins become guarded SQL views that pass SIT checks, and evaluation reports view validity and KPI correctness. **MVP gate: add JoinPilot to the resumes now.**

- [ ] M6.1 `feat(sqlgen): generate views from approved joins and the requirement`
- [ ] M6.2 `feat(sqlgen): add sqlglot guard with statement and identifier allowlists`
- [ ] M6.3 `feat(checks): add SIT suite for counts, fan-out, orphans, null keys, buckets and totals`
- [ ] M6.4 `feat(agent): repair failing views using check results`
- [ ] M6.5 `feat(sqlgen): export the model to Postgres, Snowflake and BigQuery dialects`
- [ ] M6.6 `test(sqlgen): add SQL red-team cases and prove they are blocked`
- [ ] M6.7 `feat(eval): measure view validity and KPI correctness against gold`

## M7: Web console (branch `m7-console`)
Done when: the whole flow, from upload to approved views, works in the browser.

- [ ] M7.1 `feat(web): add project list and upload flow`
- [ ] M7.2 `feat(web): add profile explorer`
- [ ] M7.3 `feat(web): add join graph view with evidence panel`
- [ ] M7.4 `feat(web): add approval workflow and run status`
- [ ] M7.5 `feat(web): add SQL viewer with check results`
- [ ] M7.6 `test(web): add component tests and a Playwright happy-path test`
- [ ] M7.7 `docs: add console screenshots to README`

## M8: KPI dashboard (branch `m8-dashboard`)
Done when: a dashboard is generated from metric definitions, and KPI values match gold in evaluation.

- [ ] M8.1 `feat(kpi): define metrics from the requirement and model`
- [ ] M8.2 `feat(kpi): compute metrics on approved views`
- [ ] M8.3 `feat(api): add dashboard endpoint`
- [ ] M8.4 `feat(web): add generated dashboard page`

## M9: Ask questions (branch `m9-qa`)
Done when: plain-English questions get guarded, read-only SQL answers with the query shown, and accuracy is evaluated.

- [ ] M9.1 `feat(qa): generate SQL from questions over the semantic model`
- [ ] M9.2 `feat(qa): run answers read-only with guard, limit and timeout`
- [ ] M9.3 `feat(eval): measure question-answering execution accuracy`
- [ ] M9.4 `feat(web): add ask panel showing SQL and evidence`

## M10: MCP server (branch `m10-mcp`)
Done when: Claude Desktop or Claude Code can list projects, profile tables, propose joins, run checks and ask questions through JoinPilot.

- [ ] M10.1 `feat(mcp): add MCP server with JoinPilot tools`
- [ ] M10.2 `test(mcp): add tool contract tests`
- [ ] M10.3 `docs(mcp): add setup guide and demo GIF`

## M11: Ship it (branch `m11-deploy`)
Done when: JoinPilot runs at a public URL with CI building Docker images and running an evaluation smoke test. **Add the live link to the resumes.**

- [ ] M11.1 `build(infra): add Dockerfiles for API, worker and web`
- [ ] M11.2 `ci: build Docker images and run an evaluation smoke test`
- [ ] M11.3 `feat(api): add rate limits and request size limits`
- [ ] M11.4 `build(infra): deploy database, Redis, API and web`
- [ ] M11.5 `docs: add deployment guide and live demo link`

## M12: Auth and polish (branch `m12-polish`)
Done when: the public demo is safe, the final evaluation is in the README, and v1.0.0 is tagged.

- [ ] M12.1 `feat(auth): add Supabase sign-in and per-user projects`
- [ ] M12.2 `feat(web): add demo mode with a preloaded sample project`
- [ ] M12.3 `feat(eval): run the final test split and publish results`
- [ ] M12.4 `docs: add architecture diagram, limitations and demo video`
- [ ] M12.5 `chore: release v1.0.0 with changelog`
