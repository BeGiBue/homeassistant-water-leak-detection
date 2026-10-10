# Water Leak Guard 1.0.3

Version 1.0.3 is a safety and reliability release built from the seven reviewed correction rounds after 1.0.2.

## What changed

### Deterministic measurement evidence

Leak timing is now based only on consecutive fresh, valid flow reports.

- Internal Home Assistant ticks never create leak or quiet evidence.
- Regular and irregular sensor report intervals work without cadence learning.
- The optional expert maximum report gap is deterministic.
- Intervals above an explicit maximum gap contribute zero time without deleting previously confirmed monitoring progress.

### Safer source outages

Temporary `unknown`, `unavailable`, negative or otherwise invalid flow observations no longer erase already confirmed Slow/Low/High monitoring progress.

Unknown time itself still contributes **zero** evidence. The first valid report after recovery also contributes zero time, so an outage can neither accelerate detection nor silently reset confirmed progress.

Burst handling remains conservative: an unconfirmed Burst candidate and Rapid-Rise history do not cross an observation gap, while already confirmed ACTIVE leaks and Water Shut Off requests remain active.

A real source change remains separate from a temporary outage and does not transfer unconfirmed evidence from one meter to another.

### Persistence, restore and notification hardening

This release also improves:

- bounded persistence and defensive restore handling,
- stale/out-of-order/invalid measurement handling,
- optional total-meter plausibility and rebasing,
- per-recipient notification delivery and acknowledgement races,
- live recipient updates and setup rollback,
- source-change isolation,
- release/tag integrity checks.

## Validation

The final repository state passed:

- **713 automated repository tests**,
- Ruff,
- Home Assistant hassfest,
- Python/JSON/YAML/Bash validation,
- scope and byte/AST regression checks.

The independent final acceptance review additionally ran **110 external tests** and reported:

- Critical: **0**
- High: **0**
- Medium: **0**
- Low: **0**

F05 and F15 were explicitly verified.

## Compatibility

- Existing configuration is preserved.
- Technical domain remains `water_leak_detection`.
- Integration type remains `service`.
- High Flow bypass still does not bypass Burst Leak detection.
- Acknowledgement does not end the physical leak state or an existing Water Shut Off request.

## Known documented limits

- Unconfirmed monitoring progress is intentionally not restored across a full Home Assistant restart; ACTIVE events are restored and offline time never counts as evidence.
- Without an explicit maximum report gap, a silent communications outage that never reports `unknown`/`unavailable` cannot be distinguished from a legitimately slow-reporting sensor.
- F02, F04, F08 and the detector-design work around Rapid Rise remain intentionally outside this bug-fix release and are planned for later feature work.

## License

This release is distributed under the **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**.
