"""Release/UI metadata tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "water_leak_detection"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_is_normal_service_integration() -> None:
    manifest = _load_json(INTEGRATION / "manifest.json")

    assert manifest["integration_type"] == "service"
    assert manifest["config_flow"] is True
    assert manifest["version"] == "0.3.0"


def test_runtime_translations_exist_for_english_and_german() -> None:
    english = _load_json(INTEGRATION / "translations" / "en.json")
    german = _load_json(INTEGRATION / "translations" / "de.json")

    assert english["title"] == "Water leak detection"
    assert german["title"] == "Wasserleck-Erkennung"
    assert german["device"]["water_leak_detection"]["name"] == "Wasserleck-Erkennung"


def test_all_exposed_entity_translation_keys_have_german_names() -> None:
    german = _load_json(INTEGRATION / "translations" / "de.json")

    expected = {
        "sensor": {
            "status",
            "current_flow",
            "active_event_duration",
            "active_event_volume",
            "high_flow_bypass_remaining",
            "learned_maximum_flow",
            "learning_confidence",
            "learning_coverage",
            "hydraulic_reference_flow",
            "effective_high_threshold",
            "effective_burst_threshold",
        },
        "binary_sensor": {"leak_alarm", "shutoff_request"},
        "switch": {
            "slow_leak_detection",
            "low_flow_detection",
            "high_flow_bypass",
        },
        "number": {"high_flow_bypass_duration"},
    }

    for platform, keys in expected.items():
        translated = german["entity"][platform]
        for key in keys:
            assert translated[key]["name"]


def test_setup_and_options_recipient_translations_exist() -> None:
    german = _load_json(INTEGRATION / "translations" / "de.json")

    config_steps = german["config"]["step"]
    option_steps = german["options"]["step"]

    assert "notifications" in config_steps
    assert "add_initial_recipient" in config_steps
    assert "reconfigure" in config_steps
    assert "notifications" in option_steps
    assert option_steps["init"]["menu_options"]["notifications"]
