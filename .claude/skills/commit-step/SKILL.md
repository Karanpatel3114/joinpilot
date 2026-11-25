---
name: commit-step
description: Create one small, clearly described commit for the task that was just finished, get the owner's approval, and push it, or open the milestone's pull request when a milestone is complete. Use this whenever a task is done and verified, or when the owner says "commit", "push", "save progress" or "open a PR".
---

# Commit step

The owner wants a GitHub history that shows steady, real progress: one commit per task, pushed as soon as it's made. Follow `.claude/rules/git-commits.md`.

## Steps

1. Confirm the `verify` skill passed for the current changes. If not, run it first.
2. Review `git status` and `git diff`. Make sure every changed file belongs to this task. Make sure nothing forbidden is included: `.env`, `data/generated/`, `*.duckdb`, `node_modules/`, `.venv/`, large binaries or secrets.
3. Stage only this task's files, by path. Never use `git add -A` blindly.
4. Write the message in Conventional Commits format, using the message from docs/PLAN.md unless the work changed:
   ```
   type(scope): short imperative summary

   Why it was needed and what it does, in 1 to 4 plain sentences.

   Task: M<n>.<k>
   ```
   No Co-Authored-By trailers.
5. Show the owner a plain-language summary, the list of files, the verify result and the message. Wait for a clear yes.
6. Commit, then push the branch to origin straight away.
7. Confirm with the short hash and one line about what is now in the history.

## When the milestone is complete
1. Make sure the `code-reviewer` subagent has reviewed the branch and its blocking issues are fixed.
2. Open the pull request with `gh pr create`. Use the milestone name as the title. In the body, list the tasks with their commit hashes, say what changed and how it was tested, and include evaluation numbers if any.
3. After CI passes and the owner approves, merge with a merge commit (`gh pr merge --merge --delete-branch`). Never squash or rebase-merge.
