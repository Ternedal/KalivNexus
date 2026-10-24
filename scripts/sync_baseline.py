#!/usr/bin/env python3
"""Reconcile a Kaliv Nexus baseline ZIP into a dedicated GitHub branch.

Uses only Python's standard library. Does not create PRs or touch main.
Requires GITHUB_TOKEN and an existing target branch.
"""
import argparse
import base64
import hashlib
import json
import os
import sys
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
    args = p.parse_args()
    if args.branch == "main":
        p.error("Refusing to modify main")
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
        for entry in sorted(z.namelist()):
            if not entry.startswith("kaliv-nexus/") or entry.endswith("/"):
                continue
            path = entry[len("kaliv-nexus/"):]
            if not path or path.startswith("/") or ".." in path.split("/"):
                raise ValueError("Unsafe archive path")
            data = z.read(entry)
            git_blob_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if existing.get(path) == git_blob_sha:
                continue
            try:
                source = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Non-UTF-8 file: {path}") from exc
            changes.append((path, source))
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
    new_tree = request("POST", base + "/git/trees", token, {"base_tree": head, "tree": elements})["sha"]
    commit = request("POST", base + "/git/commits", token, {
        "message": "bootstrap: reconcile complete v0.50.0 baseline from source archive",
        "tree": new_tree, "parents": [head],
    })["sha"]
    ref_url = base + "/git/refs/heads/" + urllib.parse.quote(args.branch, safe="/")
    # GitHub rejects non-fast-forward updates. No force push.
    request("PATCH", ref_url, token, {"sha": commit, "force": False})
    print(f"Committed {len(changes)} files: {commit}")


if __name__ == "__main__":
    main()
