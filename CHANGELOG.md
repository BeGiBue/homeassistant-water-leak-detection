# Changelog

All notable changes to Home Assistant Water Leak Detection are documented here.

## 0.3.1 — 2026-10-06

### Fixed

- The integration is now classified as a normal Home Assistant service integration instead of a helper, so it appears under **Settings → Devices & services → Integrations**.
- Complete English and German runtime translations now follow the configured Home Assistant language.
- Device names, entity names, translated sensor states, service actions, and Companion notification text are localized.
- Notification recipients can be selected during initial setup.
- Notification recipients and expert settings can be reopened later through **Configure**.
- Measurement source entities can be changed later through **Reconfigure**.
- Options changes reload the integration through Home Assistant's native reloadable options flow.

### Compatibility

- No detector thresholds, adaptive-learning algorithms, shutoff semantics, or acknowledgement rules were changed from 0.3.0.
- Existing runtime state and learning history remain compatible.

## 0.3.0 — 2026-10-06

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
