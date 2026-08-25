# The OpenAPI spec is the source of truth

Sigma publishes its entire public REST API as machine-readable JSON, generated
from their own code:

```
https://assets.sigmacomputing.com/openapi/public-rest-api/sigma-computing-public-rest-api.json
```

**Query that, not the tables in this repo.** Every hardcoded shape here — including
the element-kind tables and per-kind examples — is a snapshot that rots between
Sigma releases. When this repo and the OpenAPI disagree, the OpenAPI is right and
this repo is stale.

## Fetch and query it

```bash
curl -s https://assets.sigmacomputing.com/openapi/public-rest-api/sigma-computing-public-rest-api.json -o /tmp/sigma-openapi.json
```

List the element kinds the workbook spec actually accepts:

```bash
jq -r '[.. | objects | select(.properties.kind?) | .properties.kind.enum // empty] | flatten | unique | .[]' /tmp/sigma-openapi.json
```

Get the full schema for one element kind:

```bash
jq '.components.schemas | to_entries[] | select(.key | test("kpi";"i")) | .key' /tmp/sigma-openapi.json
jq '.components.schemas["<SchemaName>"]' /tmp/sigma-openapi.json
```

Find the endpoints for a resource:

```bash
jq -r '.paths | keys[] | select(test("workbook"))' /tmp/sigma-openapi.json
jq '.paths["/v2/workbooks/{workbookId}/spec"] | keys' /tmp/sigma-openapi.json
```

Check whether a field you are about to send is real:

```bash
jq -r '[.. | objects | select(has("properties")) | .properties | keys[]] | unique | .[]' /tmp/sigma-openapi.json | grep -i comparison
```

`scripts/refresh-vendor.sh` in this toolkit automates the download step.

## What the OpenAPI will *not* tell you

This is why the rest of this reference exists. The OpenAPI is authoritative about
**shape** and silent about **behaviour**:

- Which accepted fields are UI-only and get silently rewritten on a round-trip.
- Which error messages are misleading (an unrecognised *field* surfaces as
  `Invalid kind: "<kind>"`, naming the wrong thing entirely).
- The four layout mistakes that return 200 and render nothing at all.
- Which enum values are accepted at POST but rejected at runtime.
- That `verify` passing means very little.

So: use the OpenAPI to confirm a field exists and what type it takes, and use
this reference for what happens when you actually send it. When the two conflict
on shape, trust the OpenAPI and please correct this repo.

## If an agent is doing the lookup

Sigma also exposes its documentation and endpoint index through an MCP
integration, which avoids the download entirely — search for a function or
endpoint by name and fetch the page. Prefer a lookup round-trip over recalling a
signature from training data: Sigma's function semantics (argument order on
`Rollup`, `DateLookback`, `DateAdd`) are easy to misremember, and the cost of a
malformed formula is a silent `NULL` in the generated SQL, not a POST error.
