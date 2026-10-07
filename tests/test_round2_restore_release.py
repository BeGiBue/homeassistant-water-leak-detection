"""Fail-safe persisted events and actual release shell logic with local command fakes."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_manager_runtime import report

from custom_components.water_leak_detection.const import DOMAIN, DetectorKind, DetectorPhase
from custom_components.water_leak_detection.engine import DetectionEngine
from custom_components.water_leak_detection.manager import WaterLeakManager

BASE = datetime(2026, 10, 7, tzinfo=UTC)


def confirmed_runtime():
    return {
        "phase": "active", "event_id": "burst_leak_confirmed", "started_at": BASE.isoformat(),
        "detected_at": BASE.isoformat(), "estimated_volume_l": 10, "reason": "absolute_flow",
        "quiet_since": None,
    }


@pytest.mark.parametrize("field,value", [
    ("phase", "corrupt"), ("phase", None), ("phase", "idle"), ("event_id", []),
    ("detected_at", {}), ("event_id", "   "), ("reason", []), ("estimated_volume_l", "nan"),
    ("quiet_since", "bad"),
])
async def test_f16_individual_corruption_keeps_confirmed_safety_and_setup(
    runtime_hass, runtime_entry, measurement_clock, field, value
):
    raw = confirmed_runtime()
    raw[field] = value
    manager = WaterLeakManager(runtime_hass, runtime_entry)
    await manager._store.async_save({"engine": {"runtimes": {"burst_leak": raw}}})
    report(runtime_hass, measurement_clock, "unavailable")
    runtime_hass.data.setdefault(DOMAIN, {})[runtime_entry.entry_id] = manager
    await manager.async_setup()
    runtime = manager.engine.runtimes[DetectorKind.BURST_LEAK]
    assert runtime.phase is DetectorPhase.ACTIVE
    assert runtime.event_id
    assert manager.engine.snapshot().shutoff_request
    assert runtime.quiet_since is None


@pytest.mark.parametrize("fields", [
    {"phase": [], "event_id": None},
    {"phase": "bad", "reason": None, "estimated_volume_l": -1},
    {"event_id": [], "detected_at": "bad", "reason": {}},
])
def test_f16_multiple_corrupt_fields_preserve_remaining_confirmation(fields):
    raw = confirmed_runtime()
    raw.update(fields)
    engine = DetectionEngine()
    engine.restore({"runtimes": {"burst_leak": raw}})
    assert engine.snapshot().alarm_active
    assert engine.snapshot().shutoff_request


@pytest.mark.parametrize("raw", [
    {}, {"phase": "bad"}, {"phase": "monitoring", "started_at": BASE.isoformat()},
    {"phase": [], "event_id": "meaningless", "estimated_volume_l": 1},
])
def test_f16_missing_or_unconfirmed_data_does_not_create_alarm(raw):
    engine = DetectionEngine()
    engine.restore({"runtimes": {"burst_leak": raw}})
    assert not engine.snapshot().alarm_active
    assert not engine.snapshot().shutoff_request


@pytest.mark.parametrize("version", ["1.0.1", "1.0.2"])
@pytest.mark.parametrize("tag,release,success,creates", [
    ("none", False, True, 1), ("right", False, True, 1), ("wrong", False, False, 0),
    ("right", True, True, 0), ("wrong", True, False, 0), ("none", True, False, 0),
    ("lookup_error", False, False, 0),
])
def test_f20_actual_script_checks_tag_even_without_release(
    tmp_path, version, tag, release, success, creates
):
    sha = "a" * 40
    executable = tmp_path / "bin"
    executable.mkdir()
    log = tmp_path / "commands.jsonl"
    git = executable / "git"
    git.write_text('''#!/usr/bin/env python3
import json,os,sys
with open(os.environ['TEST_LOG'],'a') as f: f.write(json.dumps(['git']+sys.argv[1:])+'\\n')
if sys.argv[1]=='ls-remote':
 sys.exit({'none':2,'lookup_error':128}.get(os.environ['TEST_TAG'],0))
if sys.argv[1]=='rev-parse':
 print(os.environ['GITHUB_SHA'] if os.environ['TEST_TAG']=='right' else 'b'*40)
''')
    gh = executable / "gh"
    gh.write_text('''#!/usr/bin/env python3
import json,os,sys
with open(os.environ['TEST_LOG'],'a') as f: f.write(json.dumps(['gh']+sys.argv[1:])+'\\n')
if sys.argv[2]=='view': sys.exit(0 if os.environ['TEST_RELEASE']=='1' else 1)
''')
    git.chmod(0o755)
    gh.chmod(0o755)
    env = {**os.environ, "PATH": str(executable) + os.pathsep + os.environ["PATH"],
           "GITHUB_SHA": sha, "GITHUB_REPOSITORY": "local/review", "TEST_TAG": tag,
           "TEST_RELEASE": str(int(release)), "TEST_LOG": str(log)}
    script = Path(".github/release_checked_commit.sh").resolve()
    result = subprocess.run(["bash", str(script), version, "--target", sha],
                            env=env, text=True, capture_output=True, timeout=5)
    assert (result.returncode == 0) is success
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    creation = [cmd for cmd in commands if cmd[:3] == ["gh", "release", "create"]]
    assert len(creation) == creates
    if creation:
        assert creation[0][creation[0].index("--target") + 1] == sha
        # A re-run with the newly created matching tag/release does not create again.
        env.update(TEST_TAG="right", TEST_RELEASE="1")
        again = subprocess.run(["bash", str(script), version, "--target", sha],
                               env=env, text=True, capture_output=True, timeout=5)
        assert again.returncode == 0
        commands = [json.loads(line) for line in log.read_text().splitlines()]
        assert sum(cmd[:3] == ["gh", "release", "create"] for cmd in commands) == 1


def test_f16_corrupt_detection_time_alone_does_not_promote_monitoring():
    engine = DetectionEngine()
    engine.restore({"runtimes": {"burst_leak": {
        "phase": "monitoring", "event_id": None, "started_at": BASE.isoformat(),
        "detected_at": BASE.isoformat(), "reason": "absolute_flow", "estimated_volume_l": 1,
    }}})
    assert not engine.snapshot().alarm_active
