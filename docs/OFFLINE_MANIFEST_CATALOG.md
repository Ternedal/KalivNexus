# Offline manifest catalog (prototype)

> **Status: offline prototype with automated contract tests; integration
> design remains a proposal.** No runtime, API compatibility, deployed service
> or production readiness is asserted by this document.

**Provenance.** This is the part of `main`'s `README.md` (at `6e25c635e`) that
[ECOSYSTEM_BOUNDARIES.md](ECOSYSTEM_BOUNDARIES.md) did not copy: the status
line, "Suggested documentation roadmap", "Current prototype" and "Compare
offline catalog snapshots". It moved here when `main` and the v0.50.0 baseline
were merged (#22), because the repository's `README.md` is now the original
v0.50.0 archive README, kept byte for byte. Changes from `main`'s text:

- The trust claim is scoped to **this component**. `main`'s README said that
  neither implementation "connects to ModelRig, resolves secrets or calls
  external APIs". That holds for the catalog, but not for the repository,
  which now also contains the v0.50.0 runtime under `nexus/` (MCP gateway,
  egress relay).
- The literal `\n\n` in the catalog paragraph is fixed.
- The `--prefix` example is fixed. It had run two commands together.
- The test commands use the shared environment (`.[test,catalog]`).

Purpose, ecosystem boundaries, the proposed architecture and the security
requirements are in [ECOSYSTEM_BOUNDARIES.md](ECOSYSTEM_BOUNDARIES.md). The
manifest format is in [CAPABILITY_MANIFEST_V0_1.md](CAPABILITY_MANIFEST_V0_1.md).

## What the catalog is, and what it touches

| Part | Where | Network, secrets, ModelRig |
| --- | --- | --- |
| JSON Schema for manifest v0.1 | `schemas/` | None |
| Manifest validator | `scripts/validate_manifest.py` | None |
| In-memory default-deny catalog, SQLite registry prototype | `scripts/manifest_registry.py`, `scripts/persistent_registry.py` | None; SQLite is a local file |
| Fixture-only read adapter and redacted fixture audit | `scripts/read_only_adapter.py`, `scripts/adapter_fixture_audit.py` | None |
| Review-token prototypes | `scripts/review_tokens.py`, `scripts/review_authorization.py` | None; test HMAC only |
| Catalog CLI and snapshot comparison | `scripts/list_manifest_catalog.py`, `scripts/compare_manifest_catalogs.py` | None |

**None of the parts above** connects to ModelRig, resolves secrets or calls
external APIs. This statement covers the catalog only. The v0.50.0 runtime in
`nexus/` is a separate component with its own network code. Its boundaries
are described in `README.md` and enforced by the Docker isolation workflow.

## Current prototype (not an active broker)

The catalog consists of:

- a draft JSON Schema;
- a Python manifest validator;
- an in-memory default-deny catalog;
- a **SQLite-backed prototype** with registration, revocation and lifecycle
  events;
- a fixture-only read adapter;
- review-token prototypes.

The read adapter provides:

- schema checks;
- strict JSON object and array validation;
- cycle and depth rejection;
- a 1 MiB limit on the serialized payload;
- defensive copies;
- redacted in-memory audit events with optional correlation IDs.

The review-token prototypes exercise scoped HMAC claims and replay prevention
in tests. They are **not** production identity or approval integration.

Limits:

- Neither catalog has an enable path or an execution path.
- The SQLite database persists local state, but it is not a hardened,
  tamper-proof audit log or a multi-user approval system.
- Offline fixture handlers are ordinary injected Python callables, and they
  are **not sandboxed**. Do not use untrusted handlers.
- The JSON size check serializes the input. It is not a complete bound on
  memory allocation.

To run the local contract tests (Python 3.11 or 3.12):

```bash
python -m pip install -e '.[test,catalog]'
python -m pytest -q
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/validate_manifest.py examples/weather-readonly.manifest.json
python -m scripts.list_manifest_catalog examples
# Export redacted catalog metadata to a new file (fails if it exists):
python -m scripts.list_manifest_catalog examples --output catalog.json
# Optionally filter displayed capability IDs after validating every manifest:
python -m scripts.list_manifest_catalog examples --prefix weather.
# Or inspect one manifest file instead of a directory:
python -m scripts.list_manifest_catalog examples/weather-readonly.manifest.json
```

`pytest` runs both suites: the v0.50.0 runtime tests and the catalog's
`unittest` tests.

The catalog command validates local manifests and prints only capability IDs
and their disabled status. It does not activate or invoke providers.

The [validate-manifests workflow](../.github/workflows/validate-manifests.yml)
and the [CI workflow](../.github/workflows/ci.yml) are configured to run these
checks. A passing CI run must be confirmed separately.

## Compare offline catalog snapshots

After exporting two disabled-only catalog JSON snapshots, you can compare
their capability IDs without contacting providers:

```bash
python -m scripts.compare_manifest_catalogs catalog-before.json catalog-after.json
```

The output contains sorted `added` and `removed` ID arrays. It does not
compare configuration, authorization or live availability.

Options:

- `--fail-on-change` is for CI drift detection. The command still prints the
  JSON diff, then exits `2` if any capability ID was added or removed.
  Unchanged catalogs exit `0`, and invalid inputs exit `1`.
- `--summary` adds `counts.added` and `counts.removed` next to the sorted
  capability IDs. It does not change the exit codes.

## Suggested documentation roadmap

- [x] [Draft architecture decisions](ARCHITECTURE_DECISIONS.md) for authority, manifest trust, lifecycle and release gates (not yet implementation decisions)
- [x] Draft JSON Schema, example manifest and local validator (prototype only)
- [x] Offline read-only fixture adapter, contract tests and redacted in-memory fixture audit (not a provider SDK)
- [ ] ModelRig integration and approval flow
- [ ] Installation, configuration and rollback runbooks
- [ ] Observability, costs, quotas and failure modes
- [ ] End-to-end tests on exact pinned revisions

## Release discipline

Document **proposed**, **implemented**, **automated-test verified**,
**physically tested** and **released** separately. This document describes a
prototype and a proposal, not delivered functionality.
