# KalivNexus

Local-first API discovery, capability registry and guarded MCP inspection
prototype, intended for Kaliv/ModelRig. No ModelRig integration exists yet.

## What it is, and what it is not

KalivNexus is:

- a catalog of **unverified API leads** imported from the public
  [`cporter202/API-mega-list`](https://github.com/cporter202/API-mega-list)
  README (master/main fallback), normalized, deduplicated by URL, categorized
  and searchable;
- a content-addressed, immutable registry for OpenAPI and MCP `tools/list`
  metadata, with a manual review workflow (`discovered → reviewed → approved`,
  or `disabled`) and append-only audit records in SQLite;
- opt-in, read-only MCP inspection (initialize, `tools/list`, manifest
  reconciliation) through Python APIs and an experimental egress relay;
- an offline manifest catalog for the capability manifest v0.1 schema
  ([OFFLINE_MANIFEST_CATALOG.md](docs/OFFLINE_MANIFEST_CATALOG.md)).

KalivNexus is **not**:

- an active broker: MCP `tools/call` is disabled, and approval of an entry
  does not make it executable;
- integrated with ModelRig: no ModelRig client or tool-schema export exists;
- a gateway to LAN or Home Assistant devices: local home capabilities stay in
  ModelRig (option A in
  [PROPOSAL_LOCAL_HOME_CAPABILITIES.md](docs/PROPOSAL_LOCAL_HOME_CAPABILITIES.md));
- production-hardened: deploy only on a private host.

Imported links are leads, not working integrations. The Markdown parser is
heuristic and can include navigation or non-API links. Status `approved` is a
manual registry state, not a security certification.

## Status

| Item | State |
| --- | --- |
| Package version | 0.50.0 (`pyproject.toml`) |
| Releases and Git tags | None |
| Version reported by the app | FastAPI/OpenAPI reports `0.21.0` (`nexus/main.py`) and `nexus.__version__` is `0.2.0`. Both are values from the v0.50.0 archive and are pinned or kept unchanged (see [COMPLETE_BASELINE_IMPORT.md](docs/COMPLETE_BASELINE_IMPORT.md)). |
| Automated tests | `ci.yml`, `validate-manifests.yml` and `docker-isolation.yml` run on `main` and pull requests (`validate-manifests.yml` only when its paths change); check GitHub Actions for the latest result |
| Docker isolation | Smoke-tested in CI by a route/reachability probe; not a proof of isolation |
| Physical or production use | Not tested |

The relay pipeline `inspect_via_relay` uses the unattested `MCPRelayTransport`
and reports `isolation_verified: false`. `AttestedMCPRelayTransport` exists but
is not wired into the pipeline.

The history of every version up to v0.50.0 is in [CHANGELOG.md](CHANGELOG.md).

## Requirements and installation

- Python 3.11 or newer (CI uses 3.11 and 3.12; the Docker image uses 3.12)
- Docker with Compose v2, for the container setups

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,catalog]'
```

The `test` extra adds pytest. The `catalog` extra adds `jsonschema`, which
the offline manifest catalog and its tests import; `pytest -q` collects those
tests, so install both extras.

## Run

### Docker

```bash
cp .env.example .env
# Replace NEXUS_ADMIN_TOKEN with a secure random secret
# e.g. python -c 'import secrets; print(secrets.token_urlsafe(48))'
docker compose up -d --build
curl http://127.0.0.1:8088/healthz
curl -X POST http://127.0.0.1:8088/v1/import -H "Authorization: Bearer YOUR_TOKEN"
curl 'http://127.0.0.1:8088/v1/capabilities?q=weather'
```

`compose.yaml` publishes the API on `127.0.0.1:8088` only and stores the
database in the `nexus_data` volume (`/data/nexus.db`). Swagger UI:
http://127.0.0.1:8088/docs

### Local

```bash
export NEXUS_ADMIN_TOKEN='replace-with-long-random-secret'
uvicorn nexus.main:app --reload --port 8088
```

The database is created at `./data/nexus.db` unless `NEXUS_DB` is set. The
admin token is read once at startup.

### Egress relay and container probes (experimental)

```bash
# Networkless sandbox probe; exit code 0 means external and loopback TCP were blocked.
docker compose -f compose.sandbox.yaml --profile sandbox-test run --rm --build mcp-sandbox-check

