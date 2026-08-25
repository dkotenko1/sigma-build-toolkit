# Styled workbook examples

Reference specs for `sigma-workbook-styling`. Treat them as immutable — clone the
blocks you need, don't edit in place.

| File | Pages | Elements | Why it's here |
|---|---|---|---|
| `cold-provisions.json` | 16 | 601 | The deepest reference in the bundle. Heavy use of `container` (135) and `text` (148) to build card grids and section furniture, 73 KPI charts, 20 input tables, 16 dividers, 22 images. Go here for how a genuinely app-like workbook is composed. |
| `marketing-control-center.json` | 12 | 132 | A control-heavy command centre — 27 controls against 15 KPIs and 8 input tables. The reference for filter clusters and control-driven layout. |
| `demand-planning.json` | 3 | 50 | The smallest and easiest to read end to end. A write-back planning app: 15 controls, 2 input tables, 9 tables, 5 KPIs. Start here. |

## Read these for style, not as POST payloads

All three are `GET /v2/workbooks/{id}/spec` round-trips of workbooks built in the
UI, so they are in the **pre-August-2026 nested shape**
(`pages[].elements[...]`), which the current spec endpoint rejects. See
`../../sigma-workbook-conventions/reference/schema-2026-08-breaking-changes.md`
for the migration: elements now live in one flat `document.elements` list and the
layout XML is the source of truth for nesting.

Practical consequence: running `scripts/validate-spec.py` against these files
reports every element as "not placed in the layout XML." That is the linter
correctly identifying the old schema, not a defect in the examples. Use them to
read `style` objects, `themeOverrides`, container composition and colour rules —
then author your own spec in the current shape.

Connection and folder IDs in these specs are environment-specific. Substitute
your own before POSTing anything derived from them.

## What these specs are

All three are **fictional demo workbooks**, not customer data:

- `cold-provisions.json` — an ice-cream manufacturer/retailer. The richest of the
  three by a wide margin, and the one to read first: 654 style objects, 34
  element kinds, 83 distinct colours, 21 inline data-URI SVG icons, and the only
  example here using `backgroundImage` — the technique behind a brand-gradient
  header and gradient KPI cards. Also the only one with `donut-chart`,
  `combo-chart`, `scatter-chart`, an embedded `plugin` element, and the `bold` /
  `color` / `horizontalAlign` / `strokeStyle` style properties.
- `marketing-control-center.json` — campaign/channel performance. Read it for
  `tableStyles` theming and a `region-map`.
- `demand-planning.json` — forecast adjustment. The smallest; read it for
  `borderRadius` theming and a clean input-table layout.

Every identifier in them (connection, data model, plugin, workbook, folder,
owner) is a placeholder. Column and element names are the original demo's, which
is the point — they show how a real, polished workbook is actually organised.

## External dependencies baked into these specs

Two of these specs reference images hosted outside Sigma. Harmless to read, but
if you clone the block you inherit the dependency:

- `https://live-image.netlify.app/badge.svg?text=…` — a dynamic-badge service
  used to render a live text value as an image. Third-party hosting that may
  disappear; if you want that effect, self-host the endpoint or use a
  `data:image/svg+xml` URI instead.
- A Webflow CDN photo URL in `marketing-control-center.json`.

Prefer inline `data:` URIs for anything you intend to ship — they have no
runtime dependency, no CORS surprises, and they survive the source site being
redesigned. See the styling skill's "Images and icons" section.
