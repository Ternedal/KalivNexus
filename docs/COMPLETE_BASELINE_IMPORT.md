# Complete v0.50.0 baseline import

The repository's `bootstrap/v0.50.0-baseline` branch is a **work in progress**.
Do not merge it into `main` until all source files are reconciled and the
repository's own CI checks pass.

## One-shot source reconciliation

`scripts/sync_baseline.py` compares the original release archive against the
current branch by **Git blob SHA**, so it detects modified files as well as
missing files. It creates a single non-force commit on the specified branch,
preserving additional repository-only files.

Prerequisites: Python 3.11+, the original `kaliv-nexus-v0.50.0.zip` archive,
and a fine-grained GitHub token with **Contents: Read and write** permission
restricted to `Ternedal/KalivNexus`.

Run from a trusted machine:

```bash
export GITHUB_TOKEN='YOUR_FINE_GRAINED_TOKEN'
python scripts/sync_baseline.py ./kaliv-nexus-v0.50.0.zip
# Inspect every reported path first; this command makes no changes.
python scripts/sync_baseline.py ./kaliv-nexus-v0.50.0.zip --apply
unset GITHUB_TOKEN
```

The ZIP must contain the original `kaliv-nexus/` directory. Do not commit
the token or store it in a shell script. The tool refuses to modify `main`.
It does not run tests, verify Docker isolation, or publish a release.

## Verification after import

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

Review GitHub Actions on the branch and check both Python tests and Docker
isolation jobs. A passing run on the **original ZIP** is not evidence that the
imported branch passes. In particular, verify `nexus/main.py` and every test
are present before treating the branch as deployable.

## Current limitation

This chat session does not have a GitHub API token in its local execution
environment. The GitHub connector can write individual files, but cannot
directly access the local ZIP archive. Consequently, publishing the importer
is **not** the same as executing the complete import.
