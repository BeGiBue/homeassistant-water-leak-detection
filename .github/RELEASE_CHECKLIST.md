# Release checklist

## Repository metadata

- [x] Repository is public.
- [x] Repository description explains the integration.
- [x] GitHub Topics include Home Assistant / HACS / leak detection.
- [x] README documents installation and usage.
- [x] `hacs.json` exists at repository root.
- [x] Integration has local brand assets.

## Version 1.0.1

- [x] Manifest version is 1.0.1.
- [x] Manifest classifies the component as `integration_type: "service"`, never `helper`.
- [x] Recipient overview is implemented for initial setup and later configuration.
- [x] Release notes are prepared in `RELEASE_NOTES_1.0.1.md`.
- [x] Changelog updated.
- [x] Publish GitHub Release with tag `1.0.1`.
- [x] Verify the tagged manifest still says `service`.
- [ ] Verify HACS sees `1.0.1`.
