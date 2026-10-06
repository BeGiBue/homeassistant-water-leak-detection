# Troubleshooting

## Integration is not shown after HACS installation

1. Confirm HACS downloaded the repository as an **Integration**.
2. Restart Home Assistant.
3. Verify that this directory exists:
   `<config>/custom_components/water_leak_detection`
4. Check Home Assistant logs for `water_leak_detection`.

## Flow sensor is rejected

The flow source must expose a supported unit.

Common supported flow units:

- L/h
- L/min
- L/s
- m³/h
- m³/min
- m³/s

The integration validates and normalizes the unit. An entity without a supported flow unit is rejected rather than guessed.

## Total sensor is not available

The cumulative consumption sensor is optional.

Without it, the integration can still detect flow patterns. Event volume may rely on integrated flow instead of meter-total deltas.

## Notification device cannot be added

The Companion App must already have registered a `notify.mobile_app_*` service in Home Assistant.

Also verify that a matching `device_tracker.*` exists for that device.

## Global acknowledgement is missing from a notification

The global acknowledgement action is only offered when the configured device tracker currently reports `home` and that recipient is allowed to globally acknowledge.

The backend validates the Home state again when the action is received.

## Global acknowledgement is rejected

Check:

- the recipient still exists in the integration options,
- its tracker entity is correct,
- the tracker state is exactly `home`,
- global acknowledgement is enabled for that recipient.

An away device can still mute the event for itself.

## Shared Home tablet

For a tablet that normally stays Home, enable the **trusted stationary Home device** option and global acknowledgement permission.

The integration authorizes the responding configured device, not the identity of the person holding it.

## High Flow bypass did not suppress an alarm

The High Flow bypass suppresses only High Flow.

It intentionally does not suppress:

- Slow Leak
- Low Flow
- Burst Leak

Burst Leak protection always remains active.

## Learned maximum looks wrong

Check the following sensors:

- Learned maximum flow
- Learning confidence
- Learning coverage
- Effective High Flow threshold
- Effective Burst Leak threshold

Suspicious High/Burst candidates and High Flow bypass periods are excluded from learning.

Use `water_leak_detection.reset_learning` if you intentionally want to restart the learning history.

## Source sensor becomes unavailable

Unavailable/unknown source values are not interpreted as zero flow.

The integration exposes source unavailability and suspends incomplete learning episodes instead of admitting them as normal data.

## Debug logging

Add temporary logger configuration in Home Assistant:

```yaml
logger:
  default: info
  logs:
    custom_components.water_leak_detection: debug
```

Restart or reload logging as appropriate, reproduce the problem, and remove debug logging afterward.

## Reporting an issue

Open:

`https://github.com/BeGiBue/homeassistant-water-leak-detection/issues`

Include:

- Home Assistant version
- integration version
- source sensor entity IDs and units
- relevant integration settings
- relevant log excerpts
- reproduction steps

Do not post private access tokens or other credentials.
