#!/usr/bin/env bash
# LinkedIn MCP — one-shot bootstrap for Ubuntu/Debian.
#
# Phase 1 (no DOMAIN):  installs Python deps, system user, repo, venv, .env stub,
#                       and the systemd unit. Service is enabled but only started
#                       after you fill LINKEDIN_LI_AT.
# Phase 2 (DOMAIN set): also installs Caddy and configures TLS + Bearer-auth in
#                       front of the MCP endpoint. Generates and stores the token
#                       at /opt/linkedin-mcp/.bearer-token.
#
# Re-run anytime — every step is idempotent.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/probuilder10/LinkedIn_MCP/claude/linkedin-mcp-integration-UHolL/deploy/bootstrap.sh | sudo bash
#   # then edit /opt/linkedin-mcp/app/.env to add LINKEDIN_LI_AT
#   sudo systemctl start linkedin-mcp
#   # later, when DNS is ready:
#   sudo DOMAIN=linkedin.yourdomain.com bash /opt/linkedin-mcp/app/deploy/bootstrap.sh

set -euo pipefail

# ---------- config (override via env) ----------
REPO="${REPO:-https://github.com/probuilder10/LinkedIn_MCP}"
BRANCH="${BRANCH:-claude/linkedin-mcp-integration-UHolL}"
USER_NAME="${USER_NAME:-linkedin}"
ROOT_DIR="${ROOT_DIR:-/opt/linkedin-mcp}"
APP_DIR="$ROOT_DIR/app"
VENV_DIR="$ROOT_DIR/venv"
DATA_DIR="$ROOT_DIR/data"
PORT="${PORT:-8765}"
DOMAIN="${DOMAIN:-}"
TOKEN_FILE="$ROOT_DIR/.bearer-token"

# ---------- helpers ----------
log()  { printf '\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || err "Run with sudo: 'curl … | sudo bash' or 'sudo bash bootstrap.sh'"
command -v apt-get >/dev/null || err "Ubuntu/Debian only (no apt-get found)."

# ---------- phase 0: apt deps + python ----------
export DEBIAN_FRONTEND=noninteractive
log "Updating apt cache..."
apt-get update -qq

log "Installing base packages..."
apt-get install -y -qq git curl openssl ca-certificates gnupg python3 python3-venv >/dev/null

# Pick the newest python3.x available
PYTHON=""
for v in python3.12 python3.11 python3.10 python3; do
    if command -v "$v" >/dev/null; then PYTHON="$(command -v "$v")"; break; fi
done
[[ -n "$PYTHON" ]] || err "No python3 found."
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)' \
    || err "Need Python ≥3.10. Detected: $($PYTHON -V 2>&1)"

# Make sure the matching -venv package is present (e.g. python3.12-venv on 24.04)
PY_BASENAME="$(basename "$PYTHON")"
if [[ "$PY_BASENAME" != "python3" ]]; then
    apt-get install -y -qq "${PY_BASENAME}-venv" >/dev/null 2>&1 || true
fi
log "Using $PYTHON ($($PYTHON -V 2>&1))"

# ---------- phase 1: user + dirs ----------
if ! id "$USER_NAME" &>/dev/null; then
    log "Creating system user '$USER_NAME'..."
    useradd -r -m -d "$ROOT_DIR" -s /usr/sbin/nologin "$USER_NAME"
fi
install -d -m 750 -o "$USER_NAME" -g "$USER_NAME" "$ROOT_DIR" "$DATA_DIR"

# ---------- phase 2: code ----------
if [[ -d "$APP_DIR/.git" ]]; then
    log "Updating repo on '$BRANCH'..."
    sudo -u "$USER_NAME" git -C "$APP_DIR" fetch --quiet origin
    sudo -u "$USER_NAME" git -C "$APP_DIR" checkout --quiet "$BRANCH"
    sudo -u "$USER_NAME" git -C "$APP_DIR" pull --quiet --ff-only origin "$BRANCH"
else
    log "Cloning $REPO ($BRANCH)..."
    sudo -u "$USER_NAME" git clone --quiet --branch "$BRANCH" "$REPO" "$APP_DIR"
fi

# ---------- phase 3: venv + install ----------
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "Creating venv..."
    sudo -u "$USER_NAME" "$PYTHON" -m venv "$VENV_DIR"
fi
log "Installing/upgrading linkedin-mcp into venv..."
sudo -u "$USER_NAME" "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo -u "$USER_NAME" "$VENV_DIR/bin/pip" install --quiet -e "$APP_DIR"

