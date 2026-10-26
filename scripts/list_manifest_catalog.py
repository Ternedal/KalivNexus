"""Inspect validated manifests offline; registration never activates a provider."""
import argparse
import json
from pathlib import Path

from scripts.manifest_registry import ManifestRegistry


def build_catalog(paths: list[str]) -> list[dict[str, str]]:
    """Load explicit files or a directory of *.manifest.json files, without recursion."""
    registry = ManifestRegistry()
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            files = sorted(path.glob("*.manifest.json"))
            if not files:
                raise ValueError("Manifest directory contains no *.manifest.json files")
        else:
            files = [path]
        for file in files:
            if not file.is_file():
                raise ValueError("Manifest path is not a regular file")
            registry.register_file(file)
    return registry.list_capabilities()


def main() -> int:
    parser = argparse.ArgumentParser(description="List disabled KalivNexus capabilities from local manifests")
    parser.add_argument("manifests", nargs="+", help="Local manifest JSON files or directories containing *.manifest.json files")
    args = parser.parse_args()
    try:
        entries = build_catalog(args.manifests)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Invalid manifest catalog: {type(exc).__name__}\n")
    print(json.dumps({"capabilities": entries}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
