#!/usr/bin/env bash
# Export a workbook page as PNG so you can LOOK at it.
#
# Four of the layout failures documented in
# skills/sigma-workbook-conventions/reference/workbook-spec-api.md are invisible
# in the spec and obvious in a screenshot. This is the tool that closes that
# loop: generate -> lint -> push -> export -> look -> fix.
#
# Usage:
#   ./scripts/export-png.sh <workbookId> [pageId] [outfile]
#   ./scripts/export-png.sh 1a2b3c4d page-overview shots/overview.png
#
# Omit pageId to export the whole document (first/default page).
# Requires SIGMA_BASE_URL and SIGMA_API_TOKEN — source scripts/api/_env.sh first.
# Source it from BASH, not zsh: _env.sh resolves the repo root from $BASH_SOURCE,
# which is empty under zsh, so it looks for .env in the wrong directory and the
# token never loads. `bash -c 'source scripts/api/_env.sh && ./scripts/export-png.sh …'`
#
# The export is ASYNC and the polling contract is not obvious:
#   POST {base}/v2/workbooks/{id}/export  {"format":{"type":"png"}}  -> queryId
#   GET  {base}/v2/query/{queryId}/download                          -> bytes
# Poll the *query* download path, NOT /v2/workbooks/.../export/{queryId}.
# A zero-byte 200 means "not ready yet", not "failed" — sleep and retry.
set -euo pipefail

WB="${1:?usage: export-png.sh <workbookId> [pageId] [outfile]}"
PAGE="${2:-}"
OUT="${3:-export.png}"

: "${SIGMA_BASE_URL:?set SIGMA_BASE_URL (e.g. https://aws-api.sigmacomputing.com)}"
: "${SIGMA_API_TOKEN:?set SIGMA_API_TOKEN — see scripts/api/_env.sh}"

MAX_WAIT="${MAX_WAIT:-180}"   # seconds; a plugin-heavy page is slow
POLL="${POLL:-3}"

if [ -n "$PAGE" ]; then
  BODY=$(printf '{"format":{"type":"png"},"pageId":"%s"}' "$PAGE")
else
  BODY='{"format":{"type":"png"}}'
fi

echo "starting export: workbook=$WB page=${PAGE:-<default>}" >&2
QID=$(curl -sS -X POST "$SIGMA_BASE_URL/v2/workbooks/$WB/export" \
        -H "Authorization: Bearer $SIGMA_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$BODY" \
      | python3 -c 'import sys,json; print(json.load(sys.stdin).get("queryId",""))')

[ -n "$QID" ] || { echo "export did not return a queryId" >&2; exit 1; }
echo "queryId=$QID — polling (a zero-byte 200 just means not ready)" >&2

waited=0
while [ "$waited" -lt "$MAX_WAIT" ]; do
  code=$(curl -sS -o "$OUT.part" -w '%{http_code}' \
           -H "Authorization: Bearer $SIGMA_API_TOKEN" -H 'Accept: */*' \
           "$SIGMA_BASE_URL/v2/query/$QID/download")
  size=$(wc -c < "$OUT.part" | tr -d ' ')
  if [ "$code" = "200" ] && [ "$size" -gt 1000 ]; then
    mv "$OUT.part" "$OUT"
    echo "wrote $OUT ($size bytes)" >&2
    exit 0
  fi
  sleep "$POLL"; waited=$(( waited + POLL ))
  printf '.' >&2
done

rm -f "$OUT.part"
cat >&2 <<'MSG'

TIMED OUT.

The most common cause is a plugin on the page that never reaches idle. The
renderer waits for the page to go quiet, so either of these hangs it forever:

  * a plugin with an infinite animation loop (bound your animations)
  * a plugin served with the wrong Content-Type — a jsDelivr .html URL is
    served as text/plain and hangs export indefinitely (see plugins/HOSTING.md)
  * a plugin whose HOST IS UNREACHABLE from the renderer — the usual case is a
    plugin registered against http://localhost:PORT while nothing is listening
    on that port. This is why exporting somebody else's old workbook hangs on
    your machine: their dev server is not running here.

To confirm it is the plugin and not your spec: clone the workbook, replace each
plugin element with an inert text tile of the same id, and export the clone. If
that succeeds, the plugin is the problem, not the layout. Keep that stub swap in
the generator behind a flag — the reference builds render their screenshots with
"<plugin id> (stubbed for render)" tiles so the export loop never depends on a
dev server being up.
MSG
exit 1
