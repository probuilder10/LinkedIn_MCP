# LinkedIn MCP

A self-hosted Model Context Protocol server that gives Claude (or any
MCP-compatible client) a full set of LinkedIn superpowers: search, scoring,
messaging, multi-step outreach campaigns, scheduled posts, and intent signals.

It implements the same tool surface a commercial product like Zevari exposes, in
open source, running on your own machine against your own account.

> **Read this first.** LinkedIn's User Agreement restricts automated access.
> This repo is provided for educational and personal productivity use. You are
> responsible for how you use it — conservative daily caps are on by default
> and should stay there.

## Features

- **People & companies**: `search_people`, `get_profile`, `get_profile_contact_info`, `search_companies`, `get_company`, `search_jobs`.
- **Sales-Nav-style lists**: `salesnav_build_list`, `salesnav_account_list` — natural-language filters (titles, seniority, industries, geo, company keywords).
- **Connections**: `list_connections`, `send_connection_request` (with optional note, respects daily cap).
- **Messaging**: `list_conversations`, `get_conversation`, `send_message`, `draft_personalized_message` (LLM-backed if `OPENAI_API_KEY` is set).
- **Posts**: `publish_post`, `schedule_post`, `list_scheduled_posts`, `cancel_scheduled_post`.
- **ICP scoring**: `create_icp`, `list_icps`, `score_prospect`, `list_prospects`, `enrich_company`.
- **Campaigns**: `create_campaign`, `enroll_prospects`, `start_campaign`, `pause_campaign`, `run_campaign_tick`, `campaign_metrics`, `list_campaigns`.
- **Signals**: `detect_job_changes`, `detect_hiring_signal`, `list_signals`, `mark_signal_processed`.
- **Safety**: `whoami`, `quota_status`, daily caps with jittered delays.
- **Pre-built agents** as MCP prompts: `prospector`, `outreach`, `signal_watcher`.

## Architecture

```
                ┌─────────────────────────┐
                │        MCP client        │  (Claude Desktop, Claude Code, etc.)
                └──────────┬──────────────┘
                           │ stdio / JSON-RPC
                ┌──────────▼──────────────┐
                │    FastMCP server       │   src/linkedin_mcp/server.py
                │  tools + prompts        │
                └──────┬──────────┬───────┘
                       │          │
            ┌──────────▼──┐   ┌───▼─────────────┐
            │ LinkedIn    │   │ APScheduler     │   scheduler.py
            │ client      │   │  - posts/1 min  │
            │ (Voyager)   │   │  - campaigns/5  │
            └─────┬───────┘   └───────┬─────────┘
                  │                   │
          ┌───────▼───────┐   ┌───────▼────────┐
          │ linkedin-api  │   │ SQLite (WAL)   │  data/linkedin_mcp.sqlite
          │ (unofficial)  │   │ ICPs/prospects │
          └───────────────┘   │ campaigns/etc. │
                              └────────────────┘
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
# edit .env — paste your `li_at` cookie from your browser (safer than password)
linkedin-mcp    # stdio server; run via an MCP client, not directly
```

Or with Docker:

```bash
docker compose build
docker compose run --rm linkedin-mcp
```

## Connect to Claude Desktop

Copy `examples/claude_desktop_config.json` into your Claude Desktop config
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS) and
restart Claude.

## Getting `li_at`

1. Open `linkedin.com` in a browser where you're logged in.
2. DevTools → Application → Cookies → `https://www.linkedin.com` → copy `li_at`.
3. Paste into `.env` as `LINKEDIN_LI_AT`.

Rotate occasionally; never commit it.

## End-to-end flow

See [`examples/quickstart.md`](examples/quickstart.md) for the full prospect →
score → enroll → campaign → measure sequence.

## Daily caps

Defaults are conservative (80 connection requests, 120 DMs, 200 profile views).
Quotas reset at UTC midnight and are tracked in SQLite. Change them in `.env`
if you understand the risk.

## Project layout

```
src/linkedin_mcp/
  server.py               # FastMCP entry
  client.py               # Voyager wrapper + rate limiting
  config.py               # pydantic-settings
  scheduler.py            # APScheduler background jobs
  storage/db.py           # SQLite connection + schema
  storage/schema.sql
  tools/                  # MCP tools, one module per domain
    profiles.py companies.py connections.py messaging.py posts.py
    sales_nav.py signals.py scoring.py campaigns.py health.py
  agents/                 # MCP prompts
    prospector.py outreach.py signal_watcher.py
```

## License

MIT
