# Releasing 1.0.0

This repository is prepared so release 1.0.0 can be published without building a ZIP artifact.

HACS installs the integration directly from:

`custom_components/water_leak_detection`

## Before publishing

Repository settings must contain GitHub Topics such as:

- `home-assistant`
- `hacs`
- `water-leak`
- `leak-detection`

The repository description and Issues are enabled.

## Critical Home Assistant classification check

Before publishing, verify in `custom_components/water_leak_detection/manifest.json`:

- `"version": "1.0.0"`
- `"integration_type": "service"`

Do **not** publish a release that declares `integration_type: "helper"`. Home Assistant routes custom config flows with that type to the Helpers UI.

The 0.3.0 GitHub release was tagged from an older commit that still used `helper`; 1.0.0 supersedes it.

## Validate

From the GitHub **Actions** tab, run these manual workflows when required:

1. **Validate**
2. **Hassfest**
3. **HACS**

The HACS workflow uses the official `hacs/action@main` validator.

## Publish

After the release-preparation changes are merged into `main`:

1. Open **Actions**.
2. Select **Publish 1.0.0**.
3. Choose **Run workflow**.
4. Run it on `main`.

The workflow verifies the manifest version and integration type, then publishes GitHub Release `1.0.0` using `RELEASE_NOTES_1.0.0.md`.

## HACS versioning

Once the GitHub Release is published, HACS uses the latest published release tag as the remote version.

A standalone Git tag without a GitHub Release is not enough for HACS release versioning.

## Post-release verification

- Confirm the GitHub Release page shows version `1.0.0`.
- Confirm the tagged `manifest.json` contains `"integration_type": "service"`.
- Open the HACS repository deep link from README.
- Confirm HACS offers version `1.0.0`.
- Update/install on a test Home Assistant instance.
- Restart Home Assistant.
- Verify **Wasserwächter / Water Leak Guard** appears under **Devices & services → Integrations**, not under **Helpers**.
- Verify the integration shows its local brand icon.
