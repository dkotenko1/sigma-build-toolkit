# Provenance and attribution

## Credit where it's due

The substance of this toolkit — the verified API spec shapes, the layout and
formula patterns, the styling guidance, the plugin reference — was written by
**Connor Miller** (Solutions Engineering, Sigma Computing) as part of a larger
skill collection. This repository is a curated, redacted subset of that work,
reorganised for general use.

If you find this useful, the credit is his. This repo is a redistribution, not
original research.

## What this is a subset of

The source collection is larger. This repository is a deliberately narrow slice
of it: the reusable craft layer, and nothing that is specific to any particular
organisation or environment.

Excluded by category:

- end-to-end dashboard generators and their configuration
- working notes and status documents
- anything named after, or built for, a specific organisation
- environment identifiers, hostnames and credential file paths

What remains is verified API spec shapes, formula and layout patterns,
visual-design guidance, a linter, and generically-named examples. Cross-
references to excluded material were rewritten, skill descriptions were
rewritten by hand, and the brand kit is a neutral template.

Every identifier in the example specs — connection, data model, plugin,
workbook, folder, owner — is a placeholder. The example workbooks themselves are
fictional demos, not anyone's data.

Automated sweeps over every file report zero organisation names, environment
identifiers, credentials or local paths. Those are keyword and pattern sweeps,
not a proof — if you spot something that shouldn't be here, please open an issue
and it will be removed.

## Licensing

There is no `LICENSE` file here yet, so no formal grant is in place: copyright in
the underlying material stays with its author, and publishing it publicly does
not transfer or waive that.

Practically, that separates into two things:

- **The knowledge is yours to use.** Facts and techniques aren't copyrightable —
  which spec field is required, which value gets rejected, why an element renders
  empty. Read it, and apply what you learn to your own Sigma work freely. That is
  the entire point of the repo.
- **The files are not yet yours to redistribute.** The example specs, the plugin
  `index.html` files and the scripts are creative works. Copying them verbatim
  into your own repository or product, or relicensing them, needs the author's
  agreement first. Reading them and writing your own is fine.

If a licence is agreed later it will be added as a `LICENSE` file and this
section replaced. If you need one to proceed, open an issue and say so.

## Not an official Sigma product

This is field and community material, not a supported Sigma deliverable. It
carries no warranty and no support commitment, and Sigma Support does not cover
it. Specifics — element shapes, error behaviour, which fields are UI-only — were
verified against a particular org at a particular time and will drift as Sigma
ships. Treat
[Sigma's published OpenAPI](https://assets.sigmacomputing.com/openapi/public-rest-api/sigma-computing-public-rest-api.json)
as the source of truth for shape, and see
`skills/sigma-workbook-conventions/reference/openapi-is-source-of-truth.md`.

For supported tooling, see
[`sigmacomputing/sigma-agent-skills`](https://github.com/sigmacomputing/sigma-agent-skills)
and [Sigma Support](https://help.sigmacomputing.com/docs/sigma-support).
