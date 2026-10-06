# Releasing 0.3.1

This repository is prepared so release 0.3.1 can be published without building a ZIP artifact.

HACS installs the integration directly from:

`custom_components/water_leak_detection`

## Before publishing

Repository settings must contain at least one GitHub Topic. Recommended Topics:

- `home-assistant`
- `hacs`
- `water-leak`
- `leak-detection`

The repository description and Issues are already enabled.

## Validate

From the GitHub **Actions** tab, run these manual workflows:

1. **Validate**
2. **Hassfest**
3. **HACS**

The HACS workflow uses the official `hacs/action@main` validator.

## Publish

After the release-preparation changes are merged into `main`:

1. Open **Actions**.
2. Select **Publish 0.3.1**.
3. Choose **Run workflow**.
4. Run it on `main`.

The workflow verifies that the manifest version is exactly `0.3.1`, then runs:

`gh release create 0.3.1 --target main`

using `RELEASE_NOTES_0.3.1.md` as the release body.

If the tag does not yet exist, GitHub CLI creates the tag for the target commit as part of publishing the release.

## HACS versioning

Once the GitHub Release is published, HACS uses the latest published release tag as the remote version.

A standalone Git tag without a GitHub Release is not enough for HACS release versioning.

## Post-release verification

- Confirm the GitHub Release page shows version `0.3.1`.
- Open the HACS repository deep link from README.
- Confirm HACS offers version `0.3.1`.
- Install on a test Home Assistant instance.
- Restart Home Assistant.
- Add the integration through Devices & Services.
- Verify the integration shows its local brand icon.
