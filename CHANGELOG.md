# Changelog

All notable changes to Water Leak Guard are documented here.

## 1.0.1 — 2026-10-06

### Improved

- Notification-recipient setup now shows all already configured alert devices instead of only the device currently being edited.
- The overview stays visible while adding, editing, or removing recipients.
- Each configured recipient is shown with display name, Companion notification service, and matching device tracker.
- The same overview is available both during initial setup and later through **Configure → Notification recipients**.
- Internal recipient IDs and action tokens remain hidden.

## 1.0.0 — 2026-10-06

### Stable release

- First stable release of Water Leak Guard / Wasserwächter.
- The published manifest explicitly uses `integration_type: "service"`; the integration is therefore exposed through **Settings → Devices & services → Integrations**, not through **Helpers**.
- Supersedes the 0.3.0 GitHub release, whose tag was created before the integration-type and visible-name corrections landed on `main`.
- Keeps the existing technical domain `water_leak_detection` and config-entry model, so an update does not create a new helper/domain.
- Includes the completed detection, notification, acknowledgement, Water Shut Off, adaptive-learning, hydraulic-plausibility, localization, and post-install configuration work from the 0.x roadmap.
- Adds release metadata regression coverage that requires the manifest to stay a normal `service` integration.

## 0.3.0 — 2026-10-06

### Fixed before first 0.3.0 release

- Integration is classified as a normal Home Assistant service integration instead of a helper, so it appears under **Settings → Devices & services → Integrations**.
- Complete runtime localization for English and German using Home Assistant's configured language.
- Device names, entity names, translated sensor states, action labels, and Companion notification text now follow the Home Assistant language.
- Notification recipients can be selected during initial setup.
- Measurement sources, notification recipients, and expert settings can all be reopened later through **Configure**.
- Measurement source entities can additionally be changed through Home Assistant's **Reconfigure** action.

### Added

- Continuous rolling adaptive normal-flow learning.
- Learning confidence states: insufficient, learning, reliable.
- Short-term and long-term references for seasonal adaptation.
- Hydraulic plausibility model using nominal pipe diameter and static pressure.
- Adaptive High Flow and Burst Leak thresholds.
- Rapid rate-of-rise Burst Leak detection.
- Learned maximum, confidence, coverage, hydraulic reference, and effective-threshold sensors.
- `water_leak_detection.reset_learning` action.
- Detector reason in leak/shutoff event payloads.
- Deterministic tests for adaptive learning, hydraulic context, and Burst behavior.

### Safety behavior

- Suspicious High/Burst candidates are excluded from learning.
- High Flow bypass periods are excluded from learning.
- Insufficient learning confidence does not raise safety thresholds.
- Burst Leak remains active during High Flow bypass.
- Adaptive thresholds are bounded by the hydraulic plausibility envelope.

## 0.2.0 — 2026-10-06

### Added

- Multiple Companion App notification recipients.
- Per-device mute.
- Backend-authorized global acknowledgement while the responding device is Home.
- Trusted stationary Home-device support.
- Return-home re-notification for active, globally unacknowledged events.
- Persistent acknowledgement state.
- Add/edit/remove recipient options UI.
- Critical Burst notification payloads for iOS and Android.

## 0.1.0 — 2026-10-06

### Added

- Initial Home Assistant custom integration.
- Config Flow and Options Flow.
- Flow/total source selection and unit normalization.
- Slow Leak, Low Flow, High Flow, and Burst Leak detectors.
- Independent Slow Leak and Low Flow enable switches.
- High Flow bypass.
- Persistent detector/event state.
- Independent Water shutoff request.
- Backend entities, actions, events, translations, and automated tests.
