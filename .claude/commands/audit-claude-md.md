---
description: Audit CLAUDE.md for size, duplicates, contradictions, dead rules, and structure drift. Outputs a proposed diff; never auto-commits.
---

Audit `/home/user/LinkedIn_MCP/CLAUDE.md`. Do not edit it without my approval.

## Steps

1. **Size**: report `wc -w` and an estimated token count (`words * 1.33`). Target band is 2000–2500 tokens. Flag if over.

2. **Duplicates**: find rules that say the same thing in different words. Quote both, propose a single consolidated line.

3. **Contradictions**: find rules that conflict. Show both, ask which to keep — do not pick on my behalf.

4. **Single-incident rules**: flag rules that describe one specific bug or file rather than a class of error. Propose a generalization or removal.

5. **Dead rules**: best-effort scan for rules that no longer match the codebase (e.g., references to files that have been moved/deleted, scripts that no longer exist in `Makefile`, dependencies removed from `pyproject.toml`). Use `git log -S` or `grep` to confirm before flagging.

6. **Structure**: confirm sections exist in this order — Project, Stack, Workflow, Architecture rules, Style rules, LinkedIn safety rules, Bug fix protocol, Self-improvement protocol, Effort defaults, Verification, Out of bounds. Flag any missing or out-of-order section.

7. **Output**: print a unified diff of the proposed changes (use `diff -u` or generate inline). Stop and wait for my approval. Do not write the file or commit.

## Notes

- Never delete a rule without explicit approval, even if it looks dead — it may be load-bearing.
- If you find more than 5 issues, group them by category and present the most impactful 5 first.
