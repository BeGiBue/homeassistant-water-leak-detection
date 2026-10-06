# Release checklist

## Repository metadata

- [x] Repository is public.
- [x] Repository description explains the integration.
- [ ] Add GitHub Topics (required by HACS): `home-assistant`, `hacs`, `water-leak`, `leak-detection`.
- [x] README documents installation and usage.
- [x] `hacs.json` exists at repository root.
- [x] Integration has local brand assets.
- [x] Manifest contains domain, documentation, issue tracker, code owners, name, and version.

## Version 0.3.0

- [x] Manifest version is 0.3.0.
- [x] Python/JSON/compile/Ruff/tests validated.
- [x] Release notes are prepared in `RELEASE_NOTES_0.3.0.md`.
- [x] Changelog updated.
- [ ] Publish GitHub Release with tag `0.3.0` pointing to the release-preparation merge commit.
- [ ] Use `RELEASE_NOTES_0.3.0.md` as the release body.
- [ ] Run the manual **HACS** workflow after Topics and Release are published.

## HACS behavior

When GitHub Releases are used, HACS derives the remote version from the latest published release tag. A tag without a published Release is not sufficient.
