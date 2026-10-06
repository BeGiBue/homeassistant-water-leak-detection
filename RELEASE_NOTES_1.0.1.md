# Water Leak Guard 1.0.1

Version 1.0.1 improves the configuration experience for households with multiple notification devices.

## Notification recipients are now visible as a group

During initial setup and later under **Configure → Notification recipients**, Water Leak Guard now shows all recipients that are already configured.

The overview remains visible while you:

- add another recipient,
- select a recipient to edit,
- edit a recipient,
- remove a recipient.

For every configured recipient the UI shows:

- display name,
- `notify.mobile_app_*` service,
- assigned `device_tracker.*`.

Internal recipient IDs and notification action tokens are intentionally not shown.

This makes it much easier to configure several phones or tablets without losing track of which devices are already included.

## Home Assistant classification

The integration remains a normal Home Assistant integration:

- `"integration_type": "service"`
- technical domain: `water_leak_detection`

It is **not** a Helper.

## Upgrade

Update to **1.0.1** through HACS and restart Home Assistant. Existing recipient configuration is kept; this release changes how configured recipients are presented in the setup/configuration UI.
