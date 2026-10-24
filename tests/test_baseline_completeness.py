"""Baseline completeness checks for the v0.50.0 bootstrap branch.

These checks intentionally fail until the original application entry point and
the key runtime modules are imported. They do not claim behavioral equivalence.
"""
from importlib.util import find_spec
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MODULES = (
    "nexus.main",
    "nexus.mcp_network",
    "nexus.mcp_client",
    "nexus.mcp_worker",
    "nexus.mcp_relay_client",
    "nexus.mcp_pipeline",
    "nexus.mcp_connections",
    "nexus.mcp_credentials",
    "nexus.mcp_reconcile",
    "nexus.mcp_discovery",
    "nexus.egress_proxy",
    "nexus.executor",
)

REQUIRED_TEST_FILES = (
    "tests/test_api.py",
    "tests/test_mcp_client.py",
    "tests/test_mcp_network.py",
    "tests/test_mcp_pipeline.py",
    "tests/test_mcp_relay_pipeline.py",
    "tests/test_mcp_connections.py",
    "tests/test_mcp_reconcile.py",
    "tests/test_executor.py",
    "tests/test_egress_proxy.py",
)


@pytest.mark.parametrize("module", REQUIRED_MODULES)
def test_required_module_is_present(module):
    path = ROOT / (module.replace(".", "/") + ".py")
    assert path.is_file(), f"Baseline module missing: {path.relative_to(ROOT)}"


@pytest.mark.parametrize("path", REQUIRED_TEST_FILES)
def test_required_test_file_is_present(path):
    assert (ROOT / path).is_file(), f"Baseline test missing: {path}"


def test_fastapi_entrypoint_has_expected_app():
    pytest.importorskip("nexus.main")
    from nexus.main import app
    from fastapi import FastAPI

    assert isinstance(app, FastAPI)
