# Releasing 1.0.2

HACS installs the integration directly from:

`custom_components/water_leak_detection`

## Critical release checks

Before publishing, verify in `custom_components/water_leak_detection/manifest.json`:

- `"version": "1.0.2"`
- `"integration_type": "service"`

The release must remain a normal Home Assistant integration and must never regress to `helper`.

Also verify:

- the repository contains `LICENSE`,
- `pyproject.toml` declares `AGPL-3.0-only`.

## Publish

Use the manual **Publish 1.0.2** workflow. It verifies:

- manifest version 1.0.2,
- `integration_type: "service"`,
- visible name `Water Leak Guard`,
- presence of `RELEASE_NOTES_1.0.2.md`,
- repository licensing remains **AGPL-3.0-only**.

The workflow first runs the reusable validation workflow. Checkout and release target
both use the triggering immutable `github.sha` / `GITHUB_SHA`, never a moving branch.
A failed validation prevents publication. Run external hassfest/HACS checks as well.

It then creates GitHub Release `1.0.2` using those release notes.

## HACS versioning

HACS derives the remote version from the latest published GitHub Release.

## Post-release verification

- GitHub Release is `1.0.2`.
- Tagged manifest reports `1.0.2`.
- Tagged manifest reports `integration_type: "service"`.
- HACS offers `1.0.2`.
- Existing recipient configuration survives the update.
- Configure remains open after saving a subsection.
- Notification recipients can navigate back to the main Configure menu.
- Recipient descriptions render real line breaks instead of literal escape sequences.

The current correction round is unreleased. Do not run publication workflows while reviewing it.

The shared script for 1.0.1 and 1.0.2 atomically creates a missing GitHub tag ref
on `GITHUB_SHA` through the GitHub Git References API. It never force-updates a ref.
A failed creation may mean another run won; the ref is reread and must still resolve
to precisely that SHA. Annotated tags are fully peeled to commits. Tags are verified
again immediately before release creation and after verifying the release's tag name.
A racing release creator is accepted only after the same checks. Remote errors fail
closed. Workflow concurrency serializes publication for the same release tag.

**For the complete SHA guarantee, release tags must be protected against moving
with GitHub Rulesets / Tag Protection.** A client script cannot prevent an authorized
external user from force-moving a tag after a successful check. Checks detect moves
during the observed operations and fail hard; they cannot undo a concurrent external
mutation or guarantee that it will never happen later. Configure tag protection
before running publication workflows. This correction round does not publish a tag
or release and does not modify GitHub Rulesets itself.
