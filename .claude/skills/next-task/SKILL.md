---
name: next-task
description: Pick up the next unchecked task in docs/PLAN.md and take it all the way from plan to a verified, approved, pushed commit. Use this whenever the owner says "next task", "continue", "keep going", "what's next", starts a new work session, or names a task ID like M3.2, even if they don't mention the plan.
---

# Next task

The owner builds JoinPilot one task at a time. Each task in docs/PLAN.md becomes exactly one commit.

## Steps

1. **Find the task.** Read docs/PLAN.md. Take the first unchecked task in the current milestone, or the task ID the owner named. If it is the first task of a milestone, create the milestone branch from an up-to-date `main` (for example `git switch main && git pull && git switch -c m2-profiling`).
2. **Explain it plainly.** In 2 or 3 sentences, say what this task does and why it matters for the product, as if to a smart non-expert.
3. **Plan.** List the files you will create or change, the tests you will add, any risks, and the commit message from PLAN.md. If the task touches the API contract, SQL safety, `data/gold/`, prompts or the architecture, stop and wait for the owner's OK. Otherwise continue.
4. **Implement the smallest complete change.** Write or update tests first where practical. Follow the rules in `.claude/rules/`.
5. **Verify.** Run the `verify` skill and fix problems until everything passes. Never weaken a test to pass.
6. **Review risky areas.** If you changed sqlgen, checks, qa, kpi or mcp, run the `sql-auditor` subagent. If you created a new module without tests, ask the `test-writer` subagent for focused tests.
7. **Update docs in the same commit.** Tick the task in docs/PLAN.md. Add an entry to docs/decisions.md if you made a choice that had real alternatives. Update the commands in CLAUDE.md if they changed.
8. **Commit.** Use the `commit-step` skill, which asks for approval and pushes.
9. **Report.** Tell the owner in plain language what now works, how to try it (a command or URL), and what the next task is.

## Stop and ask when
- The task is ambiguous, or seems to conflict with docs/SPEC.md or a rule.
- The change is growing past about 300 lines. Propose a split into smaller tasks in PLAN.md instead.
- A dependency, an API key or an external service is needed that isn't set up yet.

## End of a milestone
When the last task of a milestone is committed, run the `code-reviewer` subagent on the branch, fix blocking issues as separate commits, then open the pull request through `commit-step`.
