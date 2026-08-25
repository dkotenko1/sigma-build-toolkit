# Sigma Build Toolkit

Reference material for building **Sigma workbooks, pixel-perfect reports and
custom plugins as code** — through `POST /v2/workbooks/spec`,
`POST /v2/reports/spec` and `POST /v2/plugins` — rather than clicking them
together in the UI.

Reports are a separate document kind with their own spec shape: fixed page size,
absolute pixel positioning, header/footer panels, PDF output. Note the `/spec`
endpoints for reports are a **gated beta** — check they're enabled on your org
before designing around them (`skills/sigma-reports/SKILL.md` §0).

Everything here was verified against a live Sigma org. The value is in the parts
the public API reference doesn't tell you: which element kinds the spec endpoint
actually accepts, what shape each one wants, which error messages lie to you, and
the four layout mistakes that render as *nothing at all* with a 200 response.

## Use it

```bash
git clone https://github.com/dkotenko1/sigma-build-toolkit.git
```

Point your coding agent at the folder, or just read it — every file is plain
Markdown and JSON, useful with or without an agent.

**Reading it needs nothing.** The reference, the recipes and the example specs
are all plain text. You only need the setup below if you want to *run* the
scripts — push a spec, export a PNG, resolve a name to an id.

### Running the scripts

Create `.env` in the repo root with your own organization's credentials:

```
SIGMA_BASE_URL=https://aws-api.sigmacomputing.com
SIGMA_CLIENT_ID=<your client id>
SIGMA_CLIENT_SECRET=<your client secret>
```

Generate the client id and secret in Sigma under **Administration → Developer
Access → Create**. The secret is displayed once and cannot be retrieved
afterwards. `.env` is gitignored; no template file ships, because credentials
are per-organization and a committed template is one careless edit away from
being a committed secret.

**`SIGMA_BASE_URL` is the one people get wrong.** Sigma has a different API
host per cloud and region, and credentials are per-organization. Verified
against a live org: a perfectly valid client id and secret sent to the wrong
regional host comes back

```
400 {"message":"Invalid access/refresh token"}
```

which names the *token*, so it reads as a bad secret and sends you off rotating
credentials that were fine. If auth fails, check this table before you touch
your credentials:

| Cloud / region | `SIGMA_BASE_URL` |
|---|---|
| GCP (US) | `https://api.sigmacomputing.com` |
| GCP (KSA) | `https://api.sa.gcp.sigmacomputing.com` |
| AWS US (West) | `https://aws-api.sigmacomputing.com` |
| AWS US (East) | `https://api.us-a.aws.sigmacomputing.com` |
| AWS Canada | `https://api.ca.aws.sigmacomputing.com` |
| AWS Europe | `https://api.eu.aws.sigmacomputing.com` |
| AWS UK | `https://api.uk.aws.sigmacomputing.com` |
| AWS Australia / APAC | `https://api.au.aws.sigmacomputing.com` |
| Azure US | `https://api.us.azure.sigmacomputing.com` |
| Azure Canada | `https://api.ca.azure.sigmacomputing.com` |
| Azure Europe | `https://api.eu.azure.sigmacomputing.com` |
| Azure UK | `https://api.uk.azure.sigmacomputing.com` |
| Azure Australia | `https://api.au.azure.sigmacomputing.com` |

(Sourced from `servers` in Sigma's published OpenAPI — re-check there if your
region is newer than this table.)

Then confirm the whole chain works:

```bash
bash -c 'source scripts/api/_env.sh && bash scripts/api/list-connections.sh'
```

That fetches a token via `scripts/api/get-token.sh`, caches it for 55 minutes,
and lists your connections. If it prints JSON, everything downstream will work.
`scripts/api/_env.sh` must be sourced from **bash, not zsh** — it resolves the
repo root from `$BASH_SOURCE`, which zsh leaves empty.

Python 3 is needed for `validate-spec.py` and `sigma-resolve.py`, both
standard-library only. `validate-openapi.py` additionally wants `jsonschema`;
without it that script prints a notice and exits 0 rather than failing.

## Start here

| If you want to… | Read |
|---|---|
| Build an executive overview / command-center page | `skills/sigma-workbook-conventions/reference/command-center-recipes.md` |
| **Know when the dashboard is actually finished** | `command-center-recipes.md` **§0 — the completeness checklist** |
| Author or debug a workbook spec | `skills/sigma-workbook-conventions/reference/workbook-spec-api.md` |
| Make a workbook look designed, not just correct | `skills/sigma-workbook-styling/SKILL.md` |
| Build a write-back / planning app on input tables | `skills/sigma-input-table-app/SKILL.md` |
| Build a population-segmentation app | `skills/sigma-cohort-builder-app/SKILL.md` |
| Build a custom visualization plugin | `skills/sigma-plugin-development/SKILL.md` |
| Apply a brand to a workbook | `skills/branded-dashboard-format/` |
| **Set up the one shared base table (start here)** | `skills/sigma-workbook-conventions/examples/base-table-snowflake.sql` |
| Catch layout bugs before you POST | `scripts/validate-spec.py` |
| **Catch element-shape bugs before you POST** | `scripts/validate-openapi.py` |
| See what you actually built | `scripts/export-png.sh <workbookId> <pageId>` |
| **Port this to Databricks / BigQuery** | `skills/sigma-workbook-conventions/reference/warehouse-portability.md` |
| Build a statement / invoice / LP report as a PDF | `skills/sigma-reports/SKILL.md` |

