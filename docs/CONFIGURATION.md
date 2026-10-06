# Configuration reference

## Reopening the configuration

After installation, open **Settings → Devices & services → Integrations → Water leak detection → Configure**.

The configuration remains editable and contains:

- **Measurement sources**
- **Notification recipients**
- **Expert settings**

The measurement-source form is also available through Home Assistant's **Reconfigure** action.

## Measurement sources

A flow-rate sensor is required. A cumulative consumption sensor is optional but recommended.

The config flow supports:

- direct selection of individual sensor entities,
- selecting a Home Assistant device and choosing compatible entities from it.

Internally:

- flow is normalized to L/h,
- cumulative consumption is normalized to L.

A missing or unavailable flow sensor is not treated as zero flow.

## Slow Leak

Default:

- threshold: 3 L/h
- detection time: 60 min
- reset: 10 min below threshold

Typical purpose: leaking toilet cistern, tiny continuous losses, small fitting leaks.

Slow Leak has its own enable/disable switch.

## Low Flow

Default:

- start threshold: 150 L/h
- detection time: 60 min
- quiet threshold: 20 L/h
- quiet/reset time: 7 min

Typical purpose: a tap left running.

Low Flow has its own enable/disable switch.

## High Flow

High Flow represents unusually high but potentially legitimate water use.

The effective threshold is adaptive and uses:

- the fixed base threshold,
- learned normal peak usage when confidence permits,
- optional manually known normal maximum,
- hydraulic plausibility limits.

High Flow can be temporarily bypassed. This bypass does not disable Burst Leak.

## Burst Leak

Burst Leak is intended for major failures such as a burst pipe or failed hose.

Detection combines:

- adaptive absolute flow threshold,
- rapid rate-of-rise detection,
- learned household context,
- hydraulic plausibility.

Burst Leak remains active during High Flow bypass.

## High Flow bypass

Backend controls:

- High Flow bypass switch
- High Flow bypass duration number
- High Flow bypass remaining sensor
- `water_leak_detection.start_high_flow_bypass`
- `water_leak_detection.cancel_high_flow_bypass`

The bypass expires automatically and its expiry is persisted across Home Assistant restarts.

## Companion notification devices

Recipients can be selected during initial setup and managed later under **Configure → Notification recipients**.

Each recipient is configured independently with:

- display name,
- `notify.mobile_app_*` service,
- matching `device_tracker.*`,
- critical-alert permission,
- global acknowledgement permission while Home,
- optional trusted stationary Home-device flag.

### Personal mute

An authorized notification device can mute the current event for itself.

This does not clear:

- the detector state,
- the event,
- notifications on other devices,
- the shutoff request.

### Global acknowledgement

Global acknowledgement is accepted only when:

- the device is configured to allow it, and
- its assigned `device_tracker.*` currently reports `home`.

Authorization is checked by backend logic, not only by which notification button is shown.

### Trusted stationary Home device

A shared tablet that normally remains Home can be marked as trusted stationary.

This allows the device itself to act as a Home terminal for global acknowledgement without assuming which person is holding it.

### Return Home

When a configured notification device transitions from away to Home while an event is still active and not globally acknowledged, it is notified again.

Any per-device mute for that event is cleared when the device returns Home.

## Adaptive learning

Default learning window: 30 days.

The learner admits completed normal-use episodes and excludes suspicious events and bypass periods.

Confidence states:

- `insufficient`
- `learning`
- `reliable`

The model combines recent and longer-term references to allow seasonal adaptation.

Use `water_leak_detection.reset_learning` to clear learned normal-flow samples intentionally.

## Hydraulic settings

Reference defaults:

- nominal diameter: 25 mm / DN25
- static pressure: 3.5 bar

These settings form a plausibility envelope only. They are not an exact theoretical maximum-flow calculation.

## Shutoff request

Each detector can be configured independently to request shutoff.

The **Water shutoff request** entity is independent from acknowledgement.

Typical conservative behavior:

- Slow Leak: no shutoff by default
- Low Flow: no shutoff by default
- High Flow: no shutoff by default
- Burst Leak: shutoff request enabled by default

Physical valve control is intentionally external/opt-in so users can decide which existing `valve.*` or `switch.*` should react.

## Expert settings

The integration options expose detector thresholds, durations, reset limits, bypass duration, hydraulic context, learning parameters, and detector-to-shutoff mapping.

Change these values only with measured household data where possible.