# Two-network topology smoke test: the worker must have no default route and reach only the relay.
export NEXUS_PROXY_ORIGIN=https://approved.example.org/mcp
export NEXUS_PROXY_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker compose -f compose.egress.yaml --profile egress-test up --build --abort-on-container-exit --exit-code-from mcp-worker
```

The relay can also run on its own with `python -m nexus.egress_proxy`
(loopback, port 8787) when `NEXUS_PROXY_ORIGIN` and `NEXUS_PROXY_SECRET` are
set. Never expose port 8787 or commit the secret.

## Configuration

| Variable | Default | Read by | Meaning |
| --- | --- | --- | --- |
| `NEXUS_ADMIN_TOKEN` | empty | `nexus/main.py` | Bearer token for admin routes. Empty means every admin route answers `503`. Required by `compose.yaml`. |
| `NEXUS_DB` | `./data/nexus.db` | `nexus/db.py` | SQLite path. The Docker image and `compose.yaml` set `/data/nexus.db`. |
| `NEXUS_ENABLE_HTTP_EXECUTION` | unset | `nexus/main.py` | Must be exactly `true` to enable the experimental GET executor (`…/execute`); otherwise that route answers `503`. |
| `NEXUS_PROXY_ORIGIN` | required by the relay | `nexus/egress_proxy.py` | The one HTTPS MCP URL the relay forwards to; no query or fragment. |
| `NEXUS_PROXY_SECRET` | required by the relay | `nexus/egress_proxy.py` | Shared Bearer secret for `/mcp` and `/attest`; at least 32 characters. |
| `NEXUS_PROXY_BIND` | `127.0.0.1` | `nexus/egress_proxy.py` | Relay bind address: `127.0.0.1` or `0.0.0.0`. |
| `NEXUS_PROXY_CONTAINER_ISOLATED` | unset | `nexus/egress_proxy.py` | Must be `1` when `NEXUS_PROXY_BIND=0.0.0.0` (set in `compose.egress.yaml`). |
| `NEXUS_PROXY_HOST` | `mcp-relay` | `nexus/egress_isolation_probe.py` | Relay host the isolation probe tries to reach. |
| `NEXUS_PROXY_PORT` | `8787` | `nexus/egress_isolation_probe.py` | Relay port for the isolation probe. |

`environment_secret_provider` in `nexus/mcp_credentials.py` reads the
environment variable named by a `CredentialBinding` at request time (for
example `NEXUS_EXAMPLE_TOKEN`). `scripts/sync_baseline.py` reads `GITHUB_TOKEN`
(see [COMPLETE_BASELINE_IMPORT.md](docs/COMPLETE_BASELINE_IMPORT.md)).

## REST API

Admin means `Authorization: Bearer $NEXUS_ADMIN_TOKEN` (constant-time
comparison): `401` for a missing or wrong token, `503` when no token is
configured.

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/healthz` | none |
| GET | `/v1/capabilities?q=&category=&limit=&offset=` | none |
| GET | `/v1/categories` | none |
| GET | `/v1/capabilities/{capability_id}` | none |
| POST | `/v1/import` | admin |
| PATCH | `/v1/capabilities/{capability_id}/status` | admin |
| GET | `/v1/capabilities/{capability_id}/reviews` | admin |
| GET | `/v1/discover?q=&limit=&approved_only=` | none |
| GET | `/v1/manifest` | admin |
| POST | `/v1/openapi/inspect` | admin |
| POST | `/v1/specs` | admin |
| GET | `/v1/specs` | admin |
| GET | `/v1/specs/{digest}/operations` | admin |
| PATCH | `/v1/specs/{digest}/operations/{operation_id}/status` | admin |
| GET | `/v1/specs/{digest}/operations/{operation_id}/reviews` | admin |
| GET | `/v1/specs/{digest}/operations/{operation_id}/plan-events` | admin |
| POST | `/v1/specs/{digest}/operations/{operation_id}/plan` | admin |
| POST | `/v1/specs/{digest}/operations/{operation_id}/preflight` | admin |
| POST | `/v1/specs/{digest}/operations/{operation_id}/execute` | admin, and `NEXUS_ENABLE_HTTP_EXECUTION=true` |
| POST | `/v1/mcp/inspect` | admin |
| GET | `/v1/tools?approved_only=` | admin |
| POST | `/v1/mcp/manifests` | admin |
| GET | `/v1/mcp/manifests` | admin |
| GET | `/v1/mcp/manifests/{digest}/tools` | admin |
| PATCH | `/v1/mcp/manifests/{digest}/tools/{name}/status` | admin |
| GET | `/v1/mcp/manifests/{digest}/tools/{name}/reviews` | admin |
| POST | `/v1/mcp/connections` | admin |
| GET | `/v1/mcp/connections` | admin |
| POST | `/v1/mcp/protocol/inspect` | admin |
| POST | `/v1/mcp/protocol/transition` | admin |
| POST | `/v1/mcp/transport/inspect` | admin |
| POST | `/v1/mcp/sessions` | admin |
| GET | `/v1/mcp/sessions/{session_id}` | admin |
| PATCH | `/v1/mcp/sessions/{session_id}` | admin |
| POST | `/v1/mcp/handshake/validate` | admin |
| POST | `/v1/mcp/sessions/{session_id}/reconcile` | admin |
| GET | `/docs`, `/redoc`, `/openapi.json` | none (FastAPI defaults) |

