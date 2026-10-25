"""Offline safety checks for the complete-baseline importer."""
import importlib.util
import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_baseline.py"


def load_importer():
    spec = importlib.util.spec_from_file_location("sync_baseline", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive(tmp_path, entries):
    path = tmp_path / "baseline.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, body in entries.items():
            z.writestr(name, body)
    return path


def invoke(tmp_path, entries, *, apply=False):
    module = load_importer()
    zip_path = archive(tmp_path, entries)
    calls = []

    def fake_request(method, url, token, data=None):
        calls.append((method, url))
        if "/branches/" in url:
            return {"commit": {"sha": "a" * 40}}
        if "/git/trees/" in url:
            return {"sha": "b" * 40, "tree": []}
        raise AssertionError("Unexpected write request")

    args = ["sync_baseline.py", str(zip_path), "--min-files", "1"]
    if apply:
        args.append("--apply")
    with patch.object(sys, "argv", args), patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}), patch.object(module, "request", fake_request):
        return module.main(), calls


@pytest.mark.parametrize("unsafe", [
    "../escape.py", "/absolute.py", "dir/../escape.py", "dir\\escape.py",
])
def test_rejects_unsafe_zip_paths(tmp_path, unsafe):
    with pytest.raises(ValueError, match="Unsafe archive path"):
        invoke(tmp_path, {unsafe: "bad"})


def test_rejects_missing_critical_files(tmp_path):
    with pytest.raises(ValueError, match="Missing required baseline files"):
        invoke(tmp_path, {"README.md": "hello"})


def test_dry_run_never_writes(tmp_path):
    required = {
        "nexus/main.py": "pass",
        "nexus/mcp_relay_client.py": "pass",
        "tests/test_api.py": "pass",
        "pyproject.toml": "[build-system]",
    }
    _, calls = invoke(tmp_path, required)
    assert calls and all(method == "GET" for method, _ in calls)


def test_refuses_default_branch(tmp_path):
    module = load_importer()
    with patch.object(sys, "argv", ["sync_baseline.py", "unused.zip", "--branch", "main"]):
        with pytest.raises(SystemExit):
            module.main()
