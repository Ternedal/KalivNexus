#!/usr/bin/env python3
"""Compare a checked-out Kaliv Nexus tree against the original v0.50.0 ZIP.

Exit nonzero if any source file is missing or differs byte-for-byte.
Additional repository-only files are allowed.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import zipfile


def verify(archive: Path, checkout: Path):
    missing, changed, checked = [], [], 0
    with zipfile.ZipFile(archive) as source:
        items = [item for item in source.infolist() if not item.is_dir()]
        prefix = "kaliv-nexus/" if items and all(item.filename.startswith("kaliv-nexus/") for item in items) else ""
        if not items or (not prefix and any(item.filename.startswith("kaliv-nexus/") for item in items)):
            raise ValueError("Empty archive or mixed ZIP roots")
        names = [item.filename.removeprefix(prefix) for item in items]
        if len(names) != 92 or len(names) != len(set(names)):
            raise ValueError("Expected exactly 92 unique v0.50.0 source files")
        for item in sorted(items, key=lambda x: x.filename):
            name = item.filename.removeprefix(prefix)
            if (not name or name.startswith("/") or chr(92) in name
                    or "." in Path(name).parts or ".." in Path(name).parts):
                raise ValueError("Unsafe ZIP path")
            if item.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError("ZIP symlinks are forbidden")
            target = checkout / name
            if target.is_symlink():
                raise ValueError(f"Checkout symlink forbidden: {name}")
            if not target.is_file():
                missing.append(name)
                continue
            original_hash = hashlib.sha256(source.read(item)).digest()
            current_hash = hashlib.sha256(target.read_bytes()).digest()
            if original_hash != current_hash:
                changed.append(name)
            checked += 1
    if checked + len(missing) != 92:
        raise ValueError("Incomplete source verification")
    return checked, missing, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    args = parser.parse_args()
    checked, missing, changed = verify(args.archive, args.checkout)
    print(f"Matching source files: {checked}")
    print(f"Missing files: {len(missing)}")
    for name in missing:
        print("  MISSING", name)
    print(f"Modified files: {len(changed)}")
    for name in changed:
        print("  DIFFERENT", name)
    if missing or changed:
        sys.exit(1)
    print("PASS: checkout matches every file in the original source archive")


if __name__ == "__main__":
    main()