## What's in here

**`skills/sigma-workbook-conventions/`** — the core reference.
`reference/command-center-recipes.md` covers the pieces an executive overview
page needs and the per-kind sections don't: the comparative KPI card
(`comparisonColumn` + `comparison`), card sparklines, `progress` rings,
row-scoped card grids via `MaxIf`, data-bound `text` elements, a live warehouse
AI narrative, `region-map` with working cross-filtering, control-driven
dynamic charts, overlays and drill-through, and agent configuration — each with
the trap that makes it render empty. **§0 is the completeness checklist**: what a
finished command center contains, and §12–§18 are the blocks a generated one
usually lacks — a `navigation` masthead with a cross-document CTA, the composite
current+prior KPI card, persona tabs, the per-entity card grid, the operational
alert feed, modal/drawer drill-through, and a time-series breakout chart.
`reference/workbook-spec-api.md` (~1,650 lines) covers verified spec shapes for
every element kind (KPI, bar/line/area/combo, pie/donut, scatter/bubble, pivot,
container, text), series breakout and color-by, the full `controlType` catalog
(`date-range`, `list`, `text`, `number-range`, `segmented`), multi-level table
groupings, cross-element joins with `Lookup()`, formula-namespace resolution,
`[Metrics/<Name>]` references, and a required **visualization clarity** standard.
Also `reference/schema-2026-08-breaking-changes.md` and `reference/naming.md`,
plus four runnable example specs.

**`skills/sigma-workbook-styling/`** — the visual-craft layer: the element
`style` object, theme color tokens, repeated containers, data-URI SVG icons, and
the masthead → cards → detail composition. Three complete example specs to clone
from, including a full styled workbook in `examples/cold-provisions.json`.

**`skills/sigma-plugin-development/`** and **`skills/sigma-plugin-patterns/`** —
the `@sigmacomputing/plugin` SDK end to end: all editor-panel config types,
control variables, action triggers and effects, lifecycle, hosting, plus the
JSON-settings pattern for configuration richer than the editor panel allows.

**`skills/sigma-input-table-app/`** and **`skills/sigma-cohort-builder-app/`** —
verified shapes for interactive data apps: input tables with computed columns,
linked input tables, modals, button actions, control-driven formulas; and the
tabbed-container / agent-tool-per-filter shape for segmentation apps. Each ships
a runnable reference build.

**`skills/branded-dashboard-format/`** — the recurring page composition
(header → filter bar → KPI row → trend → detail) and a fill-in brand-kit
template.

**`scripts/`** — `validate-openapi.py` validates a spec against Sigma's own
published OpenAPI **offline**, element by element. This matters more than it
sounds: the API stops at the *first* bad element and reports it as
`Invalid kind: "<kind>"`, naming the element kind rather than the field that is
actually wrong — so fixing a generated spec costs one network round trip per
mistake. This walks the nested `oneOf` unions, picks the branch matching each
element's `kind`, and prints the real offending field for every element at once.
Needs `jsonschema`; skips itself with a notice if it is missing.
`export-png.sh` renders a workbook page to PNG so you can look
at it; the async export/poll contract is non-obvious and this wraps it, including
the plugin-hangs-forever diagnosis. `validate-spec.py` walks a generated spec and reports the
silent layout failures (unplaced elements, empty containers, legacy tags) plus
the element-shape traps that a 200 response hides — `backgroundImage` buried in
`style`, a bare image `url`, non-`none` padding, a `/` in a referenced column
name, `hidden` input-table columns, the wrong `conditionalFormats` envelope, and
`open-overlay`/`close-overlay` argument mistakes. It also prints advisory
`[completeness]` and `[period-scoping]` lines — the interaction blocks the
dashboard is missing, and any snapshot measure that forgot to scope to the
current half of a two-period base table (the `Sum(x)/12` bug that silently
doubles a scorecard). Point it at one of the bundled `examples/*.json` and it
leads with a `[note]`: those are GET-backs of UI-built workbooks in the older
nested schema, so the flood of findings is the linter reading an old shape
correctly, not the examples being broken. `sigma-resolve.py`
resolves names to IDs. `fetch_logo.py <domain>` pulls a company's own published
logo off their site as a `data:` URI for the header. `api/get-token.sh` exchanges your client credentials for a
bearer token with nothing but curl — no plugin install — and `api/_env.sh`
wraps it with on-disk caching and 401 retry. The rest of `api/*.sh` are small
recipes for listing connections, folders and columns, and publishing a workbook
or data model.

