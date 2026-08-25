# Hosting and registering a Sigma plugin

Each plugin here is a single self-contained `index.html` with no build step — it
pulls the `@sigmacomputing/plugin` SDK from a CDN. To use one, host that file at
a publicly reachable URL and register the URL with Sigma.

## Use GitHub Pages, not jsDelivr

**This is the one finding worth reading before you pick a host.** A
`cdn.jsdelivr.net/gh/...` URL serves `.html` files as
`Content-Type: text/plain`, not `text/html`. Two consequences, both reproduced
live:

1. Depending on how the embedding iframe treats a `text/plain` response, the
   plugin can render as **literal HTML source text** instead of executing.
2. `POST /v2/workbooks/{id}/export {"format":{"type":"png"}}` **hangs
   indefinitely** for any page containing that plugin element — the renderer
   never reaches idle. Isolated by proving table-only exports on the same
   workbook complete in 15–20s.

GitHub Pages serves a correct `text/html` and fixes both. Verify with:

```bash
curl -sD - -o /dev/null https://<your-user>.github.io/<repo>/plugins/<name>/index.html | grep -i content-type
```

Expect `text/html`. Any static host that serves the right content type works —
Pages is just the path of least resistance if the plugin already lives in a repo.

## Enable Pages on your repo

```bash
gh api -X POST repos/<owner>/<repo>/pages -f "source[branch]=main" -f "source[path]=/"
```

A Pages build takes 30–60s after a push. Confirm before registering:

```bash
gh api repos/<owner>/<repo>/pages/builds/latest --jq .status   # expect "built"
```

## Register the plugin

```bash
curl -s -X POST "$SIGMA_BASE_URL/v2/plugins" \
  -H "Authorization: Bearer $SIGMA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Decomposition Tree",
       "description":"Interactive metric decomposition with drill-to-control",
       "url":"https://<your-user>.github.io/<repo>/plugins/decomposition-tree/index.html",
       "type":"element"}'
```

The response carries a `pluginId`. Use it in a workbook spec:

```json
{ "kind": "plugin", "pluginId": "<pluginId>",
  "config": { "source": { "kind": "element", "elementId": "tbl-base" }, "...": "..." },
  "style": { "backgroundColor": "#FFFFFF" } }
```

## Hosting on localhost

If the plugin lives on `http://localhost:PORT` (the fastest path, and the only
one available without a repo to publish from):

- **It works in a browser.** `http://localhost` is a "potentially trustworthy"
  origin, so an https Sigma page is allowed to iframe it — this is not blocked
  as mixed content.
- **It does not work for anyone else, or for the renderer.** Sigma's headless
  PNG export runs in Sigma's cloud and cannot reach your machine, so every
  export of that page hangs until it times out. Same for a colleague opening
  the workbook.
- **The dev server has to be running.** Nothing in the workbook says so; the
  element just sits blank.

So build a stub switch into the generator and use it for screenshots:

```python
if os.environ.get("STUB") == "1":
    add({"id": "plg-board", "kind": "text", "verticalAlign": "middle",
         "body": "_plg-board (stubbed for render)_"})
else:
    add({"id": "plg-board", "kind": "plugin", "pluginId": PLUGIN_ID, "config": {...}})
```

Ship it on a real static host before anyone but you needs to see it.

## Two constraints that will bite you

**There is no update endpoint.** `PATCH`/`PUT` on a registered plugin returns
404. Changing a plugin's hosting URL means registering a **new** `pluginId` and
re-pushing every workbook that referenced the old one. Verify the swap landed by
`GET`-ing the live workbook spec and checking the element's `pluginId` directly —
a successful update response does not by itself prove the new id is bound.

**`plugin.style` accepts `backgroundColor` only, and it must be a hex.**
`"transparent"` is rejected.

## Authoring notes, if you write your own

- Use a **`ResizeObserver` on the stage element**, not a window resize listener —
  a window listener doesn't fire when only the Sigma element is resized.
- **No infinite animation loop.** Headless PNG export waits for idle forever, so
  an always-animating plugin makes every export of that page hang.
- Inline SVG needs an explicit `xmlns`.
- Ship a `synth()` fallback that renders plausible synthetic data when unbound,
  so the plugin looks right in the editor and during the config handshake
  (including headless export, which snapshots before that round-trip finishes).
- Keep any thresholds or status bands **consistent with what the rest of the page
  shows.** A plugin labelling a line "Behind" while the table above it says "On
  plan" is the first thing an analyst notices.

See `../skills/sigma-plugin-development/SKILL.md` for the full SDK surface and
`../skills/sigma-plugin-patterns/SKILL.md` for architectural recipes.
