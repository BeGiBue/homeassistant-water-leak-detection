# Release checklist

## Repository metadata

- [x] Repository is public.
- [x] Repository description explains the integration.
- [x] GitHub Topics include Home Assistant / HACS / leak detection.
- [x] README documents installation and usage.
- [x] `hacs.json` exists at repository root.
- [x] Integration has local brand assets.
- [x] Manifest contains domain, documentation, issue tracker, code owners, name, and version.

## Version 1.0.0

- [x] Manifest version is 1.0.0.
- [x] Manifest classifies the component as `integration_type: "service"`, never `helper`.
- [x] Release notes are prepared in `RELEASE_NOTES_1.0.0.md`.
- [x] Changelog updated.
- [ ] Publish GitHub Release with tag `1.0.0` pointing to the release-preparation commit.
- [ ] Use `RELEASE_NOTES_1.0.0.md` as the release body.
- [ ] Verify the tagged manifest still says `service`.
- [ ] Run the manual **HACS** workflow if a release validation is desired.

## HACS behavior

When GitHub Releases are used, HACS derives the remote version from the latest published release tag. A tag without a published Release is not sufficient.

The old 0.3.0 release tag contains a manifest classified as `helper`. Version 1.0.0 is the first stable release that supersedes that classification.
