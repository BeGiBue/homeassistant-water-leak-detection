# Home Assistant Water Leak Detection

Backend-only Home Assistant custom integration for detecting abnormal water consumption and possible water leaks.

The implementation follows [`SPEC.md`](SPEC.md). Version **0.2.0** adds Companion notifications, device-based acknowledgement and Home-zone authorization on top of the v0.1 detector core. Adaptive hydraulic learning remains planned for v0.3.

## Current v0.2.0 features

- UI configuration via Config Flow.
- Select source sensors directly or discover compatible sensors from a Home Assistant device.
- Flow normalization to L/h and total consumption normalization to L.
- Separate Slow Leak, Low Flow, High Flow and Burst Leak state machines.
- Slow Leak defaults: 3 L/h for 60 min; active leak resets after 10 min below threshold.
- Low Flow defaults: starts at 150 L/h; detects after 60 min unless a 7 min quiet period below 20 L/h occurs.
- Provisional High Flow detector using flow + duration + accumulated event volume.
- Provisional absolute Burst Leak detector, kept fully independent of High Flow.
- Slow Leak and Low Flow can be disabled independently through dedicated HA switch entities.
- High Flow bypass that **never disables Burst Leak**.
- Persistent active detector state and bypass expiry across HA restarts.
- Independent **Water shutoff request** binary sensor for an external motorized valve automation.
- Expert settings for all v0.1 thresholds and detector-to-shutoff mapping.
- HA events for event start/end and shutoff-request changes.
- Multiple Home Assistant Companion notification recipients.
- Per-device notification target + `device_tracker.*` association.
- Critical Burst Leak payloads for iOS and Android when enabled per recipient.
- Actionable notifications with **Mute for this device** and **Acknowledge for everyone**.
- Global acknowledgement is authorized in backend code only when the requesting device is currently `home`.
- Trusted stationary Home devices (for example a shared iPad) can globally acknowledge while they remain in the Home zone.
- A device that transitions from `not_home` to `home` is notified again if the event is still active and not globally acknowledged.
- Acknowledgements are stored per event ID and survive Home Assistant restarts.
- Global acknowledgement never clears the physical detector state or the independent shutoff request.

## Installation

### HACS custom repository

1. Add this repository as a custom **Integration** repository in HACS.
2. Install **Home Assistant Water Leak Detection**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Home Assistant Water Leak Detection**.

### Manual

Copy `custom_components/water_leak_detection` into your Home Assistant `custom_components` directory and restart Home Assistant.

Minimum target: Home Assistant **2026.9.0**.

## Example source sensors

Reference installation:

- Flow: `sensor.wasserzahler_flow` in `m³/h`, resolution 0.001 m³/h = 1 L/h.
- Total: `sensor.wasserzahler_total`.

Supported core input units include L/h, L/min, L/s, m³/h, m³/min, m³/s and common compatible volume units.

## Entities

The integration creates a device with these backend entities:

- **Status** — overall detector state (`idle`, monitoring states, or active detector class).
- **Current flow** — normalized flow in L/h.
- **Leak alarm** — ON when any detector is active.
- **Water shutoff request** — independent endpoint intended for a valve automation.
- **Active event duration** — duration of the highest-priority active event.
- **Active event volume** — water used since that event began.
- **Slow Leak detection** — independent switch to enable/disable the Slow Leak detector.
- **Low Flow detection** — independent switch to enable/disable the Low Flow detector.
- **High flow bypass** — switch to start/cancel the bypass using the configured default duration.
- **High flow bypass duration** — editable default bypass duration in minutes.
- **High flow bypass remaining** — remaining bypass time in seconds.

### Why the bypass is not a `timer.*` entity

Home Assistant's `timer` domain is a helper integration rather than a normal entity platform that third-party integrations implement. The integration therefore exposes the same backend capability using HA-native controllable entities (switch + duration number + remaining-time sensor) and integration actions. It is directly usable from dashboards, scripts and automations without depending on a user-created helper.

## Companion notification recipients

Open the integration's **Configure** dialog and choose **Add notification device**. Each recipient stores:

- a display name,
- its `notify.mobile_app_*` service,
- the matching `device_tracker.*`,
- whether Burst Leak may use critical notifications,
- whether the device may globally acknowledge while it is Home,
- whether it is a trusted stationary Home device.

Recipients are deliberately device-based rather than only person-based. This supports users with multiple devices and shared Home devices.

Example:

- Personal iPhone: may mute an event for itself while away; may globally acknowledge after it is Home.
- Shared iPad that normally stays Home: mark it as a trusted stationary Home device and allow global acknowledgement. Any household member using that iPad can then acknowledge the active event for everyone.
- If the iPhone later changes from `not_home` to `home` while the event is still active and has not been globally acknowledged, the integration sends that alarm to the iPhone again.

### Acknowledgement semantics

**Mute for this device** only suppresses further notifications for that recipient and event ID. It does not affect other devices, detector state or shutoff request.

**Acknowledge for everyone** is accepted only when the configured tracker for the responding device is currently `home`. The authorization check happens in backend code. The physical leak event remains active until its detector reset condition is fulfilled.

Each new physical event gets a new event ID, so acknowledgement never permanently disables a detector class.

## Actions

### `water_leak_detection.start_high_flow_bypass`

Starts or restarts the High Flow bypass. `duration_minutes` is optional; if omitted, the current **High flow bypass duration** value is used.

```yaml
sequence:
  - action: water_leak_detection.start_high_flow_bypass
    data:
      duration_minutes: 240
```

If multiple integration instances exist, also provide `config_entry_id`.

### `water_leak_detection.cancel_high_flow_bypass`

Cancels the bypass immediately.

## Shutoff request

`binary_sensor.*_water_shutoff_request` is deliberately independent from alarm acknowledgement logic. It is intended as a stable backend endpoint for an optional motorized shutoff valve.

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

Use your actual entity IDs. Automatic physical shutoff is intentionally not enabled by this integration unless you explicitly build/configure it.

## Events

The integration fires:

- `water_leak_detection_event_started`
- `water_leak_detection_event_ended`
- `water_leak_detection_shutoff_requested`
- `water_leak_detection_shutoff_cleared`
- `water_leak_detection_acknowledged`
- `water_leak_detection_ack_rejected`

These complement persistent entities and can be consumed by advanced automations.

## Roadmap

See [`SPEC.md`](SPEC.md) for the binding design and definitions of done:

- **v0.1.0** — Core Detection & Backend
- **v0.2.0** — Notifications, Devices & Acknowledgement
- **v0.3.0** — Adaptive Detection & Hydraulic Model

## Development status

v0.2.0 implements the notification/device acknowledgement milestone. High Flow and Burst Leak still use provisional expert-configurable thresholds; learned seasonal maximum flow and the hydraulic DN/pressure model remain intentionally reserved for v0.3.0.
