# Water Leak Guard 1.0.0

Version 1.0.0 is the first stable release of Water Leak Guard / Wasserwächter.

## Important upgrade fix: normal integration, not a Helper

The previously published 0.3.0 tag was created from an older commit whose manifest still contained:

`"integration_type": "helper"`

That made Home Assistant expose the custom config flow through the Helpers area.

Release **1.0.0 fixes the published package itself**. Its manifest contains:

- `"version": "1.0.0"`
- `"integration_type": "service"`
- `"name": "Water Leak Guard"`

Home Assistant therefore loads the component as a normal integration under **Settings → Devices & services → Integrations**.

The technical domain remains `water_leak_detection`, so this is an update of the same integration rather than a new helper/domain. After updating through HACS, restart Home Assistant so the loader re-reads the new manifest.

## Stable feature set

- Slow Leak, Low Flow, High Flow, and Burst Leak detection.
- Independent Slow/Low enable switches.
- High Flow bypass without disabling Burst detection.
- Multi-device Companion notifications.
- Home-aware acknowledgement and per-device mute.
- Trusted stationary Home devices.
- Persistent alarm/event state across restarts.
- Independent Water Shut Off request.
- Adaptive rolling learning with confidence and coverage.
- Hydraulic plausibility limits.
- Adaptive High/Burst thresholds.
- Rapid rate-of-rise Burst detection.
- German and English runtime localization.
- Notification recipients selectable during initial setup.
- Measurement sources, recipients, and expert settings available later through **Configure**.

## Upgrade from 0.3.0

1. Update Water Leak Guard to **1.0.0** in HACS.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Integrations**.
4. Verify **Wasserwächter / Water Leak Guard** is listed there and is no longer offered as a Helper.
5. Review the existing configuration and notification recipients.

Do not reinstall the old 0.3.0 release to diagnose the Helper display; that release itself contains the obsolete Helper classification.

## Safety behavior

- High Flow bypass suppresses High Flow only.
- Burst Leak always remains active.
- Acknowledgement does not mean the physical leak has ended.
- Acknowledgement does not automatically clear the shutoff request.
- Hydraulic calculations are plausibility context, not a guaranteed physical maximum.
- Automatic valve closure must be explicitly configured and tested by the user.
