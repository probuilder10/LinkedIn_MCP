from __future__ import annotations

from typing import Any

from ..client import LinkedInClient


def register(mcp) -> None:
    @mcp.tool()
    def list_invitations(limit: int = 50) -> list[dict[str, Any]]:
        """List pending inbound connection invitations."""
        return LinkedInClient.get().api.get_invitations(start=0, limit=limit)

    @mcp.tool()
    def respond_invitation(
        invitation_entity_urn: str,
        invitation_shared_secret: str,
        action: str = "accept",
    ) -> dict[str, Any]:
        """Accept or reject a pending invitation.

        Both `invitation_entity_urn` and `invitation_shared_secret` come from
        `list_invitations`. `action` is 'accept' or 'reject'.
        """
        if action not in ("accept", "reject"):
            raise ValueError("action must be 'accept' or 'reject'")
        err = LinkedInClient.get().api.reply_invitation(
            invitation_entity_urn=invitation_entity_urn,
            invitation_shared_secret=invitation_shared_secret,
            action=action,
        )
        return {"ok": not err, "action": action}

    @mcp.tool()
    def bulk_accept_invitations(max_count: int = 20, only_first_degree_hints: bool = True) -> dict[str, Any]:
        """Accept up to N pending invitations in one call.

        If `only_first_degree_hints` is true, skip obvious spam heuristics
        (invitations with no shared company/school and no note).
        """
        client = LinkedInClient.get()
        pending = client.api.get_invitations(start=0, limit=max_count * 2)
        accepted: list[str] = []
        skipped: list[dict[str, Any]] = []
        for inv in pending[:max_count]:
            ent = inv.get("entityUrn")
            secret = inv.get("sharedSecret")
            if not (ent and secret):
                skipped.append({"reason": "missing_urn_or_secret", "inv": inv})
                continue
            note = inv.get("customMessage") or inv.get("message")
            insights = inv.get("insights") or inv.get("mutualCurrentCompany") or inv.get("mutualSchool")
            if only_first_degree_hints and not note and not insights:
                skipped.append({"reason": "spammy_heuristic", "urn": ent})
                continue
            err = client.api.reply_invitation(
                invitation_entity_urn=ent,
                invitation_shared_secret=secret,
                action="accept",
            )
            if not err:
                accepted.append(ent)
        return {"accepted": len(accepted), "skipped": len(skipped), "details": skipped[:10]}

    @mcp.tool()
    def follow_company(company_following_state_urn: str, follow: bool = True) -> dict[str, Any]:
        """Follow (or unfollow) a company. Pass the followingState URN from `get_company`."""
        LinkedInClient.get().api.follow_company(company_following_state_urn, following=follow)
        return {"ok": True, "follow": follow, "urn": company_following_state_urn}

    @mcp.tool()
    def unfollow_entity(urn_id: str) -> dict[str, Any]:
        """Unfollow any entity (company, hashtag, member) by URN id."""
        LinkedInClient.get().api.unfollow_entity(urn_id)
        return {"ok": True, "urn": urn_id}

    @mcp.tool()
    def remove_connection(public_id: str) -> dict[str, Any]:
        """Remove a first-degree connection."""
        err = LinkedInClient.get().api.remove_connection(public_profile_id=public_id)
        return {"ok": not err, "public_id": public_id}
