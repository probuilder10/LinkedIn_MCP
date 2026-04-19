# Quickstart — end-to-end flow

This walks through the exact sequence of MCP tool calls that reproduces Zevari's
"prospect → enrich → personalize → connect → follow up → measure" flow.

## 1. Define your ICP

```
create_icp(
  name="saas_founders_us",
  description="US-based seed/Series A SaaS founders",
  titles=["Founder","CEO","Co-Founder"],
  seniorities=["founder","c-level"],
  industries=["Software Development","Computer Software"],
  company_sizes=["B","C"],
  geographies=["United States"],
  keywords=["SaaS","B2B","product-led"]
)
```

## 2. Build a lead list

```
salesnav_build_list(
  titles=["Founder","CEO"],
  seniority="founder",
  industries=["Software Development"],
  company_keywords=["SaaS"],
  limit=50
)
```

## 3. Score prospects against the ICP

For each `public_id` returned above:

```
score_prospect(public_id="<public_id>", icp_name="saas_founders_us")
```

Then cut to the top tier:

```
list_prospects(icp_name="saas_founders_us", min_score=70, status="new", limit=25)
```

## 4. Draft personalized openers

```
draft_personalized_message(
  public_id="<public_id>",
  goal="introduce our AI revenue-ops product and book a 15-min call"
)
```

## 5. Create and launch a campaign

```
create_campaign(
  name="ro_saas_apr",
  icp_name="saas_founders_us",
  connection_template="Hi {name} — saw your work on <x>, would love to connect.",
  followup_templates=[
    {"delay_hours": 48, "body": "Hi {name}, thanks for connecting. Thought you'd like <...>"},
    {"delay_hours": 120, "body": "Hi {name}, last nudge — worth a 15-min chat?"}
  ]
)

enroll_prospects(campaign_name="ro_saas_apr", public_ids=[...])
start_campaign(name="ro_saas_apr")
```

The background scheduler ticks every 5 minutes; you can also force a tick:

```
run_campaign_tick(name="ro_saas_apr", max_actions=10)
```

## 6. Watch for intent signals

```
detect_job_changes(lookback_days=30)
list_signals(kind="job_change", unprocessed_only=true)
```

## 7. Measure

```
campaign_metrics(name="ro_saas_apr")
quota_status()
```

## 8. Content

```
publish_post(text="Shipping something new today: ...")
schedule_post(text="Deep-dive coming Thursday...", run_at_iso="2026-04-24T14:00:00+00:00")
list_scheduled_posts(status="scheduled")
```
