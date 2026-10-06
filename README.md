# Water Leak Guard

[![Open your Home Assistant instance and open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BeGiBue&repository=homeassistant-water-leak-detection&category=integration)

A backend-focused Home Assistant custom integration for detecting abnormal water consumption and possible water leaks from an existing water-meter flow sensor.

**Current release:** 1.0.2  
**Minimum Home Assistant:** 2026.9.0  
**Integration domain:** `water_leak_detection`

> [!IMPORTANT]
> This integration can detect suspicious water usage and expose a shutoff request. It does not guarantee prevention of water damage. Automatic valve closure is opt-in and should be tested carefully.

## Highlights

- Separate **Slow Leak**, **Low Flow**, **High Flow**, and **Burst Leak** detectors.
- Independent enable/disable switches for Slow Leak and Low Flow.
- Temporary High Flow bypass for intentional high consumption such as pool filling.
- Burst Leak remains active even while High Flow is bypassed.
- Optional cumulative consumption sensor for event-volume tracking.
- Multi-device Home Assistant Companion notifications.
- Device-specific mute and Home-zone-authorized global acknowledgement.
- Trusted stationary Home devices such as a shared iPad.
- Return-home re-notification while an event is still active and not globally acknowledged.
- Independent `Water shutoff request` entity for an external motorized valve automation.
- Continuous rolling learning of normal peak consumption.
- Learning confidence states: `insufficient`, `learning`, and `reliable`.
- Hydraulic plausibility context using nominal pipe diameter and static pressure.
- Adaptive High Flow and Burst Leak thresholds.
- Rapid rate-of-rise Burst detection.
- Persistent event state, bypass expiry, acknowledgements, and learned history across Home Assistant restarts.

## Installation

### HACS — recommended

Use the button above, or add the repository manually in HACS:

- Repository: `https://github.com/BeGiBue/homeassistant-water-leak-detection`
- Category: **Integration**

Then:

1. Download **Water Leak Guard** in HACS.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**.
4. Search for **Water Leak Guard**.
5. Complete the config flow.

Detailed installation and update instructions: [docs/INSTALLATION.md](docs/INSTALLATION.md)

### Manual installation

Copy:

`custom_components/water_leak_detection`

to:

`<config>/custom_components/water_leak_detection`

Restart Home Assistant and add the integration through **Settings → Devices & services**.

## Measurement sources

The integration requires a compatible flow-rate sensor and can optionally use a cumulative water-consumption sensor.

Reference installation:

- Flow: `sensor.wasserzahler_flow` in `m³/h`
- Total: `sensor.wasserzahler_total`
- Reference flow resolution: 0.001 m³/h = 1 L/h
- Reference installation: DN25 / 1", static pressure 3.5 bar

Flow values are normalized internally to **L/h** and total consumption to **L**.

Supported flow units include L/h, L/min, L/s, m³/h, m³/min, and m³/s.

## Detector defaults

| Detector | Purpose | Default |
|---|---|---|
| Slow Leak | Very small continuous loss | ≥ 3 L/h for 60 min |
| Low Flow | Moderate flow lasting too long | ≥ 150 L/h for 60 min |
| High Flow | Sustained unusually high use | Adaptive; fixed base 600 L/h |
| Burst Leak | Major leak / pipe failure | Adaptive absolute + rapid-rise detection |

Slow Leak and Low Flow can be switched off independently. High Flow can be temporarily bypassed. Burst Leak cannot be bypassed by the High Flow bypass.

All expert thresholds and reset times can be adjusted through the integration options.

## Main entities

The integration creates a Home Assistant device with backend entities including:

- **Status**
- **Current flow**
- **Leak alarm**
- **Water shutoff request**
- **Active event duration**
- **Active event volume**
- **Slow Leak detection**
- **Low Flow detection**
- **High Flow bypass**
- **High Flow bypass duration**
- **High Flow bypass remaining**
- **Learned maximum flow**
- **Learning confidence**
- **Learning coverage**
- **Hydraulic reference flow**
- **Effective High Flow threshold**
- **Effective Burst Leak threshold**

## Language and later configuration

The integration follows the configured Home Assistant backend language.

- German Home Assistant: German integration title, device/entity names, configuration dialogs, states, service actions, and Companion notification text.
- Other supported languages fall back to English unless a matching translation file is provided.

During initial setup, notification recipients can already be added after selecting the measurement sources.

After installation, **Configure** can be opened again at any time. It contains:

- **Measurement sources** — change the flow-rate and optional total-consumption sensors.
- **Notification recipients** — add, edit, or remove Companion App devices.
- **Expert settings** — change detector thresholds, learning, hydraulic context, bypass, and shutoff mapping.

Home Assistant's separate **Reconfigure** action for the measurement sources is also supported.

Changes are applied by reloading the integration automatically. Saving a subsection returns to the appropriate Configure menu instead of closing the entire dialog. The notification-recipient submenu also provides an explicit **Back to configuration** entry.

## Companion notifications and acknowledgement

Notification recipients are configured per Companion App device. Each device can have its own:

- `notify.mobile_app_*` service,
- matching `device_tracker.*`,
- critical Burst-alert setting,
- permission for global acknowledgement while Home,
- trusted stationary Home-device flag.

An away device can mute the current event for itself. Global acknowledgement is accepted only when the configured tracker for the responding device is currently `home`. The check is enforced in backend code.

A shared iPad that normally stays Home can be configured as a trusted stationary Home device and used by another household member to globally acknowledge an event.

Returning Home is treated as a fresh safety context: if an event is still active and not globally acknowledged, that device is notified again.

## High Flow bypass

The integration intentionally does not create a custom `timer.*` platform. It exposes the bypass with HA-native controllable entities and actions:

- switch: start/cancel bypass,
- number: default duration,
- sensor: remaining duration,
- action: `water_leak_detection.start_high_flow_bypass`,
- action: `water_leak_detection.cancel_high_flow_bypass`.

Example:

```yaml
sequence:
  - action: water_leak_detection.start_high_flow_bypass
    data:
      duration_minutes: 240
```

## Adaptive learning

The learner stores peaks from completed, non-suspicious water-use episodes. Events are excluded from learning when High/Burst detection becomes suspicious or active, or while High Flow bypass is active.

The default rolling window is 30 days. Recent and longer-term references are combined so the model can adapt to seasonal changes without allowing one unusual event to redefine normal behavior.

Learning confidence:

- `insufficient` — learned values do not raise safety thresholds,
- `learning` — learned values have reduced influence,
- `reliable` — the robust learned reference can fully influence adaptive thresholds.

Use `water_leak_detection.reset_learning` to intentionally clear admitted learning history.

## Hydraulic context

Nominal pipe diameter and static pressure are used as a **plausibility envelope**, not as an exact physical maximum. Actual flow depends on the meter, pressure reducer, dynamic pressure, pipe length, fittings, and upstream supply.

The hydraulic model limits how far adaptive thresholds can move upward.

## Shutoff request

`binary_sensor.*_water_shutoff_request` is deliberately independent from alarm acknowledgement.

Example external automation:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.water_leak_detection_water_shutoff_request
    to: "on"
actions:
  - action: valve.close_valve
    target:
      entity_id: valve.main_water
```

Replace the entity IDs with the IDs from your Home Assistant instance.

## Events

The integration emits:

- `water_leak_detection_event_started`
- `water_leak_detection_event_ended`
- `water_leak_detection_shutoff_requested`
- `water_leak_detection_shutoff_cleared`
- `water_leak_detection_acknowledged`
- `water_leak_detection_ack_rejected`

Event payloads include the event ID and relevant detector context. Burst events can report reasons such as `absolute_flow` or `rapid_rise`.

## Documentation

- [Installation and updates](docs/INSTALLATION.md)
- [Configuration reference](docs/CONFIGURATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Changelog](CHANGELOG.md)
- [v1.0.2 release notes](RELEASE_NOTES_1.0.2.md)
- [Release procedure](docs/RELEASING.md)
- [Project Wiki](https://github.com/BeGiBue/homeassistant-water-leak-detection/wiki)
- [Technical specification and roadmap](SPEC.md)

## Release status

Version 1.0.2 is the current stable release and includes the complete original v0.1 → v0.3 backend roadmap plus the improved notification-recipient overview:

- **v0.1.0** — detection core and backend entities
- **v0.2.0** — notifications, device acknowledgement, and geofencing
- **v0.3.0** — adaptive learning and hydraulic plausibility

The previously published **0.3.0** GitHub release was tagged before the Home Assistant integration-type correction and still declared itself as a `helper`. **1.0.2 continues the corrected stable line introduced with 1.0.0 and explicitly declares `integration_type: "service"`, so Home Assistant loads it as a normal integration rather than a Helper.**

The release is validated against Home Assistant 2026.9.4 / Python 3.14.2 with compile checks, Ruff, JSON validation, and automated tests.


## License

Water Leak Guard is licensed under the **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**.

See [LICENSE](LICENSE) for the complete license text.