**`plugins/`** — three ready-to-register custom plugins, each a single
self-contained `index.html` with no build step: `comparison-kpi-card` (the
composite current-vs-prior KPI look), `decomposition-tree` (interactive
drill-to-control breakdown), `sigma-motors-demand-pulse` (split-ring volume view
by region). `plugins/HOSTING.md` covers hosting and registration — read the
GitHub-Pages-not-jsDelivr note there before you pick a host.

## Recreating a branded command center with your own data

The composition in most executive dashboards is the same eight moves. Everything
needed for each is in this toolkit:

1. **One base table.** Put every dimension you want to filter on into a single
   source table (custom SQL is fine: `source: {kind: "sql", connectionId, sql}`).
   Cross-filtering works *only* because every element shares that source — adding
   a control does not create a join. A runnable example with the
   current/prior-period split the KPIs need:
   `skills/sigma-workbook-conventions/examples/base-table-snowflake.sql`
   (Databricks variant alongside it). → `command-center-recipes.md` §7
2. **A branded header.** Gradient container via `backgroundImage` with a data-URI
   SVG, your real logo as an `image`, plus `navigation`.
   → `sigma-workbook-styling`, `branded-dashboard-format`
3. **A comparative KPI row.** Current-vs-prior with a delta badge and a
   sparkline, on gradient cards. → `command-center-recipes.md` §1–2
4. **A filter bar and one dynamic chart** driven by `segmented` controls instead
   of four near-identical static charts. → `command-center-recipes.md` §8,
   `workbook-spec-api.md` → control catalog
5. **A ranked detail table plus a card grid** with `progress` rings and
   row-scoped `MaxIf` lookups. → `command-center-recipes.md` §3–5
6. **An AI layer** — a live AI narrative band and an in-workbook agent with
   action tools. → `command-center-recipes.md` §6, §10
7. **The interaction layer** — persona tabs (Executive / Field Operations), a
   per-entity card grid, an operational alert feed, and drill-through into a
   modal and a drawer. This is the half most generated dashboards skip, and it
   is the half a customer reacts to. → `command-center-recipes.md` §14–§17
8. **Grade it before you ship it** against the completeness checklist in
   `command-center-recipes.md` §0. `scripts/validate-spec.py` prints the same
   check as an advisory `[completeness]` line on every run.

A build that stops after move 6 is around **50 elements** and reads as a
competent dashboard; a finished one is around **170** and reads as an
application. The difference is moves 7–8, not more charts.

**Not on Snowflake?** The spec, layout, styling, controls, formulas, plugins
and agents are all warehouse-agnostic. Only two things change: the example
seed SQL and the AI-narrative function name. Both are covered, with
Databricks translations, in
`skills/sigma-workbook-conventions/reference/warehouse-portability.md`.

For a second, interactive page, add a write-back scenario modeler
(`sigma-input-table-app`) or a segmentation builder
(`sigma-cohort-builder-app`). If a visualization has no native equivalent, build
a plugin (`sigma-plugin-development`) — three working ones are in `plugins/`.

Substitute your own connection ID, source tables, palette and logo. Nothing in
this toolkit is tied to a particular dataset.

## Two things worth knowing before you start

**`POST /v2/workbooks/spec/verify` passing means very little.** It skips SQL
resolution, dangling element IDs, duplicate IDs, layout placement, and workspace
feature flags. It has passed while `create` failed on all of those. Always
create or update to validate.

**Four layout mistakes render as nothing at all** — no error, no empty box, no
console warning, with a 200 response. They are documented in
`workbook-spec-api.md` → "The four silent layout failures", and
`scripts/validate-spec.py` catches one of them statically (overlapping
siblings). The workflow that actually finds the rest is: generate → lint → push
→ export a PNG → **look at the image** → fix.

**The layout tags changed in August 2026.** `<GridContainer>`/`<LayoutElement>`
became `<Container>`/`<Element>`, and the old names fail with a *masked* 400 that
never names the tag. `validate-spec.py` flags them; the example specs under
`sigma-workbook-styling/examples/` are pre-change UI round-trips, so read them
for styling and not as POST payloads.

## Scope

This toolkit documents **patterns and verified spec shapes**. It deliberately
does not enumerate Sigma's formula functions — for the function catalogue, date
math, string operations and statistical functions, use
[Sigma's documentation](https://help.sigmacomputing.com). What it does cover
natively: `Lookup`, `Rollup`, `DateLookback`, metric references, cross-element
column references, and the materialize-then-window rule.

For authentication, the Sigma CLI, and data-model authoring, see Sigma's
official skills at
[`sigmacomputing/sigma-agent-skills`](https://github.com/sigmacomputing/sigma-agent-skills).
This toolkit is complementary — it covers the workbook and plugin surfaces those
skills don't yet include.

See [`NOTICE.md`](./NOTICE.md) for provenance, attribution and licensing.
The patterns here were originally written by Connor Miller (Sigma Computing);
this repo is a redacted, reorganised subset of that work.
