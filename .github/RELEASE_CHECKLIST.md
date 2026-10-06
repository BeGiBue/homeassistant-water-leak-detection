# Release checklist

## Repository metadata

- [x] Repository is public.
- [x] Repository description explains the integration.
- [x] GitHub Topics include Home Assistant / HACS / leak detection.
- [x] README documents installation and usage.
- [x] `hacs.json` exists at repository root.
- [x] Integration has local brand assets.
- [x] Repository contains `LICENSE`.
- [x] License is **AGPL-3.0-only**.

## Version 1.0.2

- [x] Manifest version is 1.0.2.
- [x] Manifest classifies the component as `integration_type: "service"`, never `helper`.
- [x] Configure navigation remains open after saving subsections.
- [x] Notification-recipient rendering is fixed.
- [x] Release notes are prepared in `RELEASE_NOTES_1.0.2.md`.
- [x] Changelog updated.
- [ ] HACS validation passes.
- [ ] Publish GitHub Release with tag `1.0.2`.
- [ ] Verify the tagged manifest still says `service`.
- [ ] Verify HACS offers `1.0.2`.
