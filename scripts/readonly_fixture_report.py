"""Offline-only Home Assistant / NAS snapshot report.

Consumes local JSON fixtures; performs no network requests and never loads credentials.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

ALLOWED_SOURCES = {"home_assistant", "nas"}
MAX_BYTES = 1024 * 1024


def summarize_fixture(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("fixture_too_large")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or payload.get("source") not in ALLOWED_SOURCES:
        raise ValueError("invalid_source")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) > 1000:
        raise ValueError("invalid_records")
    for record in records:
        if not isinstance(record, dict) or type(record.get("healthy")) is not bool:
            raise ValueError("invalid_record")
    return {
        "source": payload["source"],
        "provenance": "local_fixture",
        "record_count": len(records),
        "healthy_count": sum(item["healthy"] for item in records),
        "unhealthy_count": sum(not item["healthy"] for item in records),
        "status": "fixture_only",
    }


def build_report(paths):
    results = [summarize_fixture(path) for path in paths]
    sources = [item["source"] for item in results]
    if len(set(sources)) != len(sources):
        raise ValueError("duplicate_source")
    return {
        "schema": "kaliv.nexus.readonly-fixture-report.v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "execution": "offline_fixture_only",
        "live_verified": False,
        "sources": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline read-only fixture report")
    parser.add_argument("fixtures", nargs="+", help="Local JSON fixture paths")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    result = json.dumps(build_report(args.fixtures), indent=2)
    if args.output == "-":
        print(result)
    else:
        Path(args.output).write_text(result + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