# ---------- phase 4: .env ----------
ENV_FILE="$APP_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    log "Creating $ENV_FILE from template (you'll need to edit it)..."
    sudo -u "$USER_NAME" cp "$APP_DIR/.env.example" "$ENV_FILE"
    sudo -u "$USER_NAME" sed -i \
        "s|^LINKEDIN_MCP_DB=.*|LINKEDIN_MCP_DB=$DATA_DIR/linkedin_mcp.sqlite|" \
        "$ENV_FILE"
fi
chown "$USER_NAME:$USER_NAME" "$ENV_FILE"
chmod 600 "$ENV_FILE"

# Detect whether li_at is filled
HAS_COOKIE=0
if grep -Eq '^LINKEDIN_LI_AT=.+' "$ENV_FILE"; then HAS_COOKIE=1; fi

# ---------- phase 5: systemd ----------
log "Installing systemd unit..."
install -m 644 "$APP_DIR/deploy/linkedin-mcp.service" \
    /etc/systemd/system/linkedin-mcp.service
systemctl daemon-reload
systemctl enable linkedin-mcp >/dev/null 2>&1 || true

if [[ "$HAS_COOKIE" -eq 1 ]]; then
    log "Restarting linkedin-mcp..."
    systemctl restart linkedin-mcp
    sleep 2
    if systemctl is-active --quiet linkedin-mcp; then
        log "linkedin-mcp is active."
    else
        warn "linkedin-mcp did not start. Diagnose with: journalctl -u linkedin-mcp -n 80 --no-pager"
    fi
else
    warn "LINKEDIN_LI_AT is empty — service is enabled but NOT started yet."
fi

# ---------- phase 6: Caddy (optional) ----------
if [[ -n "$DOMAIN" ]]; then
    log "Phase 2 — exposing $DOMAIN with Caddy + Bearer auth"

    if ! command -v caddy >/dev/null; then
        log "Installing Caddy..."
        apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https >/dev/null
        install -d -m 755 /usr/share/keyrings
        if [[ ! -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg ]]; then
            curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
                | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        fi
        if [[ ! -f /etc/apt/sources.list.d/caddy-stable.list ]]; then
            curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
                > /etc/apt/sources.list.d/caddy-stable.list
        fi
        apt-get update -qq
        apt-get install -y -qq caddy >/dev/null
    fi

    if [[ ! -s "$TOKEN_FILE" ]]; then
        TOKEN="$(openssl rand -hex 32)"
        umask 077
        printf '%s\n' "$TOKEN" > "$TOKEN_FILE"
        chown "$USER_NAME:$USER_NAME" "$TOKEN_FILE"
        chmod 600 "$TOKEN_FILE"
    else
        TOKEN="$(cat "$TOKEN_FILE")"
        log "Reusing existing Bearer token at $TOKEN_FILE"
    fi

    log "Writing /etc/caddy/Caddyfile for $DOMAIN..."
    install -d -m 755 /etc/caddy /var/log/caddy
    chown -R caddy:caddy /var/log/caddy 2>/dev/null || true

    cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    @authorized header Authorization "Bearer $TOKEN"

    handle @authorized {
        reverse_proxy 127.0.0.1:$PORT {
            flush_interval -1
            transport http {
                read_timeout 0
                write_timeout 0
            }
        }
    }

    handle {
        respond "Unauthorized" 401
    }

    encode zstd gzip

    log {
        output file /var/log/caddy/linkedin-mcp.log
        format json
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "no-referrer"
        -Server
    }
}
EOF

    systemctl enable caddy >/dev/null 2>&1 || true
    systemctl reload caddy 2>/dev/null || systemctl restart caddy
    log "Caddy is configured. Will auto-issue TLS once DNS resolves to this host."
fi

# ---------- summary ----------
echo
echo "========================================================================"
echo " Bootstrap complete."
echo "========================================================================"
echo
echo " Repo:    $APP_DIR  (branch: $BRANCH)"
echo " venv:    $VENV_DIR"
echo " env:     $ENV_FILE  (chmod 600, owner $USER_NAME)"
echo " data:    $DATA_DIR"
echo " service: linkedin-mcp.service  (binds 127.0.0.1:$PORT)"
echo

if [[ "$HAS_COOKIE" -eq 0 ]]; then
    cat <<EOF
 NEXT STEP — paste your LinkedIn cookie:
   sudo nano $ENV_FILE        # set LINKEDIN_LI_AT (and JSESSIONID if you have it)
   sudo systemctl start linkedin-mcp
   sudo systemctl status linkedin-mcp

 (Get li_at from https://www.linkedin.com → DevTools → Application → Cookies)
EOF
fi

if [[ -z "$DOMAIN" ]]; then
    cat <<EOF

 When DNS for your subdomain is pointed at this VPS, expose it publicly:
   sudo DOMAIN=linkedin.yourdomain.com bash $APP_DIR/deploy/bootstrap.sh
EOF
else
    cat <<EOF

 Public endpoint:  https://$DOMAIN/mcp
 Bearer token:     $TOKEN
                   (saved at $TOKEN_FILE, chmod 600)

 Add to claude.ai → Settings → Connectors → Add custom integration:
   URL              https://$DOMAIN/mcp
   Auth             Custom header
   Header name      Authorization
   Header value     Bearer $TOKEN

 Verify externally:
   curl -i https://$DOMAIN/mcp                                   # expect 401
   curl -i -H 'Authorization: Bearer $TOKEN' https://$DOMAIN/mcp # expect 405/406
EOF
fi

cat <<'EOF'

 Useful commands:
   sudo systemctl status linkedin-mcp
   sudo journalctl -u linkedin-mcp -f
   sudo -u linkedin /opt/linkedin-mcp/venv/bin/linkedin-mcp-admin quota
   sudo -u linkedin /opt/linkedin-mcp/venv/bin/linkedin-mcp-admin db backup /opt/linkedin-mcp/data/backups
EOF
