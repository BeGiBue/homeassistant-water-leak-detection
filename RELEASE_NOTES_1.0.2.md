# Water Leak Guard 1.0.2

Version 1.0.2 fixes navigation and rendering problems in the Home Assistant **Configure** flow.

## Configure stays open after saving

Saving a subsection no longer closes the complete options flow.

After saving:

- **Measurement sources** returns to the main Configure menu.
- **Expert settings** returns to the main Configure menu.
- **Add recipient** returns to **Notification recipients**.
- **Edit recipient** returns to **Notification recipients**.
- **Remove recipient** returns to **Notification recipients**.

The notification-recipient submenu now also contains an explicit **Back to configuration** entry.

Home Assistant itself uses the top-left X to close an options-flow dialog and does not provide a native header back button. Water Leak Guard therefore provides the back navigation inside the menu flow.

## Recipient overview rendering fixed

The recipient overview no longer displays literal `\n\n` escape sequences.

The overview now uses normal Markdown line breaks and displays only the configured recipient names, for example:

- **Benedikt**
- **iPad**
- **Theresa**

The long technical `notify.mobile_app_*` and `device_tracker.*` IDs are no longer shown in the overview.

## Clearer action labels

The forms now make the continuing workflow explicit with labels such as:

- **Save and go back**
- **Add and go back**
- **Remove and go back**

German Home Assistant installations receive the corresponding German labels automatically.

## Compatibility

- Existing configuration is preserved.
- Technical domain remains `water_leak_detection`.
- Integration type remains `service`.
- No detector or safety behavior is changed.
