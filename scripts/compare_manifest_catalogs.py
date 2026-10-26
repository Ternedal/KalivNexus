"""Compare two redacted, disabled-only capability catalog exports offline."""
import argparse
import json
from pathlib import Path


def read_catalog(path: str | Path) -> set[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if type(data) is not dict or set(data) != {"capabilities"}:
        raise ValueError("Catalog must contain only capabilities")
    entries = data["capabilities"]
    if type(entries) is not list:
        raise ValueError("Capabilities must be a list")
    identifiers: set[str] = set()
    for entry in entries:
        if (type(entry) is not dict or set(entry) != {"capability_id", "status"}
                or type(entry["capability_id"]) is not str
                or not entry["capability_id"] or entry["status"] != "disabled"):
            raise ValueError("Invalid disabled capability entry")
        identifier = entry["capability_id"]
        if identifier in identifiers:
            raise ValueError("Duplicate capability ID")
        identifiers.add(identifier)
    return identifiers


def compare_catalogs(before: str | Path, after: str | Path) -> dict[str, list[str]]:
    previous = read_catalog(before)
    current = read_catalog(after)
    return {"added": sorted(current - previous), "removed": sorted(previous - current)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two offline capability catalogs")
    parser.add_argument("before", help="Previously exported catalog JSON")
    parser.add_argument("after", help="Newly exported catalog JSON")
    args = parser.parse_args()
    try:
        changes = compare_catalogs(args.before, args.after)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"Invalid catalog comparison: {type(exc).__name__}\n")
    print(json.dumps(changes, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
