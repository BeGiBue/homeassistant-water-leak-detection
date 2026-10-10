# Releasing 1.0.3

HACS installs the integration directly from:

`custom_components/water_leak_detection`

## Critical release checks

Before publishing, verify in `custom_components/water_leak_detection/manifest.json`:

- `"version": "1.0.3"`
- `"integration_type": "service"`

Also verify:

- `pyproject.toml` reports version `1.0.3`,
- the repository contains `LICENSE`,
- `pyproject.toml` declares `AGPL-3.0-only`,
- `RELEASE_NOTES_1.0.3.md` exists,
- the full validation workflow passes.

## Publish

The **Publish 1.0.3** workflow validates the exact triggering commit before publication.

The initial release-preparation commit may trigger publication automatically once when
`.github/workflows/release-1.0.3.yml` is added with the exact commit message
`Release 1.0.3`. Manual reruns remain available through `workflow_dispatch`.

The release job verifies:

- manifest version 1.0.3,
- project version 1.0.3,
- `integration_type: "service"`,
- visible name `Water Leak Guard`,
- presence of `RELEASE_NOTES_1.0.3.md`,
- repository licensing remains **AGPL-3.0-only**.

The workflow first runs the reusable validation workflow. Checkout, validation,
tag creation and release publication all target the same immutable `github.sha` /
`GITHUB_SHA`. A failed validation prevents publication.

The shared release script atomically creates a missing GitHub tag ref, never force-updates
an existing tag, verifies the tag's commit before publication, and verifies it again after
release creation.

## HACS versioning

HACS derives the remote version from the latest published GitHub Release.

## Post-release verification

- GitHub Release is `1.0.3`.
- Tag `1.0.3` resolves to the validated release commit.
- Tagged manifest reports `1.0.3`.
- Tagged manifest reports `integration_type: "service"`.
- HACS can discover `1.0.3`.

## Release scope

1.0.3 publishes the independently reviewed technical correction series through
Korrekturrunde 7. F05 and F15 are verified. The separate detector-design topics
F02, F04, F08 and Rapid Rise remain outside this bug-fix release.

For a complete immutable-tag guarantee, protect release tags with GitHub Rulesets /
Tag Protection. The client-side checks fail closed if a tag moves during the observed
release operations, but cannot prevent a separately authorized actor from moving it later.
