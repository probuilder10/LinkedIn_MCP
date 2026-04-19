def register(mcp) -> None:
    @mcp.prompt()
    def signal_watcher(lookback_days: int = 30) -> str:
        """Activate the Signal Watcher agent: surface job-change and hiring signals."""
        return (
            f"You are the Signal Watcher agent.\n"
            f"1. Call `detect_job_changes(lookback_days={lookback_days})` and summarize.\n"
            f"2. For each new company mentioned, call `detect_hiring_signal(company_public_id=...)` "
            f"to check hiring velocity.\n"
            f"3. Propose a prioritized action list (who to reach out to first, with a one-line reason). "
            f"Do NOT send anything yet. End with `list_signals(unprocessed_only=True)` for awareness."
        )
