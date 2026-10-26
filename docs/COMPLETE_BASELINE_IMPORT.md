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

## Limitation at the time of writing (resolved 2026-10-26, see the end of this page)

This chat session does not have a GitHub API token in its local execution
environment. The GitHub connector can write individual files, but cannot
directly access the local ZIP archive. Consequently, publishing the importer
is **not** the same as executing the complete import.

## Verified original-source test baseline (2026-10-25)

The flat-root verified v0.50.0 source ZIP was extracted to a temporary directory
and tested with `NEXUS_ADMIN_TOKEN=test-secret python -m pytest -q`:

```text
247 passed in 10.23s
```

This result applies **only to the extracted source ZIP**, not to the incomplete
GitHub bootstrap branch. The original release archive and the flat-root
verified-source archive are both supported by the sync script. The importer
must be run to reconcile all 92 original files, then branch CI must pass before
merging. Never interpret this source-archive result as a branch CI pass.

## Pinned archive digests (2026-10-26)

Two valid archive layouts exist, with **different ZIP SHA-256 digests** but the
same intended 92-file source tree. Supply the matching digest to prevent
accidentally importing the wrong archive:

| Archive | SHA-256 |
| --- | --- |
| `kaliv-nexus-v0.50.0.zip` (original `kaliv-nexus/` prefix) | `0d7316678733c8f4d7fdfe59f2c59afe02cd61562a05b551f8e61b334fe403e1` |
| `KalivNexus-v0.50.0-verified-source.zip` (flat root) | `9d4215ee40696860221ed3fa8ee7cb9bbe659339ef7a918c280d786da329e60f` |

Example dry-run for the verified flat-root archive:

```bash
python scripts/sync_baseline.py ./KalivNexus-v0.50.0-verified-source.zip \\
  --archive-sha256 9d4215ee40696860221ed3fa8ee7cb9bbe659339ef7a918c280d786da329e60f
```

Only after reviewing the dry-run, repeat with `--apply` using a token scoped
to this repository. Expected Git blob SHA of `nexus/main.py`:
`338d502ea3f9e0353157226c2d60910c6d26807a`.

## Reconciliation result (2026-10-26, #22)

The import has been executed on `bootstrap/v0.50.0-baseline`, with git instead
of `sync_baseline.py --apply`. The resulting tree is the same, and no token was needed.

- **Archive:** `KalivNexus-v0.50.0-verified-source.zip`, 89,318 bytes, SHA-256
  `9d4215ee40696860221ed3fa8ee7cb9bbe659339ef7a918c280d786da329e60f`, equal to the pin
  above. It has 92 entries, a flat root, and no directories, symlinks, unsafe
  paths or encryption.
- **Before the import:** compared with `df84ad519`, 83 files were identical,
  8 differed and 1 was missing (`nexus/main.py`, blob
  `338d502ea3f9e0353157226c2d60910c6d26807a`, as pinned). Seven of the eight
  differences were whitespace or docstring only. The other two were
  `README.md` and `.github/workflows/ci.yml`.
- **Commit `bf63224af`, the verbatim reconciliation:** `scripts/verify_baseline.py`,
  run on a clean worktree of this commit, reports 92 matching, 0 missing,
  0 modified, **PASS**. `python -m pytest -q` reports 285 passed.
- **Commit `faf1dd713`, the one declared divergence:** `.github/workflows/ci.yml`
  keeps the repository's hardened workflow (`permissions: contents: read`,
  concurrency, a 15-minute timeout, `compileall`). Restoring the archive's minimal
  workflow would have weakened CI. At that commit, `verify_baseline.py`
  reported exactly one `DIFFERENT` file, and it was this one.
- **`README.md`:** the original archive README is kept on this branch. The
  ecosystem and authority text that `main` had in its README is preserved
  verbatim in [ECOSYSTEM_BOUNDARIES.md](ECOSYSTEM_BOUNDARIES.md) and marked
  as a proposal.
- **Docker isolation:** the v0.50.0 probe could not parse `/proc/net/ipv6_route`,
  so the isolation job always failed. Fixed by #37 (`411c29d35`), after a
  security cross-review. CI and Docker isolation are both green on this branch.

### Declared divergences from the archive

`scripts/verify_baseline.py` reports these files as `DIFFERENT`. Each one is
intentional. Any other `DIFFERENT` or `MISSING` file is a regression.

| File | Why | Since |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Repository CI hardening kept over the minimal original | `faf1dd713` |
| `nexus/egress_isolation_probe.py` | Kernel-format IPv6 route parsing; exemption for lo REJECT only | #37, `411c29d35` |
| `tests/test_egress_isolation_probe.py` | Tests for the above, with real kernel fixtures | #37, `411c29d35` |

Merging this branch into `main` still requires Anders' explicit approval.
