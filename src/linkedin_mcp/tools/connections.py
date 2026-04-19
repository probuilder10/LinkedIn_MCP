from __future__ import annotations

from typing import Any

from ..client import LinkedInClient


def register(mcp) -> None:
    @mcp.tool()
    def list_connections() -> list[dict[str, Any]]:
        """Return the authenticated user's first-degree connections."""
        return LinkedInClient.get().get_connections()

    @mcp.tool()
    def send_connection_request(public_id: str, message: str = "") -> dict[str, Any]:
        """Send a connection request. Message is optional (max ~300 chars).

        Respects the daily quota configured in .env (MAX_CONNECTION_REQUESTS_PER_DAY).
        """
        if message and len(message) > 300:
            raise ValueError("LinkedIn note limit is 300 characters")
        return LinkedInClient.get().add_connection(public_id, message=message)
