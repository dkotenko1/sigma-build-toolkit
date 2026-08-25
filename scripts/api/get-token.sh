#!/usr/bin/env bash
# Exchange Sigma API client credentials for a bearer token. Self-contained —
# no plugin, no marketplace install, nothing but curl.
#
# `scripts/api/_env.sh` calls this and evals its stdout, so the ONLY thing this
# prints on success is a single `export SIGMA_API_TOKEN='...'` line. Diagnostics
# go to stderr, or they would be eval'd as shell.
#
# Usage:
#   eval "$(scripts/api/get-token.sh)"          # sets SIGMA_API_TOKEN
#   SIGMA_API_TOKEN=$(scripts/api/get-token.sh --raw)
#
# Reads SIGMA_BASE_URL / SIGMA_CLIENT_ID / SIGMA_CLIENT_SECRET from the
# environment, falling back to .env via scripts/load-env.sh.
#
# Create credentials in Sigma: Administration → Developer Access → Create.
# The client id and secret are shown ONCE — the secret cannot be retrieved later.
# The token is valid for one hour; _env.sh caches it and refreshes at 55 minutes.
set -euo pipefail

RAW=false
[ "${1:-}" = "--raw" ] && RAW=true

_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Load .env for anything missing, but do NOT let it clobber a value the caller
# explicitly exported. load-env.sh emits `export VAR=...` for every line in the
# file, so a bare eval silently overrides an intentional
# `SIGMA_BASE_URL=... get-token.sh` — which makes pointing at a second org look
# like it worked while it quietly authenticated against the one in .env.
if [ -z "${SIGMA_BASE_URL:-}" ] || [ -z "${SIGMA_CLIENT_ID:-}" ] || [ -z "${SIGMA_CLIENT_SECRET:-}" ]; then
  _pre_url="${SIGMA_BASE_URL:-}"; _pre_id="${SIGMA_CLIENT_ID:-}"; _pre_secret="${SIGMA_CLIENT_SECRET:-}"
  eval "$("${_repo_root}/scripts/load-env.sh")"
  [ -n "$_pre_url" ]    && SIGMA_BASE_URL="$_pre_url"
  [ -n "$_pre_id" ]     && SIGMA_CLIENT_ID="$_pre_id"
  [ -n "$_pre_secret" ] && SIGMA_CLIENT_SECRET="$_pre_secret"
  unset _pre_url _pre_id _pre_secret
fi

for v in SIGMA_BASE_URL SIGMA_CLIENT_ID SIGMA_CLIENT_SECRET; do
  if [ -z "${!v:-}" ]; then
    echo "get-token.sh: $v is not set. See the prerequisites section of README.md." >&2
    exit 1
  fi
done

# --data-urlencode, not --data: a client secret can contain +, & or = and any of
# those silently corrupts a raw form body, producing a 401 that looks like bad
# credentials rather than bad encoding.
_resp=$(curl -sS -X POST "${SIGMA_BASE_URL%/}/v2/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=${SIGMA_CLIENT_ID}" \
  --data-urlencode "client_secret=${SIGMA_CLIENT_SECRET}" \
  -w '\nHTTP_STATUS:%{http_code}')

_status="${_resp##*HTTP_STATUS:}"
_body="${_resp%HTTP_STATUS:*}"

if [ "$_status" -ge 400 ]; then
  echo "get-token.sh: token request failed (HTTP $_status)." >&2
  echo "  base url: $SIGMA_BASE_URL" >&2
  echo "  $_body" >&2
  # The overwhelmingly common cause is the wrong regional host: credentials are
  # per-organization and every cloud has its own API hostname. Verified against
  # a live org: a VALID id/secret sent to the wrong regional host comes back
  # `400 {"message":"Invalid access/refresh token"}` — which names the token, so
  # it reads as a bad secret and sends you off rotating credentials that were
  # fine. Hint on 400 as well as 401 for exactly that reason.
  case "$_status" in
    400|401) echo "  Check SIGMA_BASE_URL first: the wrong regional host rejects VALID credentials with this exact error. Host table in README.md." >&2 ;;
  esac
  exit 1
fi

_token=$(printf '%s' "$_body" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' 2>/dev/null || true)

if [ -z "$_token" ]; then
  echo "get-token.sh: no access_token in the response body." >&2
  echo "  $_body" >&2
  exit 1
fi

if $RAW; then
  printf '%s\n' "$_token"
else
  printf "export SIGMA_API_TOKEN='%s'\n" "$_token"
fi
