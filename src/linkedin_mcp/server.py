"""LinkedIn MCP server entrypoint."""

from __future__ import annotations

import argparse
import logging
import os

from mcp.server.fastmcp import FastMCP

from .agents import register_all as register_agents
from .config import settings
from .scheduler import start_scheduler
from .tools import register_all as register_tools


def build_server(host: str = "127.0.0.1", port: int = 8765) -> FastMCP:
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
        host=host,
        port=port,
    )
    register_tools(mcp)
    register_agents(mcp)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="linkedin-mcp")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.getenv("LINKEDIN_MCP_TRANSPORT", "stdio"),
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default=os.getenv("LINKEDIN_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LINKEDIN_MCP_PORT", "8765")))
    parser.add_argument(
        "--no-scheduler",
        action="store_true",
        default=os.getenv("LINKEDIN_MCP_NO_SCHEDULER") == "1",
        help="Disable the background post/campaign scheduler",
    )
    args = parser.parse_args()

    mcp = build_server(host=args.host, port=args.port)
    if not args.no_scheduler:
        start_scheduler()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
