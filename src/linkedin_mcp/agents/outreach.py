def register(mcp) -> None:
    @mcp.prompt()
    def outreach(campaign_name: str, icp_name: str, goal: str) -> str:
        """Activate the Outreach agent: create + run a multi-step campaign."""
        return (
            f"You are the Outreach agent. Goal: {goal}.\n"
            f"1. Ensure a campaign named '{campaign_name}' exists for ICP '{icp_name}' via `create_campaign`. "
            f"Use a personalized connection template and two follow-ups (48h and 120h).\n"
            f"2. Call `list_prospects(icp_name='{icp_name}', min_score=60, status='new', limit=25)`.\n"
            f"3. For each, call `draft_personalized_message(public_id, goal='{goal}')` and review before enrolling.\n"
            f"4. Call `enroll_prospects('{campaign_name}', [...])` and then `start_campaign('{campaign_name}')`.\n"
            f"5. Report back with a summary and the first `campaign_metrics` snapshot."
        )
