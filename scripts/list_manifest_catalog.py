"""Inspect validated manifests offline; registration never activates a provider."""
import argparse
import json
from pathlib import Path

from scripts.manifest_registry import ManifestRegistry


def build_catalog(paths: list[str]) -> list[dict[str, str]]:
    """Load and validate each manifest; return only non-sensitive metadata."""
    registry = ManifestRegistry()
    for path in paths:
        registry.register_file(Path(path))
    return registry.list_capabilities()


def main() -> int:
    parser = argparse.ArgumentParser(description="List disabled KalivNexus capabilities from local manifests")
    parser.add_argument("manifests", nargs="+", help="Local manifest JSON files")
    args = parser.parse_args()
    try:
        entries = build_catalog(args.manifests)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Invalid manifest catalog: {type(exc).__name__}\n")
    print(json.dumps({"capabilities": entries}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
