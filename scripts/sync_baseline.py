#!/usr/bin/env python3
"""Reconcile a Kaliv Nexus baseline ZIP into a dedicated GitHub branch.

Uses only Python's standard library. Does not create PRs or touch main.
Requires GITHUB_TOKEN and an existing target branch.
"""
import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import zipfile


def request(method, url, token, data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kaliv-nexus-baseline-sync",
    }
    payload = None if data is None else json.dumps(data).encode("utf-8")
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub {method} failed with HTTP {exc.code}") from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", help="Original v0.50.0 ZIP archive")
    p.add_argument("--repo", default="Ternedal/KalivNexus")
    p.add_argument("--branch", default="bootstrap/v0.50.0-baseline")
    p.add_argument("--apply", action="store_true", help="Actually write files; default is dry-run")
    p.add_argument("--min-files", type=int, default=92, help="Minimum source file count; default 92 for v0.50.0")
    args = p.parse_args()
    if args.branch in ("main", "master") or not args.branch.startswith("bootstrap/"):
        p.error("Refusing to modify protected default branches")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        p.error("GITHUB_TOKEN must be set")
    base = "https://api.github.com/repos/" + args.repo
    branch = request("GET", base + "/branches/" + urllib.parse.quote(args.branch, safe=""), token)
    head = branch["commit"]["sha"]
    tree = request("GET", base + "/git/trees/" + head + "?recursive=1", token)
    if tree.get("truncated"):
        raise RuntimeError("Repository tree was truncated; refusing partial comparison")
    existing = {entry["path"]: entry["sha"] for entry in tree["tree"] if entry["type"] == "blob"}
    changes = []
    with zipfile.ZipFile(args.archive) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        if len(names) < args.min_files:
            raise ValueError(f"Expected at least {args.min_files} source files, found {len(names)}")
        if len(names) > 2000:
            raise ValueError("Too many archive entries")
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entry names are not allowed")
        prefix = "kaliv-nexus/" if names and all(n.startswith("kaliv-nexus/") for n in names) else ""
        if not names or (prefix == "" and any(n.startswith("kaliv-nexus/") for n in names)):
            raise ValueError("Archive is empty or has mixed root layouts")
        paths = [entry[len(prefix):] for entry in names]
        if len(paths) != len(set(paths)):
            raise ValueError("Duplicate target paths are not allowed")
        total_uncompressed = 0
        for entry in sorted(names):
            path = entry[len(prefix):]
            if not path or path.startswith("/") or chr(92) in path or ".." in path.split("/"):
                raise ValueError("Unsafe archive path")
            info = z.getinfo(entry)
            if info.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError(f"Symlink entries are forbidden: {path}")
            total_uncompressed += info.file_size
            if total_uncompressed > 32 * 1024 * 1024:
                raise ValueError("Baseline archive exceeds 32 MB uncompressed")
            if info.file_size > 4 * 1024 * 1024:
                raise ValueError(f"Baseline file too large: {path}")
            data = z.read(entry)
            if len(data) != info.file_size:
                raise ValueError(f"Archive size mismatch: {path}")
            git_blob_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if existing.get(path) == git_blob_sha:
                continue
            try:
                source = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Non-UTF-8 file: {path}") from exc
            changes.append((path, source))
    required = {"nexus/main.py", "nexus/mcp_relay_client.py", "tests/test_api.py", "pyproject.toml"}
    missing_required = sorted(required - set(paths))
    if missing_required:
        raise ValueError("Missing required baseline files: " + ", ".join(missing_required))
    print(f"Branch: {args.branch} @ {head[:12]}")
    print(f"Different or missing baseline files: {len(changes)}")
    for path, _ in changes:
        print("  " + path)
    if not args.apply:
        print("Dry run only. Pass --apply to create a single commit.")
        return
    if not changes:
        print("Already matches the baseline.")
        return
    elements = [{"path": path, "mode": "100644", "type": "blob", "content": source}
                for path, source in changes]
    new_tree = request("POST", base + "/git/trees", token, {"base_tree": tree["sha"], "tree": elements})["sha"]
    commit = request("POST", base + "/git/commits", token, {
        "message": "bootstrap: reconcile complete v0.50.0 baseline from source archive",
        "tree": new_tree, "parents": [head],
    })["sha"]
    ref_url = base + "/git/refs/heads/" + urllib.parse.quote(args.branch, safe="/")
    current = request("GET", base + "/branches/" + urllib.parse.quote(args.branch, safe=""), token)["commit"]["sha"]
    if current != head:
        raise RuntimeError("Branch moved during import; refusing to update ref")
    # GitHub rejects non-fast-forward updates. No force push.
    request("PATCH", ref_url, token, {"sha": commit, "force": False})
    print(f"Committed {len(changes)} files: {commit}")


if __name__ == "__main__":
    main()
