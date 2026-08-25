# Comparison KPI Card — Sigma plugin

A polished KPI card: current-vs-prior value with ▲/▼ RAG delta, a sparkline, and
a gradient background — the composite KPI look that's awkward to build with native
Sigma elements. Single-file, vanilla JS, `@sigmacomputing/plugin` SDK from CDN
(no build step). Renders synthetic data when opened standalone (preview).

## Use in Sigma
0. Host `index.html` somewhere publicly reachable — see `../HOSTING.md`.
1. Admin → Plugins → Add plugin → paste your hosted URL.
2. In a workbook, add the plugin element; in the editor panel set: **source** element,
   **Trend order** (date/x column), **Measure**, **title**, **format** (currency/number/percent),
   **comparison** mode, **accent color**.

## Deploy updates
Re-publish `index.html` to wherever you host it. Note there is **no update
endpoint** for an already-registered plugin — changing the URL means registering
a new `pluginId` and re-pushing every workbook that referenced the old one.
