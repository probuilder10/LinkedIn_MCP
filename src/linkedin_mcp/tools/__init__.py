"""All MCP tool implementations. Each module exposes `register(mcp)`."""

from . import (
    campaigns,
    companies,
    connections,
    engagement,
    health,
    inbox,
    invitations,
    messaging,
    posts,
    profiles,
    sales_nav,
    scoring,
    signals,
)

ALL_MODULES = [
    profiles,
    companies,
    connections,
    invitations,
    messaging,
    inbox,
    posts,
    engagement,
    sales_nav,
    signals,
    scoring,
    campaigns,
    health,
]


def register_all(mcp) -> None:
    for m in ALL_MODULES:
        m.register(mcp)
