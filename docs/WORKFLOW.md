# Working on JoinPilot with Claude Code

How the owner works day to day. The goal is a strong product, a readable commit history, and code the owner can explain in any interview.

## Start of a session
1. Open the `joinpilot` folder in VS Code and start Claude Code.
2. First message: `Read CLAUDE.md and docs/PLAN.md, then run /next-task.`

## For each task
1. Read Claude's plain-language explanation and plan. Ask about anything unclear before saying go.
2. Let Claude implement and run `/verify`.
3. Review the diff in VS Code's Source Control panel. Ask "explain this function" or "why this approach?" until you could explain it yourself.
4. Approve the commit. Claude commits with the message from PLAN.md and pushes it.

## End of a milestone
1. Ask: `Use the code-reviewer subagent on this branch.` Fix blocking issues, each as its own commit.
2. If the milestone touched SQL, also ask for the `sql-auditor` subagent.
3. Open the pull request (`/commit-step` handles this), wait for CI, and merge without squashing.
4. Write 5 lines in `docs/notes/<milestone>.md`: what you built, the hardest problem, how you solved it, one number, and one thing you'd change. These become your interview stories.
5. Start the next milestone in a fresh session (`/clear`) so context stays focused.

## When something goes wrong
- Tests fail repeatedly: ask Claude to explain the failure in plain language before fixing it.
- The task feels too big: ask Claude to split it in PLAN.md and commit the plan change first.
- You're unsure about a design choice: ask for 2 or 3 options with trade-offs, then record the choice in docs/decisions.md.

## Keys and accounts (set up as milestones need them)
- Gemini API key (M4), in `.env` as `GEMINI_API_KEY`.
- Langfuse keys (M4.8, optional).
- Neon or Supabase Postgres, Upstash Redis, Render or Hugging Face, and Vercel (M11).
- Supabase Auth (M12).
