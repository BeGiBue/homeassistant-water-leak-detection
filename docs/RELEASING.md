# Releasing 1.0.1

HACS installs the integration directly from:

`custom_components/water_leak_detection`

## Critical release checks

Before publishing, verify in `custom_components/water_leak_detection/manifest.json`:

- `"version": "1.0.1"`
- `"integration_type": "service"`

The release must remain a normal Home Assistant integration and must never regress to `helper`.

## Publish

Use the manual **Publish 1.0.1** workflow. It verifies:

- manifest version 1.0.1,
- `integration_type: "service"`,
- visible name `Water Leak Guard`,
- presence of `RELEASE_NOTES_1.0.1.md`.

It then creates GitHub Release `1.0.1` using those release notes.

## HACS versioning

HACS derives the remote version from the latest published GitHub Release.

## Post-release verification

- GitHub Release is `1.0.1`.
- Tagged manifest reports `1.0.1`.
- Tagged manifest reports `integration_type: "service"`.
- HACS offers `1.0.1`.
- Existing recipient configuration survives the update.
- Recipient setup/configuration shows all configured alert devices.
