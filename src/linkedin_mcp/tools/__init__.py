"""All MCP tool implementations. Each module exposes `register(mcp)`."""

from . import companies, connections, messaging, posts, profiles, sales_nav, scoring, signals, campaigns, health

ALL_MODULES = [profiles, companies, connections, messaging, posts, sales_nav, signals, scoring, campaigns, health]


def register_all(mcp) -> None:
    for m in ALL_MODULES:
        m.register(mcp)
