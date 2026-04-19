"""High-level agent prompts + helpers registered as MCP prompts.

These aren't autonomous loops; they are prompt templates that wire the tools
together so Claude (or any MCP client) can "activate an agent" in one call.
"""

from . import outreach, prospector, signal_watcher


def register_all(mcp) -> None:
    prospector.register(mcp)
    outreach.register(mcp)
    signal_watcher.register(mcp)
