# Project: LinkedIn MCP Server

FastMCP server wrapping the unofficial `linkedin-api` (Voyager) — exposes 55 tools across 13 domains, three MCP prompts, a background scheduler (posts + campaigns), and SQLite storage with daily quotas.

## Stack
- Python 3.10+ (CI matrix: 3.10 / 3.11 / 3.12)
- `mcp[cli]>=1.2` (FastMCP), `linkedin-api>=2.3`
- Pydantic v2 + pydantic-settings, python-dotenv
- SQLite (WAL) at `./data/linkedin_mcp.sqlite`
- APScheduler (posts: 1 min tick, campaigns: 5 min tick)
- httpx, tenacity (retries), rapidfuzz (spam/signal matching), anyio
- Optional: `openai>=1.30` for ICP scoring + message personalization
- Ruff (lint + format, line-length 100, target py310)
- pytest + pytest-asyncio (≈46 tests, all mocked)

## Workflow
- Install dev deps: `make dev` (= `pip install -e ".[dev]"`)
- Run server (stdio, default): `linkedin-mcp`
- Run server (HTTP/SSE): `linkedin-mcp --transport sse --host 0.0.0.0 --port 8765`
- Disable background scheduler: `linkedin-mcp --no-scheduler`
- Tests: `make test` (= `pytest -q`)
- Lint: `make lint` (= `ruff check src tests`)
- Format: `make fmt` (= `ruff format src tests`)
- Docker build: `make docker`
- Admin CLI: `linkedin-mcp-admin {campaigns,prospects,posts,quota,db} ...`

## Architecture rules
- Tools live in `src/linkedin_mcp/tools/<domain>.py`; each module exposes `register(mcp)` and is wired into `server.py`.
- `LinkedInClient` is a thread-safe singleton — get it through the accessor in `client.py`, never instantiate directly.
- All DB access goes through `storage/db.py` (thread-local connection, no ORM); schema changes require editing `storage/schema.sql` with idempotent `CREATE TABLE IF NOT EXISTS`.
- Tools that hit LinkedIn must consume from the daily quota in the `quota` table; check `quota_status` before bulk operations.
- Rate-limit jitter (8–25 s) and the tenacity retry decorator are non-negotiable — never bypass for "just one call".
- Files in `src/linkedin_mcp/agents/` are MCP **prompts** (templates returned to the client), NOT autonomous loops.
- All config comes from `.env` via Pydantic settings — never hardcode credentials, quotas, or endpoints.
- Notifier (`notify.py`) is best-effort — it must never crash the calling tool on network failure.

## Style rules
- Python 3.10+ syntax: `X | Y`, not `Union[X, Y]`; `list[T]`, not `List[T]`.
- Line length 100; enforce via `ruff format` before committing.
- Type hints everywhere; Pydantic models for non-trivial tool inputs/outputs.
- Sync code by default — `httpx` (sync) and `sqlite3` are blocking; use async only where the MCP framework requires it.
- Tool returns must be JSON-serializable (dicts/lists of primitives, or `model_dump()` of pydantic models).
- Errors raise; never silently return `None` on failure unless explicitly documented.
- Default to writing no comments; only add one when the **why** is non-obvious.

## LinkedIn safety rules
- Daily caps: 80 connection requests, 120 DMs, 200 profile views — enforce via `quota_status` before bulk actions.
- Prefer `LINKEDIN_LI_AT` cookie auth; email+password fails challenge-auth headlessly.
- The rapidfuzz spam guard in `bulk_accept_invitations` stays on unless explicitly disabled by the caller.
- Session cookies expire — surface a clear error and stop, do not retry blindly.

## Bug fix protocol
1. State the root cause in one line **before** editing any code (cause, not symptom).
2. If repro is partial or unclear, write a failing test first, then fix.
3. Run all relevant tests after the fix.
4. Propose a generalized rule (about the **class** of error) for the matching section above.
5. If a fix turns out bad, do not patch on top — `/rewind` and redo with the new understanding.

## Self-improvement protocol
- After any user correction, propose **one imperative sentence** in the matching section.
- Search this file first; refine an existing rule rather than duplicating.
- Generalize to the class of error, not the specific incident.
- Flag contradictions before adding — ask which rule to keep.
- If this file passes ~2500 tokens, propose what to consolidate or delete.
- Run `/audit-claude-md` weekly (manual; the `loop` skill can drive it on demand).

## Effort defaults
- Standard work: `xhigh`.
- Hard debugging or architecture decisions: `max` (single session only).
- Trivial edits (typo, rename): `medium`.

## Verification
- Run `/go` before closing any task: lint → tests → simplify → diff summary (no PR unless explicitly asked).
- Minimum bar before declaring done: `make lint && make test`.
- For changes touching transports or tool registration: smoke-test with `linkedin-mcp --transport sse --port 8765` locally and call one tool. Live LinkedIn calls require valid `LINKEDIN_LI_AT` and are out-of-scope for CI.
- Per-user (not committed): `export CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` in your shell to delay auto-compaction.

## Out of bounds
- Never use `--dangerously-skip-permissions`.
- Never push without `make lint && make test` passing.
- Never open a PR unless the user explicitly asks.
- Never commit `.env`, `data/`, or anything matching `*.sqlite*`.
