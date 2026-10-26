"""Compare two redacted, disabled-only capability catalog exports offline."""
import argparse
import json
from pathlib import Path


def read_catalog(path: str | Path) -> set[str]:
    source = Path(path)
    if source.is_symlink():
        raise ValueError("Catalog input must not be a symbolic link")
    if not source.is_file():
        raise ValueError("Catalog input must be a regular file")
    if source.stat().st_size > 1_048_576:
        raise ValueError("Catalog input exceeds 1 MiB")
    with source.open("rb") as stream:
        raw = stream.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("Catalog input exceeds 1 MiB")
    data = json.loads(raw.decode("utf-8"))
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
    parser.add_argument("--fail-on-change", action="store_true", help="Exit 2 if capability IDs changed")
    args = parser.parse_args()
    try:
        changes = compare_catalogs(args.before, args.after)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        parser.exit(1, f"Invalid catalog comparison: {type(exc).__name__}\n")
    print(json.dumps(changes, sort_keys=True))
    return 2 if args.fail_on_change and (changes["added"] or changes["removed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
