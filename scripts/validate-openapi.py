#!/usr/bin/env python3
"""Validate a workbook/report spec against Sigma's PUBLISHED OpenAPI, locally.

Why this exists alongside `validate-spec.py`:

  * `validate-spec.py` catches the behavioural traps the schema cannot express —
    unplaced elements, empty containers, overlapping siblings, silently-dropped
    fields. It knows nothing about per-kind field shapes.
  * The API itself does know, but it stops at the FIRST bad element and reports
    it as `Invalid kind: "<kind>"`, naming the element kind rather than the field
    that is actually wrong. Fixing a spec that way costs one network round trip
    per mistake.

This script closes that gap: it walks the nested `oneOf` unions in the OpenAPI's
`WorkbookElement`, picks the branch matching each element's `kind`, and prints
the real offending field for EVERY element in one pass, offline.

    python3 scripts/validate-openapi.py <spec.json> [openapi.json]

With no second argument the OpenAPI is downloaded once and cached in
`vendor/sigma-openapi.json` (gitignored). Delete that file to force a refresh —
the spec changes between Sigma releases, and a stale cache will happily bless a
spec the live API now rejects.

Requires `jsonschema` (pip install jsonschema). If it is not importable the
script exits 0 with a notice rather than failing a pipeline — it is an
additional check, not a gate.

Run it BEFORE validate-spec.py: shape errors are cheaper to fix than layout
ones, and a spec that fails here will never reach the layout stage anyway.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

OPENAPI_URL = (
    "https://assets.sigmacomputing.com/openapi/public-rest-api/"
    "sigma-computing-public-rest-api.json"
)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO_ROOT, "vendor", "sigma-openapi.json")

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import best_match
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "validate-openapi: jsonschema not installed — skipping.\n"
        "  pip install jsonschema\n"
    )
    sys.exit(0)


def load_openapi(path: str | None) -> dict:
    if path:
        with open(path) as f:
            return json.load(f)
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        sys.stderr.write("validate-openapi: fetching %s\n" % OPENAPI_URL)
        with urllib.request.urlopen(OPENAPI_URL, timeout=120) as r:
            data = r.read()
        with open(CACHE, "wb") as f:
            f.write(data)
    with open(CACHE) as f:
        return json.load(f)


def relax_oneof(node) -> None:
    """Sigma's OpenAPI uses `oneOf` where it means `anyOf`.

    Several unions carry duplicate branches — a color is
    `oneOf: [{type: string}, {type: string}, {theme ref}]`, and a plain hex
    string is valid under BOTH string branches. Under strict oneOf semantics
    that is a failure ("is valid under each of ..."), so validating the spec
    as published produces a flood of false positives on almost every styled
    element. The API plainly does not enforce exclusivity; relax to anyOf.
    """
    if isinstance(node, dict):
        if "oneOf" in node and "anyOf" not in node:
            node["anyOf"] = node.pop("oneOf")
        for v in node.values():
            relax_oneof(v)
    elif isinstance(node, list):
        for v in node:
            relax_oneof(v)


class Checker:
    def __init__(self, oas: dict):
        self.oas = oas
        self.schemas = oas["components"]["schemas"]

    def deref(self, s):
        seen = 0
        while isinstance(s, dict) and "$ref" in s and len(s) == 1:
            s = self.schemas[s["$ref"].split("/")[-1]]
            seen += 1
            if seen > 32:  # cycle guard
                break
        return s

    def leaves(self, schema) -> list:
        """Expand anyOf/oneOf unions into concrete candidate schemas."""
        schema = self.deref(schema)
        if not isinstance(schema, dict):
            return [schema]
        for key in ("anyOf", "oneOf"):
            if key in schema:
                out = []
                for branch in schema[key]:
                    out.extend(self.leaves(branch))
                return out
        return [schema]

    def constrains_kind(self, schema, want: str, depth: int = 0) -> bool:
        """Does this candidate pin `kind` (or `type`) to `want`?"""
        schema = self.deref(schema)
        if not isinstance(schema, dict) or depth > 10:
            return False
        props = schema.get("properties") or {}
        for field in ("kind", "type"):
            node = self.deref(props.get(field, {}))
            if not isinstance(node, dict):
                continue
            if want in (node.get("enum") or []) or node.get("const") == want:
                return True
            for sub in (node.get("anyOf") or []) + (node.get("oneOf") or []):
                sub = self.deref(sub)
                if want in (sub.get("enum") or []) or sub.get("const") == want:
                    return True
        return any(
            self.constrains_kind(b, want, depth + 1) for b in schema.get("allOf", [])
        )

    def check(self, objects: list, item_schema, label: str) -> list[str]:
        candidates = self.leaves(item_schema)
        problems = []
        for i, obj in enumerate(objects):
            want = obj.get("kind") or obj.get("type") or ""
            matching = [c for c in candidates if self.constrains_kind(c, want)]
            if not matching:
                # unknown kind — validate against everything and take the closest
                matching = candidates
            fewest = None
            for cand in matching:
                full = dict(cand)
                full["components"] = self.oas["components"]
                errs = list(Draft202012Validator(full).iter_errors(obj))
                if not errs:
                    fewest = None
                    break
                if fewest is None or len(errs) < len(fewest):
                    fewest = errs
            else:
                if fewest:
                    b = best_match(iter(fewest))
                    where = ".".join(str(p) for p in b.absolute_path) or "(root)"
                    problems.append(
                        "%s[%d] id=%s kind=%s — %s: %s"
                        % (label, i, obj.get("id", "?"), want, where, b.message[:300])
                    )
        return problems


def document_properties(checker: Checker, root_schema_name: str):
    """Find the `document` sub-schema that actually declares `elements`.

    The path through the allOf chain moves between API releases, so search for
    it rather than hardcoding indices (an earlier version of this script
    hardcoded them, found nothing, and cheerfully reported a broken spec as
    clean — the worst possible failure mode for a validator).
    """
    found = []

    def walk(node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict) and "elements" in props:
                found.append(props)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(checker.schemas[root_schema_name])
    if not found:
        raise SystemExit(
            "validate-openapi: could not locate `document.elements` in "
            "%s — the OpenAPI structure changed. Re-derive the path with:\n"
            "  jq '.components.schemas.%s' vendor/sigma-openapi.json"
            % (root_schema_name, root_schema_name)
        )
    return found[0]


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.stderr.write("usage: validate-openapi.py <spec.json> [openapi.json]\n")
        sys.exit(2)
    spec_path = sys.argv[1]
    with open(spec_path) as f:
        spec = json.load(f)

    oas = load_openapi(sys.argv[2] if len(sys.argv) == 3 else None)
    relax_oneof(oas)
    checker = Checker(oas)

    doc = spec.get("document") or spec
    root_name = "CreateWorkbookSpec" if "CreateWorkbookSpec" in checker.schemas else "WorkbookSpec"
    props = document_properties(checker, root_name)

    problems: list[str] = []
    for key in ("elements", "overlays", "agents"):
        if key in props and isinstance(props[key].get("items"), dict):
            problems += checker.check(doc.get(key, []) or [], props[key]["items"], key)

    if not problems:
        n = len(doc.get("elements", []) or [])
        print("validate-openapi: %s — %d element(s) valid against the OpenAPI" % (spec_path, n))
        sys.exit(0)

    for p in problems:
        sys.stderr.write("[openapi] %s\n" % p)
    sys.stderr.write(
        "\nvalidate-openapi: %d object(s) with schema errors in %s\n"
        "Note: the API reports only the FIRST of these, masked as "
        '`Invalid kind: "<kind>"`.\n' % (len(problems), spec_path)
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