The catalog read routes need no login and return entries of every status.
`GET /v1/discover` ranks approved entries by default; with
`approved_only=false` it also returns unreviewed entries, **without login**.

The relay (`python -m nexus.egress_proxy`) is a separate HTTP server, not part
of the FastAPI app: `GET /attest` and `POST /mcp` on port 8787, both requiring
`Authorization: Bearer $NEXUS_PROXY_SECRET` (`403` otherwise).

## Python APIs (opt-in)

These are not exposed as REST routes, and each is disabled until a caller
enables it explicitly:

- `nexus.mcp_network.MCPNetworkTransport` — pinned HTTPS POST for MCP; requires `enabled=True`.
- `nexus.mcp_credentials.AuthenticatedMCPTransport` — adds a runtime Bearer
  token and requires a `CredentialScope` bound to the exact binding and URL:

  ```python
  from nexus.credential_policy import CredentialScope
  from nexus.credentials import CredentialBinding
  from nexus.mcp_credentials import AuthenticatedMCPTransport

  binding = CredentialBinding('example', 'NEXUS_EXAMPLE_TOKEN')
  transport = AuthenticatedMCPTransport(
      'https://example.com/mcp',
      binding=binding,
      scope=CredentialScope(binding, 'https://example.com/mcp'),
      enabled=True,
  )
  ```

  The default scope allows `initialize`, `notifications/initialized` and
  `tools/list`, not `tools/call`.
- `nexus.mcp_relay_client.MCPRelayTransport` and `AttestedMCPRelayTransport` —
  MCP through the relay; require `enabled=True`; only `initialize`, `notifications/initialized` and
  `tools/list` are allowed.
- `nexus.mcp_pipeline.inspect_via_relay(...)` — read-only initialize →
  `tools/list` → reconciliation through the relay; requires `enabled=True` and
  an `upstream_url` equal to the registered connection URL.
- `nexus.mcp_worker.exchange_isolated(...)` — one-shot subprocess with a
  parent-enforced deadline; requires `enabled=True` and a `SandboxPolicy`.

