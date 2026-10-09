"""Byte/AST scope guard against the verified round-5 baseline."""

import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "e3cb3d9570afc86c46926a24cf9cadcf6cdd8b31"
MANAGER = "custom_components/water_leak_detection/manager.py"
MUTABLE = {
    "README.md", "docs/CONFIGURATION.md", "docs/wiki/Persistenz-und-Betrieb.md",
    "custom_components/water_leak_detection/evidence.py", MANAGER,
    "custom_components/water_leak_detection/translations/en.json",
    "custom_components/water_leak_detection/translations/de.json",
    "tests/test_manager_runtime.py", "tests/test_round2_measurements.py",
    "tests/test_round3_measurements.py", "tests/test_round4_measurements.py",
    "tests/test_round5_evidence.py",
}


def original(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)


def functions(source):
    tree = ast.parse(source)
    return {
        node.name: node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def source_bytes(source, node):
    first = min([node.lineno] + [item.lineno for item in node.decorator_list])
    return b"".join(source.splitlines(keepends=True)[first - 1:node.end_lineno])


def verify_protected_files_and_non_f05_tests():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT)
    for path in paths.decode().splitlines():
        before = original(path)
        after = (ROOT / path).read_bytes()
        if path not in MUTABLE:
            assert before == after, path
        elif path.startswith("tests/"):
            old, new = functions(before), functions(after)
            for name, node in old.items():
                if not name.startswith("test_f05_"):
                    assert source_bytes(before, node) == source_bytes(after, new[name]), name
                    assert ast.dump(node) == ast.dump(new[name]), name
    # All F15 tests, learning.py, engine.py, release/control/notification files,
    # config_flow and settings are covered by the same whole-file byte guard.


def verify_manager_protected_methods_and_report_processing():
    before = original(MANAGER)
    after = (ROOT / MANAGER).read_bytes()
    old, new = functions(before), functions(after)
    permitted = {"_async_tick", "async_refresh", "_suspend_source", "source_max_age_seconds"}
    for name, node in old.items():
        if name not in permitted:
            assert source_bytes(before, node) == source_bytes(after, new[name]), name
            assert ast.dump(node) == ast.dump(new[name]), name
    # Replacing only the four permitted method spans must restore the entire
    # original file, protecting imports, class fields and all other source bytes.
    restored = after.splitlines(keepends=True)
    for name in sorted(permitted, key=lambda item: new[item].lineno, reverse=True):
        node = new[name]
        first = min([node.lineno] + [d.lineno for d in node.decorator_list])
        restored[first - 1:node.end_lineno] = source_bytes(before, old[name]).splitlines(
            keepends=True
        )
    assert b"".join(restored) == before
    # Source suspension only adds a measurement-chain break.
    assert ast.dump(ast.Module(body=old["_suspend_source"].body, type_ignores=[])) == ast.dump(
        ast.Module(body=new["_suspend_source"].body[1:], type_ignores=[])
    )
    # Legacy gap option semantics remain identical; only its docstring changes.
    assert [ast.dump(n) for n in old["source_max_age_seconds"].body[1:]] == [
        ast.dump(n) for n in new["source_max_age_seconds"].body[1:]
    ]
    # Control-plane entry and all validated report processing (including totals,
    # thresholds, learning and clock context) remain byte-identical.
    old_refresh = source_bytes(before, old["async_refresh"])
    new_refresh = source_bytes(after, new["async_refresh"])
    marker = b"        try:\n            flow = normalize_flow_lph("
    assert old_refresh[old_refresh.index(marker):] == new_refresh[new_refresh.index(marker):]
    assert [ast.dump(n) for n in old["async_refresh"].body[1:4]] == [
        ast.dump(n) for n in new["async_refresh"].body[1:4]
    ]
    old_tick, new_tick = old["_async_tick"], new["_async_tick"]
    new_tick.body[0].body.pop(0)  # Added zero-credit tick marker only.
    new_tick.body[0].body[0].value.value.keywords.clear()  # Disable tick measurements.
    assert ast.dump(old_tick) == ast.dump(new_tick)


def verify_translation_scope():
    for language in ("en", "de"):
        path = f"custom_components/water_leak_detection/translations/{language}.json"
        old = json.loads(original(path))
        new = json.loads((ROOT / path).read_bytes())
        new["options"]["step"]["expert"]["data"]["source_max_age_seconds"] = (
            old["options"]["step"]["expert"]["data"]["source_max_age_seconds"]
        )
        assert old == new


if __name__ == "__main__":
    verify_protected_files_and_non_f05_tests()
    verify_manager_protected_methods_and_report_processing()
    verify_translation_scope()
    print("Round-6 byte/AST protection: all three scope checks passed")
