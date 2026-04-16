"""MultiText configuration — DB credentials, send settings, SSH tunnel."""

# ── SSH tunnel to Digital Ocean ──────────────────────────────────
SSH_HOST = "64.227.108.128"
SSH_USER = "root"
# Uses your default SSH key (~/.ssh/id_ed25519 or id_rsa)

# ── MySQL (remote, accessed through tunnel) ─────────────────────
DB_HOST = "127.0.0.1"  # local end of SSH tunnel
DB_USER = "mcallpl"
DB_PASS = "amazing123"
DB_NAME = "propertypulse"

# ── Send engine defaults ────────────────────────────────────────
DELAY_MIN = 20          # seconds between messages (minimum)
DELAY_MAX = 35          # seconds between messages (maximum)
DAILY_CAP = 50          # max messages per DAY (spread large sends across multiple days)
SEND_HOUR_START = 9     # earliest hour to send (24h)
SEND_HOUR_END = 20      # latest hour to send (24h)
COOLDOWN_DAYS = 30      # don't re-send same template to same person within this window

# ── Flask ────────────────────────────────────────────────────────
SECRET_KEY = "multitext-local-dev-key"