## Security boundaries

- **Outbound requests.** By default the API fetches only the fixed import
  source (`POST /v1/import`, raw GitHub URLs for `cporter202/API-mega-list`).
  The opt-in executor (`NEXUS_ENABLE_HTTP_EXECUTION=true`) performs GET
  requests to hosts from administrator-registered, approved OpenAPI specs,
  in a supervised subprocess, with the public IP pinned, redirects blocked, a
  256 KiB response limit, an 8-second budget and a process-local limit of 2
  concurrent and 20 per 60 seconds. `…/preflight` performs DNS lookups. No
  REST route fetches a URL that a non-administrator supplies.
- **Application-level controls only.** Credential scopes, sandbox policies,
  relay attestation and hostname checks are checks in Python. They do not
  configure or inspect a firewall. A compromised relay can misreport its
  configuration.
- **Docker.** The isolation workflow checks that the worker container has no
  default IPv4/IPv6 route and can reach the relay. It is a smoke test, not
  proof against container escape or host compromise. The relay container can
  still reach other public hosts at the network layer.
- **Exposure.** Do not publish port 8088 or 8787 on the internet or an
  untrusted network. The relay's internal HTTP transport does not encrypt the
  shared secret. Secrets passed as environment variables are visible to
  Docker administrators.
- **Audit.** Review and execution audit rows are append-only in SQLite but not
  tamper-evident, and there are no individual administrator identities.

## Tests and CI

```bash
python -m pytest -q
```

The test modules set their own `NEXUS_ADMIN_TOKEN`. Catalog-specific checks
are in [OFFLINE_MANIFEST_CATALOG.md](docs/OFFLINE_MANIFEST_CATALOG.md).

| Workflow | What it gates |
| --- | --- |
| [`ci.yml`](.github/workflows/ci.yml) | Python 3.11 and 3.12: install `.[test,catalog]`, `compileall`, `pytest -q` (including `tests/test_baseline_completeness.py`, which pins `nexus/main.py` to the v0.50.0 original) |
| [`docker-isolation.yml`](.github/workflows/docker-isolation.yml) | Builds `compose.egress.yaml`, starts `mcp-relay` and runs the `mcp-worker` isolation probe once |
| [`validate-manifests.yml`](.github/workflows/validate-manifests.yml) | Validator CLI on the example manifest, six manifest/catalog contract-test modules, catalog export and drift gate |

`scripts/verify_baseline.py <archive.zip>` compares the checkout with the
original v0.50.0 archive; the expected differences are listed in
[COMPLETE_BASELINE_IMPORT.md](docs/COMPLETE_BASELINE_IMPORT.md#declared-divergences-from-the-archive).

## Documentation

- [ECOSYSTEM_BOUNDARIES.md](docs/ECOSYSTEM_BOUNDARIES.md) — intended authority boundaries (proposal)
- [ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) — draft architecture decisions
- [CAPABILITY_MANIFEST_V0_1.md](docs/CAPABILITY_MANIFEST_V0_1.md) — capability manifest format
- [SCHEMA_VALIDATION_PLAN.md](docs/SCHEMA_VALIDATION_PLAN.md) — schema validation cases
- [OFFLINE_MANIFEST_CATALOG.md](docs/OFFLINE_MANIFEST_CATALOG.md) — offline manifest catalog prototype
- [PROPOSAL_LOCAL_HOME_CAPABILITIES.md](docs/PROPOSAL_LOCAL_HOME_CAPABILITIES.md) — local home capabilities (decided: option A)
- [COMPLETE_BASELINE_IMPORT.md](docs/COMPLETE_BASELINE_IMPORT.md) — v0.50.0 baseline import and declared divergences
- [BASELINE_IMPORT.md](docs/BASELINE_IMPORT.md) — historical bootstrap notes
- [CHANGELOG.md](CHANGELOG.md) — version history up to v0.50.0
