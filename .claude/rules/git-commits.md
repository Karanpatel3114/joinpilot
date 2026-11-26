# Git and commit rules

The owner wants a steady, readable history on GitHub: many small commits, each one a complete step.

## One task, one commit
- Every task in docs/PLAN.md becomes exactly one commit. Never bundle tasks, and never leave a task half-committed.
- Commit only after the `verify` skill passes. Never skip, delete or weaken a test to get a green run.
- Tick the task's checkbox in docs/PLAN.md in the same commit.
- Aim for under about 300 changed lines, excluding lockfiles and test fixtures. If a task grows past that, stop and propose splitting it in PLAN.md.

## Message format (Conventional Commits)
```
type(scope): short imperative summary, 72 characters or fewer

Why this change was needed and what it does, in 1 to 4 plain sentences.

Task: M2.3
```
- Types: feat, fix, test, docs, refactor, perf, build, ci, chore.
- Scope is the module: synth, profiling, joins, agent, llm, sqlgen, checks, kpi, qa, api, db, jobs, web, mcp, eval, infra, docs.
- Use the exact commit message written for the task in PLAN.md unless the work changed.

## Approval and pushing
- Before committing, show the owner a plain-language summary, the files changed and the check results, plus the proposed message, and wait for a clear yes.
- After each commit, push to origin straight away so GitHub shows real, steady progress.

## Branches and pull requests
- One branch per milestone, named like `m2-profiling`, created from an up-to-date `main`.
- When a milestone's tasks are all done, run the `code-reviewer` subagent, fix any blocking issues as their own commits, then open a pull request with `gh pr create`.
- The pull request description lists the tasks, what changed, how it was tested, and any evaluation numbers.
- Merge only after CI passes, using a merge commit (never squash) so every task commit stays visible. Then delete the branch.

## Never
- Force-push, rebase or otherwise rewrite history that has been pushed.
- Change commit dates or authors.
- Commit secrets, `.env`, generated data (`data/generated/`), DuckDB files, `node_modules/`, `.venv/` or large binaries.
- Add Co-Authored-By trailers (the owner's choice).
