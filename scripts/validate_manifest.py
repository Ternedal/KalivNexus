#!/usr/bin/env python3
"""Validate a proposed KalivNexus manifest. Does not activate providers."""
import argparse
import ipaddress
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "capability-manifest-v0.1.schema.json"


def validate_manifest(manifest: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(manifest)
    for field in ("input_schema", "output_schema"):
        Draft202012Validator.check_schema(manifest[field])
    for host in manifest["network"]["allowed_https_hosts"]:
        # JSON Schema hostname regex is only a first structural check.
        for label in host.split("."):
            if label.startswith("-") or label.endswith("-"):
                raise ValueError("Invalid DNS label in allowed host")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("Literal IP address is not allowed")
        if host.endswith((".localhost", ".internal", ".test", ".local")):
            raise ValueError("Non-public host suffix is not allowed")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    args = parser.parse_args(argv)
    failed = False
    for path in args.manifests:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            validate_manifest(manifest)
        except (OSError, ValueError, ValidationError, TypeError) as exc:
            failed = True
            print(f"INVALID {path}: {exc}", file=sys.stderr)
        else:
            print(f"VALID {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
