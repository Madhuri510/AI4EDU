#!/usr/bin/env bash
set -euo pipefail

: "${BASIC_AUTH_USERNAME:?Set BASIC_AUTH_USERNAME in App Settings}"
: "${BASIC_AUTH_PASSWORD:?Set BASIC_AUTH_PASSWORD in App Settings}"

HTPASSWD_FILE="/etc/nginx/.htpasswd"
mkdir -p "$(dirname "$HTPASSWD_FILE")"

if command -v htpasswd >/dev/null 2>&1; then
  htpasswd -b -c -B "$HTPASSWD_FILE" "$BASIC_AUTH_USERNAME" "$BASIC_AUTH_PASSWORD"
else
  echo "htpasswd not found" >&2
  exit 1
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
