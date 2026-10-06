# Home Assistant Water Leak Detection 0.3.1

Version 0.3.1 is a Home Assistant UI, localization, and configuration bugfix release on top of 0.3.0.

## Fixed

- The integration now appears as a normal integration under **Settings → Devices & services → Integrations** instead of being hidden as a helper.
- The integration follows the configured Home Assistant language.
- Complete German and English runtime translations are included.
- Integration title, device name, entity names, translated states, service actions, and Companion notification texts are localized.
- Notification recipients can be added during initial setup.
- Notification recipients can be added, edited, or removed later through **Configure**.
- Expert detector settings remain available later through **Configure**.
- Flow and optional cumulative-consumption source sensors can be changed later through **Reconfigure**.
- Options changes reload the integration using Home Assistant's native reloadable options flow.

## German UI

When Home Assistant is configured for German, the integration uses German UI text automatically, including examples such as:

- **Wasserleck-Erkennung**
- **Aktueller Durchfluss**
- **Leckalarm**
- **Absperranforderung**
- **Gelernter Maximaldurchfluss**
- **Lernzuverlässigkeit**
- **Unzureichend gelernt**
- **Lernen aktiv**
- **Zuverlässig gelernt**

Companion notification titles, messages, and action buttons also follow the configured Home Assistant language.

## Compatibility

The detection and safety model is unchanged from 0.3.0:

- no detector threshold changes,
- no adaptive-learning algorithm changes,
- no High Flow bypass behavior changes,
- no Burst Leak behavior changes,
- no acknowledgement or shutoff semantic changes.

Existing integration storage, acknowledgement state, bypass state, and learned history remain compatible.

## Upgrade from 0.3.0

1. Update to **0.3.1** in HACS.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Integrations** and verify **Wasserleck-Erkennung / Water leak detection** is listed.
4. Open **Configure** to manage notification recipients and expert settings.
5. Use **Reconfigure** if the measurement-source entities need to be changed.

Home Assistant stores entity-registry names. If entities created by 0.3.0 continue to show an old English name after updating, do not delete your configuration immediately. First restart Home Assistant and reload the integration. User-renamed entities are intentionally not overwritten.

## Validation

Validated against Home Assistant 2026.9.4 / Python 3.14.2:

- Hassfest: passed
- Ruff: passed
- JSON validation: passed
- Python compile: passed
- Pytest: 87 passed

## Installation

Recommended HACS repository:

`https://github.com/BeGiBue/homeassistant-water-leak-detection`

Minimum Home Assistant: 2026.9.0.
