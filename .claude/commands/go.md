---
description: Close-out workflow — runs lint, tests, and the simplify skill on the diff, then summarizes. Stops on red. Never opens a PR unless I ask explicitly.
---

Close out the current task. Do not skip any step.

## Steps

1. **Lint**: `make lint`. If it fails, print the violations and stop here — fix them yourself in the same run if they're trivial (formatting), otherwise stop and report.

2. **Tests**: `make test`. If anything fails, print the failing test ids + first assertion line and stop — do NOT continue to step 3.

3. **Simplify**: invoke the `simplify` skill on the diff vs the merge-base with `main` (`git diff $(git merge-base HEAD main)..HEAD`). Surface any reuse opportunities, dead code, or CLAUDE.md violations it finds.

4. **Diff summary**: produce a short summary of what changed:
   - Files touched (grouped by area: tools, storage, scheduler, tests, config, docs).
   - Behavioral changes in 3–5 bullets.
   - Anything I should manually verify (live MCP smoke test, schema migration, etc).

5. **PR**: do NOT open a PR. Wait for me to ask explicitly. If I ask, draft the PR body but show it to me for approval before calling the GitHub MCP tools.

## Hard rules

- If lint or tests are red, stop after step 2. Never push, never PR on red.
- Never run `--dangerously-skip-permissions`.
- Never run `linkedin-mcp` against the live LinkedIn API as part of `/go`. Mocked tests are the bar.
