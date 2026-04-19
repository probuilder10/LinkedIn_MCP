"""LinkedIn MCP server entrypoint."""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from .agents import register_all as register_agents
from .config import settings
from .scheduler import start_scheduler
from .tools import register_all as register_tools


def build_server() -> FastMCP:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp = FastMCP(
        name="linkedin-mcp",
        instructions=(
            "LinkedIn MCP: prospecting, outreach, posts, signals, ICP scoring, campaigns. "
            "All actions respect the daily quotas from .env. Start with `whoami`, then `list_icps`."
        ),
    )
    register_tools(mcp)
    register_agents(mcp)
    return mcp


def main() -> None:
    mcp = build_server()
    if os.getenv("LINKEDIN_MCP_NO_SCHEDULER") != "1":
        start_scheduler()
    mcp.run()  # stdio transport by default


if __name__ == "__main__":
    main()
