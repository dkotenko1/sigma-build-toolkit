# Demand Pulse — Sigma plugin

One split-ring per region: a donut divided proportionally between two demand
streams, with the primary stream's share shown in the centre, a backlog-weeks
badge (green / amber / red), and a soft halo on regions whose backlog is growing
fast. Ring diameter scales with total volume, so the biggest markets read
biggest at a glance.

Built as an order-backlog view for a fictional automaker ("Sigma Motors"), but
the bindings are generic — any two-way split of a volume metric across a
dimension works: EV vs hybrid, new vs refurbished, contract vs spot, subscription
vs one-off.

Single-file vanilla JS on the `@sigmacomputing/plugin` SDK from CDN, no build
step. Renders synthetic data when opened standalone or before the config
handshake resolves.

## Editor-panel config

| Field | Type | Meaning |
|---|---|---|
| `source` | element | The data element — one row per region/segment |
| `region` | column | The dimension each ring represents |
| `ev_backlog` | number | Primary stream volume (drives the coloured arc) |
| `hybrid_backlog` | number | Secondary stream volume (drives the grey arc) |
| `growth_pct` | number | 30-day growth %; above 25% the ring gets a halo |
| `backlog_weeks` | number | Drives the badge: <2 green, 2–4 amber, ≥4 red |

Embed it the same way as any plugin element — bindings are bare `columnId`
strings matching the editor-panel names:

```json
{ "kind": "plugin", "pluginId": "<pluginId>",
  "config": { "source": { "kind": "element", "elementId": "tbl-regions" },
              "region": "r-name", "ev_backlog": "r-primary",
              "hybrid_backlog": "r-secondary", "growth_pct": "r-growth",
              "backlog_weeks": "r-weeks" },
  "style": { "backgroundColor": "#FFFFFF" } }
```

## Hosting

See [`../HOSTING.md`](../HOSTING.md) — use GitHub Pages, not jsDelivr.

## Note on the halo animation

The growth halo originally used `animation: … infinite`, which breaks headless
PNG export: `POST /v2/workbooks/{id}/export {"format":{"type":"png"}}` waits for
the page to reach idle, and an always-animating element never gets there, so the
export hangs indefinitely rather than failing.

It is now bounded to 4 iterations — the pulse still draws attention on load, then
settles and lets the page idle. **If you add motion to a plugin, bound it.** This
is the same rule stated in `../../skills/sigma-plugin-development/SKILL.md`; this
plugin was violating it.
