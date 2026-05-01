# Deploying LinkedIn MCP behind HTTPS for claude.ai

End-to-end runbook to expose this MCP server as a custom integration that
claude.ai (web) can call directly. Tested on Ubuntu 22.04+ with Caddy.

## Prerequisites

- Ubuntu VPS with a public IP, root/sudo access, ports 80 + 443 open.
- A subdomain you can A-record at the VPS (e.g. `linkedin.yourdomain.com`).
- A claude.ai plan that supports Custom Integrations (Pro / Team / Enterprise).
- A LinkedIn account session — you'll need its `li_at` cookie.

## 1. Get your `li_at` cookie

1. Open <https://www.linkedin.com> in a browser logged in as the target account.
2. DevTools → Application/Storage → Cookies → `https://www.linkedin.com`.
3. Copy the `li_at` value (long string starting with `AQED…`).
4. Optionally copy `JSESSIONID` (keep its surrounding quotes; the code strips them).

Treat this cookie like a password — it has full account access. Do not commit
it, do not paste into chats. It's valid until you sign out of that browser.

## 2. Provision the server

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv git
sudo useradd -r -m -d /opt/linkedin-mcp -s /usr/sbin/nologin linkedin
sudo install -d -o linkedin -g linkedin /opt/linkedin-mcp/data

sudo -u linkedin git clone https://github.com/probuilder10/LinkedIn_MCP \
    /opt/linkedin-mcp/app
sudo -u linkedin git -C /opt/linkedin-mcp/app checkout \
    claude/linkedin-mcp-integration-UHolL
sudo -u linkedin python3.12 -m venv /opt/linkedin-mcp/venv
sudo -u linkedin /opt/linkedin-mcp/venv/bin/pip install -e /opt/linkedin-mcp/app
```

## 3. Configure `.env`

```bash
sudo -u linkedin cp /opt/linkedin-mcp/app/.env.example /opt/linkedin-mcp/app/.env
sudo chmod 600 /opt/linkedin-mcp/app/.env
sudo -u linkedin nano /opt/linkedin-mcp/app/.env
```

Required values:

```
LINKEDIN_LI_AT=<paste from step 1>
LINKEDIN_JSESSIONID="ajax:..."           # optional but recommended
OPENAI_API_KEY=sk-...                    # optional, enables AI drafts
LINKEDIN_MCP_DB=/opt/linkedin-mcp/data/linkedin_mcp.sqlite

# Start conservative — LinkedIn flags sudden activity spikes
MAX_CONNECTION_REQUESTS_PER_DAY=40
MAX_MESSAGES_PER_DAY=60
MAX_PROFILE_VIEWS_PER_DAY=150
```

## 4. Install the systemd unit

```bash
sudo cp /opt/linkedin-mcp/app/deploy/linkedin-mcp.service \
    /etc/systemd/system/linkedin-mcp.service
sudo systemctl daemon-reload
sudo systemctl enable --now linkedin-mcp
sudo systemctl status linkedin-mcp     # expect: active (running)

# port should be alive (405/406 is fine — means MCP is rejecting GET, which it should)
curl -sS -i http://127.0.0.1:8765/mcp | head
```

## 5. Install Caddy + the Bearer-gated reverse proxy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

# Generate a long shared secret — you'll paste this into claude.ai too
TOKEN=$(openssl rand -hex 32) && echo "$TOKEN"

# Edit the Caddyfile: replace the domain and the TOKEN placeholder
sudo cp /opt/linkedin-mcp/app/deploy/Caddyfile /etc/caddy/Caddyfile
sudoedit /etc/caddy/Caddyfile           # set domain + Bearer token

sudo systemctl reload caddy
```

## 6. DNS

Point an `A` record at the VPS:

```
linkedin.yourdomain.com → <VPS IPv4>
```

Verify externally:

```bash
curl -i https://linkedin.yourdomain.com/mcp
# expect: HTTP/2 401 (Caddy rejecting unauthenticated)

curl -i -H "Authorization: Bearer $TOKEN" https://linkedin.yourdomain.com/mcp
# expect: HTTP/2 405 or 406 (MCP server reached, GET not allowed)
```

If you see 502/504, the systemd service isn't running on `:8765`. If you see
401 with the right token, the Caddyfile token mismatch.

## 7. Wire it into claude.ai

1. claude.ai → Settings → **Connectors** (or **Integrations**) → **Add custom integration**.
2. Fill in:
   - **Name**: `LinkedIn`
   - **MCP Server URL**: `https://linkedin.yourdomain.com/mcp`
   - **Auth**: `Custom header`
   - **Header name**: `Authorization`
   - **Header value**: `Bearer <your token>`
3. Save. claude.ai performs a handshake and lists 55 tools + 3 prompts.
4. Open a new chat, enable the `LinkedIn` connector, then prompt:
   > use the linkedin connector and call `whoami`

If `whoami` returns your `publicIdentifier`, the full pipeline is live. If it
fails with auth, your `li_at` is stale — log in again and refresh `.env`.

## 8. First real flow

Try this in chat:

> Use the linkedin connector. Create an ICP `saas_eu_founders` (titles
> Founder/CEO, industry Software Development, geo United Kingdom + Germany +
> Netherlands, keywords SaaS B2B). Then `salesnav_build_list` 30 hits,
> `score_prospect` each, return the top 10 with score > 70 and a one-line
> rationale per prospect. Do not send any messages yet.

After that you can run the `outreach` prompt to launch a campaign with
follow-ups.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `whoami` raises auth error | `li_at` expired or copied with whitespace. Re-grab from browser, update `.env`, `sudo systemctl restart linkedin-mcp`. |
| Random 401s from claude.ai | Token in `Caddyfile` ≠ token in claude.ai. Regenerate both. |
| Random LinkedIn challenges (CAPTCHA) | Slow down. Set `MAX_CONNECTION_REQUESTS_PER_DAY=20`, raise `MIN_ACTION_DELAY_SECONDS=20`. Solve the challenge in your browser, get a fresh `li_at`. |
| Caddy can't get TLS cert | DNS hasn't propagated, or port 80 blocked. `dig linkedin.yourdomain.com`, check firewall. |
| `502 Bad Gateway` | Service down: `sudo systemctl status linkedin-mcp`, check `journalctl -u linkedin-mcp -e`. |

## Rotating credentials

```bash
# new LinkedIn cookie (e.g. after sign-out)
sudoedit /opt/linkedin-mcp/app/.env
sudo systemctl restart linkedin-mcp

# new Bearer token
TOKEN=$(openssl rand -hex 32)
sudoedit /etc/caddy/Caddyfile           # paste new token
sudo systemctl reload caddy
# update the same token in claude.ai → Connectors → LinkedIn → Edit
```

## Optional hardening

- Add fail2ban on `/var/log/caddy/linkedin-mcp.log` to ban repeated 401 abusers.
- Set up a daily SQLite backup:
  ```bash
  sudo crontab -e -u linkedin
  # 0 4 * * * /opt/linkedin-mcp/venv/bin/linkedin-mcp-admin db backup /opt/linkedin-mcp/data/backups
  ```
- Enable `NOTIFY_WEBHOOK_URL` (Slack/Discord) so job-change signals ping you in real time.

## Security notes

- This server has no built-in auth — all gating is at the Caddy layer.
  Never expose `:8765` directly.
- `li_at` is a session token equivalent to a logged-in browser. File mode `600`
  on `.env` is mandatory. Consider a dedicated LinkedIn account for outreach
  rather than your personal one.
- LinkedIn's Terms of Service restrict automation. Conservative quotas are the
  default for a reason — keep them low while you find your operating envelope.
