def register(mcp) -> None:
    @mcp.prompt()
    def prospector(icp_name: str, max_prospects: int = 50) -> str:
        """Activate the Prospector agent: build a ranked lead list for an ICP."""
        return (
            f"You are the Prospector agent. Using the LinkedIn MCP tools, do the following:\n"
            f"1. Call `list_icps` and pick the ICP named '{icp_name}'.\n"
            f"2. Translate its titles/seniorities/industries/geographies into a `salesnav_build_list` call, "
            f"limit={max_prospects}.\n"
            f"3. For each hit, call `score_prospect(public_id, icp_name='{icp_name}')`.\n"
            f"4. Return the top 20 prospects sorted by score with a one-line rationale each.\n"
            f"5. Do NOT send any messages or connection requests."
        )
