from __future__ import annotations

from typing import Any

from ..client import LinkedInClient


def register(mcp) -> None:
    @mcp.tool()
    def list_conversations() -> list[dict[str, Any]]:
        """List inbox conversations with their latest message previews."""
        return LinkedInClient.get().list_conversations()

    @mcp.tool()
    def get_conversation(conversation_urn_id: str) -> dict[str, Any]:
        """Fetch full message thread for a conversation URN id."""
        return LinkedInClient.get().get_conversation(conversation_urn_id)

    @mcp.tool()
    def send_message(
        body: str,
        conversation_urn_id: str | None = None,
        recipient_public_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a LinkedIn direct message.

        Either `conversation_urn_id` (reply into existing thread) or
        `recipient_public_ids` (start a new thread with those people) must be provided.
        """
        if not conversation_urn_id and not recipient_public_ids:
            raise ValueError("provide conversation_urn_id or recipient_public_ids")
        recipients = None
        if recipient_public_ids:
            recipients = [
                f"urn:li:fs_miniProfile:{p}" if not p.startswith("urn:") else p
                for p in recipient_public_ids
            ]
        return LinkedInClient.get().send_message(
            message_body=body,
            conversation_urn_id=conversation_urn_id,
            recipients=recipients,
        )

    @mcp.tool()
    def draft_personalized_message(
        public_id: str, goal: str, tone: str = "friendly, direct, non-salesy"
    ) -> dict[str, Any]:
        """Draft a personalized message for a prospect using their profile.

        Uses OpenAI if OPENAI_API_KEY is configured; otherwise returns a templated draft.
        """
        client = LinkedInClient.get()
        profile = client.get_profile(public_id=public_id)
        name = profile.get("firstName", "there")
        headline = profile.get("headline", "")
        experience = profile.get("experience", [])
        current_role = experience[0] if experience else {}

        from ..config import settings

        if settings.openai_api_key:
            try:
                from openai import OpenAI  # type: ignore

                prompt = (
                    f"Write a short LinkedIn DM (<= 600 chars). Tone: {tone}. Goal: {goal}.\n"
                    f"Recipient: {name}, {headline}. Current role: {current_role.get('title','')} at "
                    f"{current_role.get('companyName','')}.\n"
                    "Reference one specific thing from their profile. No buzzwords. No 'hope this finds you well'."
                )
                oai = OpenAI(api_key=settings.openai_api_key)
                resp = oai.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                return {"body": resp.choices[0].message.content, "source": "openai"}
            except Exception as e:
                return {"body": _fallback_draft(name, headline, goal), "source": f"fallback:{e}"}
        return {"body": _fallback_draft(name, headline, goal), "source": "fallback"}


def _fallback_draft(name: str, headline: str, goal: str) -> str:
    return (
        f"Hi {name} — saw your work on {headline or 'LinkedIn'} and thought you might find this relevant: "
        f"{goal}. Happy to share details if useful. — sent via LinkedIn MCP"
    )
