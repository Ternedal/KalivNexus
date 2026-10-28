## v0.45.0 — Strict attestation protocol version

Attestation responses now require JSON integer `version: 1` exactly; booleans and numerically equivalent floats are rejected. Added regression tests. This is not a proof of network isolation.

## v0.44.0 — Strict relay attestation parsing

- Reject duplicate attestation JSON fields and nonstandard JSON constants.
- Reject malformed or oversized attestation Content-Length before reading.
- Attestation still proves only relay-reported configuration, **not** OS network isolation.
- MCP tool execution remains disabled; no ModelRig changes.

## v0.43.0 — Attestation-gated read-only relay transport

Added `AttestedMCPRelayTransport` which challenges relay upstream configuration before **each** read-only MCP request. Failed attestation prevents the MCP POST. This does **not** verify Docker isolation, and a compromised relay can still misrepresent its configuration or change it after attestation.

## v0.41.0 — Relay configuration attestation (experimental)

The relay now exposes authenticated `GET /attest` with a random client challenge and HMAC-SHA256 proof of its configured upstream URL. `MCPRelayTransport.attest(expected_upstream)` verifies the nonce, signature and exact upstream fingerprint before a caller chooses to proceed. This is a **configuration assertion by the relay**, not independent verification of actual outbound network traffic, container isolation, or host integrity. The method is opt-in; callers must invoke it explicitly, and it does not enable `tools/call`. Do not expose the relay on an untrusted network: its internal HTTP transport does not encrypt the shared secret. Use only inside an OS-isolated Docker network and test the network controls on a real Docker host.

# Kaliv Nexus — v0.15.0

Local-first API discovery and capability registry for Kaliv/ModelRig.

## What works

- Imports public Markdown links from `cporter202/API-mega-list` (master/main README fallback).
- Normalizes, deduplicates by URL, categorizes and searches capabilities.
- SQLite persistence and REST API with OpenAPI documentation.
- Admin-token protected imports and approval/status updates.
- Existing approval statuses survive reimports.
- Docker Compose binds only to localhost; no arbitrary API execution.

**Important:** Imported links are **unverified leads**, not working integrations. The Markdown parser is heuristic and can include navigation or non-API links. Status `approved` is a manual registry state, not an automated security certification. No external API is invoked by the catalog.

## Start (Docker)

```bash
cp .env.example .env
# Replace NEXUS_ADMIN_TOKEN with a secure random secret
# e.g. python -c 'import secrets; print(secrets.token_urlsafe(48))'
docker compose up -d --build
curl http://127.0.0.1:8088/healthz
curl -X POST http://127.0.0.1:8088/v1/import -H "Authorization: Bearer YOUR_TOKEN"
curl 'http://127.0.0.1:8088/v1/capabilities?q=weather'
```

Swagger UI: http://127.0.0.1:8088/docs

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export NEXUS_ADMIN_TOKEN='replace-with-long-random-secret'
uvicorn nexus.main:app --reload --port 8088
pytest -q
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Health |
| GET | `/v1/capabilities?q=&category=&limit=&offset=` | Search catalog |
| GET | `/v1/categories` | Category counts |
| GET | `/v1/capabilities/{id}` | Detail |
| POST | `/v1/import` | Refresh source (admin) |
| PATCH | `/v1/capabilities/{id}/status` | Manual review state (admin) |

## Architecture and next steps

1. Add a proper importer for repository structure and license/provenance tracking.
2. Add separate approval gates and source-documentation validation.
3. Add OpenAPI/MCP adapters **only after** network egress controls, DNS/IP revalidation, secret vault, rate limits and audit logs.
4. Add persistent workflows (Temporal) and optional Postgres/Qdrant backend.
5. Expose approved capabilities as tool schemas to ModelRig; do not expose unreviewed URLs as executable tools.
6. Build Kaliv Android/desktop dashboard and observability.

**Security:** Do not publish the service on the internet as-is. Use a private network, reverse proxy with TLS/auth and further hardening first. No remote code or user-supplied URLs are fetched by the API.

## v0.2.0 – capability discovery

- `GET /v1/discover?q=weather`: ranks *approved* entries by matching name, category and description. Add `approved_only=false` to inspect unreviewed entries (metadata only).
- `GET /v1/manifest`: admin-token-protected export of approved capability metadata.
- No remote API invocation, credential exchange, or MCP tool execution is implemented. Entries from the source list are **untrusted** and cannot become executable merely by changing their status.
- The ranking implementation is deliberately deterministic; a later version can add semantic retrieval without relaxing approval gates.

## v0.3.0: OpenAPI inspection (metadata-only)

`POST /v1/openapi/inspect` accepts `{ "document": <OpenAPI 3 JSON object> }` with the administrator bearer token. It extracts operation metadata and returns `executable: false`; no remote URLs are fetched and no third-party API requests are executed. Limits: 1 MB JSON document, 250 operations, absolute HTTPS server URL. This is an inspection prototype, not a complete OpenAPI validator; untrusted specifications must not be converted into executable requests without separate validation, allowlisting, and user approval.

## v0.4.0 — static operation risk assessment

`POST /v1/openapi/inspect` now annotates each extracted operation with
`risk_level`, `risk_flags`, `requires_explicit_approval` and `executable=false`.
The analysis identifies state-changing HTTP methods, sensitive endpoint names,
private/local hosts, non-public IP literals, unusual ports, and absent declared
security requirements. This is advisory triage, **not** a security certification.
No external operation is executed; future execution must separately enforce
DNS rebinding defenses, IP allow/deny policy at connection time, redirect policy,
credential scoping, per-operation authorization, egress controls and audit logs.

## v0.5.0 — review workflow and audit trail

The administrator-only `PATCH /v1/capabilities/{id}/status` now requires a JSON body
such as `{"status":"reviewed","reason":"Documentation and terms checked"}`.
Transitions are restricted to `discovered → reviewed → approved`, with an option
to disable an entry at each stage. Disabled entries can return to reviewed status.
Every successful transition creates an append-only review event in SQLite;
`GET /v1/capabilities/{id}/reviews` exposes the history to administrators.
This is a breaking request-body change from v0.4.0. Approval permits metadata
discovery only: **no external API execution**. Audit records currently have no
tamper-evident storage or individual administrator identities; deploy privately.

## v0.6.0 — immutable OpenAPI registry

Administrator endpoints (Bearer `NEXUS_ADMIN_TOKEN`):

- `POST /v1/specs` with `{"document": { ... OpenAPI 3 ... }}` saves a content-addressed immutable snapshot.
- `GET /v1/specs` lists registered snapshots.
- `GET /v1/specs/{digest}/operations` lists operations and their independent review statuses.
- `PATCH /v1/specs/{digest}/operations/{operation_id}/status` accepts `{"status":"reviewed","reason":"Manual schema review"}`; transitions must follow `discovered → reviewed → approved` (or `disabled`).
- `GET /v1/specs/{digest}/operations/{operation_id}/reviews` shows the audit trail.

Every changed specification gets a new SHA-256 digest and **all its operations start unapproved**, even when they were approved in an older version. Approval does **not** enable execution. No third-party API requests are made by these endpoints. This is a metadata-only registry, not a secure execution sandbox.

## v0.7.0 — approval-gated execution planning (NO NETWORK EXECUTION)

`POST /v1/specs/{digest}/operations/{operation_id}/plan` with
`{"parameters":{"item":"example"}}` produces a **non-executable** preview
of an approved GET request. Unapproved, high-risk, state-changing and private-host
operations are rejected. Path parameters are percent-encoded and must match the
operation's placeholders exactly. This endpoint never contacts third-party APIs.

**Security boundary:** This is not yet a Secure Execution Gateway. Before allowing
real calls, implement DNS resolution + rebinding-resistant connection pinning,
network egress isolation, redirect denial, credentials scoping, request limits,
rate limits, response-size limits, runtime authorization and execution audit.

## v0.8.0 — audited execution planning (still NO NETWORK EXECUTION)

Planning requests now record an append-only SQLite event for both allowed and rejected
plans. Inspect with admin-only `GET /v1/specs/{digest}/operations/{operation_id}/plan-events`.
Parameter values and full URLs are not persisted in the audit table; only a SHA-256
fingerprint of parameter **names** is stored. Audit entries are not tamper-proof.

**Execution remains disabled.** This release intentionally does not introduce
outbound HTTP calls: DNS rebinding resistance, network egress isolation and
credential management must be addressed before that can be safe.


## v0.9.0 – DNS egress preflight (no HTTP execution)

`POST /v1/specs/{digest}/operations/{operation_id}/preflight` checks approved GET
plans and resolves DNS. All returned addresses must be globally routable.
This is a **diagnostic only**, not a secure HTTP executor: DNS rebinding
remains possible unless the future transport pins the verified address while
validating the original TLS hostname. Network isolation, redirect blocking,
rate limits, credentials, and execution auditing remain prerequisites.

## v0.10.0 – Experimental HTTP executor

A new administrator-only `POST /v1/specs/{digest}/operations/{operation_id}/execute`
endpoint executes **approved, non-high-risk GET** operations only when
`NEXUS_ENABLE_HTTP_EXECUTION=true`. It is **disabled by default**. DNS answers
are validated, a public IP is pinned at socket connection, TLS verifies the
original hostname, redirects are blocked, the response is limited to 256 KiB,
and a five-second socket timeout is used. Execution outcomes are audited.

**Not production-hardened:** use only in a restricted outbound network sandbox.
There is no rate limiter, request budget, durable job scheduler, credential
vault, or protection against every malicious upstream behavior. Proxy settings
are not supported. Only enable with trusted reviewed API specifications.

## v0.11.0 execution budgets

The opt-in execution endpoint now uses a **process-local** limiter: 2 concurrent
requests and 20 attempted executions per rolling 60 seconds. Capacity is
reserved only after operation approval and planning. A failed upstream attempt
still consumes a minute-budget slot. This does **not** coordinate between
workers or replicas; use a shared limiter (for example Redis) before multi-worker
deployment. Network isolation, end-to-end deadline enforcement, and integration
tests against a controlled HTTPS target are still outstanding. Execution remains
disabled by default (`NEXUS_ENABLE_HTTP_EXECUTION` must explicitly be `true`).


## v0.12.0 – execution deadline

The experimental executor now enforces a monotonic **8-second cooperative budget**,
checks the remaining budget after DNS and between network stages, and bounds socket
timeouts by the remaining budget. This is **not a hard wall-clock deadline**: a
blocking DNS resolver or blocking I/O may exceed the deadline before returning.
A separately isolated worker with a supervisor-enforced kill deadline is required
before enabling untrusted arbitrary endpoints in production.

## v0.13.0 — isolated execution supervisor

Opt-in HTTP GET execution now runs in a one-shot spawned subprocess. The API process
waits at most 9 seconds, terminates an over-budget worker, and forcibly kills it
if necessary. Worker failures return generic upstream errors; execution remains
disabled unless `NEXUS_ENABLE_HTTP_EXECUTION=true`.

**Security boundary:** This is a wall-clock/process boundary, **not** a network
sandbox. Production use still requires container/OS egress policy, a shared
rate limiter for multi-worker deployments, and end-to-end security review.

## v0.14.0: Unified tool discovery (metadata only)

`POST /v1/mcp/inspect` validates and normalizes MCP `tools/list`-shaped manifests without connecting to untrusted servers. `GET /v1/tools` exposes registered OpenAPI operations, approved only by default. Both endpoints require an admin bearer token. No MCP tool execution, credentials, persistence of MCP manifests or dynamic invocation is implemented.

## v0.15.0: Persistent MCP metadata registry

Register validated `tools/list`-shaped manifests using `POST /v1/mcp/manifests`.
Manifests are content-addressed by SHA-256, and tool approvals are scoped to
that exact version. Tools start `discovered` and require `reviewed` then
`approved` transitions via `PATCH /v1/mcp/manifests/{digest}/tools/{name}/status`.
Use `GET /v1/mcp/manifests`, `GET /v1/mcp/manifests/{digest}/tools`, and
`GET /v1/mcp/manifests/{digest}/tools/{name}/reviews` to inspect versions,
status and audit history. `GET /v1/tools` now merges approved OpenAPI and MCP
metadata. All these endpoints require admin authentication.

**MCP tools remain metadata-only and non-executable.** This release does not
connect to MCP servers, accept credentials, or invoke arbitrary tools.

## v0.16.0 – MCP connection profiles (inert)

Administrators can register HTTPS MCP server profiles using `POST /v1/mcp/connections`
and list them with `GET /v1/mcp/connections`. Profiles must reference an existing
versioned MCP manifest. Duplicate names, private/local hostnames, IP literals,
userinfo, fragments and non-443 ports are rejected at registration. Profiles
are **always disabled**, and Nexus does not connect to them, send credentials,
perform DNS lookups, or execute MCP tools. Hostname validation at registration
is **not** a runtime SSRF defense; a separate isolated connector with DNS/IP
pinning, redirects disabled, and explicit approval will be required.

## v0.17.0 — Offline MCP protocol inspection

Admin-only `POST /v1/mcp/protocol/inspect` validates JSON-RPC 2.0 envelopes and returns message kind without executing requests. `POST /v1/mcp/protocol/transition` validates an illustrative initialize → response → initialized notification state sequence. This is **not** an MCP transport, persistent session manager, full protocol validator, or connected client. No network traffic or MCP tool execution is enabled. The response intentionally reports `connected: false`.

## v0.18.0 – MCP transport framing (offline)

Adds `POST /v1/mcp/transport/inspect` (admin-only), which accepts `content_type`
and `body_base64`, and validates bounded JSON-RPC responses and Streamable HTTP
SSE message frames without opening a network connection. Strict UTF-8 decoding,
1 MiB payload limits, supported media-type checks and 100-message SSE limit apply.

**Not implemented:** live MCP transport, sessions, credentials, network sandbox,
server identity verification or tool execution. All external MCP execution remains
inactive. This endpoint is an offline parser, not a security boundary for live traffic.

## v0.19.0 — Offline MCP sessions

Administratorbeskyttede endpoints: `POST /v1/mcp/sessions`, `GET /v1/mcp/sessions/{session_id}` og `PATCH /v1/mcp/sessions/{session_id}`.
Sessioner oprettes kun for registrerede MCP-forbindelser, udløber efter højst 3600 sekunder og tillader kun eksplicitte tilstandsovergange. Sessionerne er **offline metadata**: de opretter ikke en MCP-transport, validerer ikke fjernservere og giver ingen eksekveringsrettigheder. Udløb kontrolleres ved læsning/opdatering, ikke via en baggrundsproces. Netværksisolation og runtime-sikkerhed er stadig nødvendige før aktive forbindelser.

## v0.20.0 — MCP handshake transcript validation

- `POST /v1/mcp/handshake/validate` (admin): validate a three-message offline MCP initialization transcript.
- Checks client/server protocol version `2025-06-18`, matching JSON-RPC IDs, client/server information, capability objects, and final `notifications/initialized`.
- Returns `connected: false` and `executable: false`. This is **not** a live MCP client; no remote connections are made.
- Next: isolated network transport with host allowlists, IP-pinning, redirects disabled, and network sandbox; never use this transcript validator as a substitute for runtime enforcement.

## v0.21.0 — MCP transport adapter contract (offline)

Introduces `nexus.mcp_client.initialize(transport)` with an injectable transport
interface and fail-closed initialization. It validates HTTP status, JSON content
type, a 1 MiB response limit, JSON-RPC handshake and server identity fields,
then emits the initialized notification only after successful validation.
Tests use a fake transport. **No real network adapter, network sandbox, live
session or tool execution is included.** The injected transport is trusted;
production use requires separate egress enforcement and an isolated worker.

## v0.22.0 — experimental MCP network transport

`nexus.mcp_network.MCPNetworkTransport` adds opt-in pinned HTTPS POST for
MCP JSON responses, 202 notification acknowledgements, bounded bodies, and
session ID checks. SSE streaming, live interoperability, credential storage,
network namespace sandboxing, and ModelRig integration are **not** implemented.
This transport must not be exposed to untrusted API definitions or deployed
without external egress firewall restrictions. No network connections occur
unless the constructor is explicitly passed `enabled=True`.

## v0.23.0 – Offline MCP tools/list discovery

`nexus.mcp_discovery.discover_tools(transport)` queries a pre-authorized, initialized
MCP transport using bounded JSON-RPC `tools/list` pagination. It validates tool
schemas, enforces limits of 10 pages / 250 tools / 1 MiB per response, rejects
repeated cursors and duplicate names, and returns **unapproved, non-executable**
metadata. It does not open connections, save credentials, register tools, or call
`tools/call`. Live integration and transport sandboxing remain future work.

## v0.24.0 – MCP manifest reconciliation (offline)

`POST /v1/mcp/sessions/{session_id}/reconcile` accepts a **previously obtained**
non-executable discovery result and compares it against the connection's pinned
manifest and operation-level approvals. Requires an admin token and a ready,
unexpired session. Reports added, removed and changed tools, plus the SHA-256
of the observed canonical manifest. Previously approved tools are reported as
matching only when the **entire** manifest digest matches. No tools are
registered, approved, executed or fetched by this endpoint. The discovery
payload is caller-provided; a trusted live discovery binding and egress
sandbox are still required before it can become an authorization boundary.

## v0.25.0 – Read-only MCP discovery pipeline

`nexus.mcp_pipeline.inspect_session_tools(db, session_id, transport)` combines
MCP initialization, paginated tool discovery, and manifest reconciliation.
It accepts an injected transport; no public API endpoint or live network access
is enabled by this addition. It requires a ready, unexpired offline session
bound to a disabled connection profile. It never approves, registers or executes
tools. Transport credentials, network sandboxing and live integration testing
remain outstanding.

Run tests: `python -m pytest -q`.

### v0.26.0: guarded live discovery entry point

`inspect_registered_connection(db, session_id, allow_network=True, transport_factory=...)`
provides an opt-in bridge from a registered MCP connection to the existing
initialize → tools/list → reconciliation pipeline. It obtains the URL only from
the connection registry, validates the profile, and checks for profile drift
before returning results. It never executes tools or changes approvals.

**Not production-ready:** The injected transport factory must enforce a network
sandbox, TLS, egress restrictions and credentials. No public live-inspection
REST endpoint is exposed. Live network tests have not been run.


## v0.27.0 — Loopback MCP integration harness

`nexus.mcp_test_harness` supplies a localhost-only ephemeral HTTP MCP fixture and test transport. It verifies a real HTTP initialize / initialized / tools/list roundtrip, without enabling external MCP access or tool execution. Run `python -m pytest -q`. This fixture is **not** a production network sandbox.


## v0.28.0 — Credential reference groundwork

Added `nexus.credentials` with validated secret references, execution-time bearer token resolution, fail-closed missing/invalid credentials, and sensitive-header redaction. No secrets are stored in SQLite or shipped in configuration. This is **not** a complete credential manager: no vault integration, rotation, network sandbox, or production MCP execution has been enabled.

## v0.29.0 — MCP credential integration

`AuthenticatedMCPTransport` adds runtime-only Bearer authorization to the existing
opt-in HTTPS transport. It accepts a `CredentialBinding` and a callable secret
provider; `environment_secret_provider` is supplied for local development.
Credentials are resolved afresh for each request, enabling rotation without
persisting tokens. Missing or invalid tokens fail closed.

Example (only with an approved destination and enforced outbound network policy):

```python
from nexus.credentials import CredentialBinding
from nexus.mcp_credentials import AuthenticatedMCPTransport

transport = AuthenticatedMCPTransport(
    'https://example.com/mcp',
    binding=CredentialBinding('example', 'NEXUS_EXAMPLE_TOKEN'),
    enabled=True,
)
```

**Security status:** The transport remains opt-in and is not a network sandbox.
Environment variables are a development secret source, not a full production
secret manager. Do not enable arbitrary remote MCP endpoints without container
or host-enforced egress controls, credential scoping, and further integration tests.

## v0.31.0 – Credential scoping

`CredentialScope` binds a credential to one exact HTTPS endpoint, one connection name, and an explicit set of MCP methods. The default method allowlist permits initialization and tool discovery, but **not** `tools/call`. Pass `scope=CredentialScope(binding, url)` to `AuthenticatedMCPTransport` to enforce it. Existing transports without a scope retain legacy behavior for backward compatibility; production deployment should require scoped transports. This is an application-level control, **not** an OS-enforced network sandbox or a substitute for secret management.

### v0.31.0 security change
Authenticated MCP transports now require an explicit `CredentialScope` at construction time. A missing scope is rejected before credentials are resolved or network access begins. Existing clients must supply a scope bound to the exact connection and endpoint. MCP tool execution remains disabled under the default scope. This is a breaking configuration change. Network sandboxing remains outstanding.


## v0.32.0 – isolated MCP exchange worker

`nexus.mcp_worker.exchange_isolated` adds an opt-in, one-shot subprocess supervisor with a parent-enforced deadline, bounded input, generic error responses and forced child termination. This is **not** a network sandbox, does not manage credentials or persist MCP sessions, and is not wired to a public API endpoint. Use only with enforced OS/container egress policy.

## v0.33.0: Network sandbox deployment gate

`exchange_isolated` now requires an explicit `SandboxPolicy` with a destination-bound
origin and an assertion that OS/container egress filtering is active. Without it,
the worker fails closed before spawning. **This is not actual sandbox enforcement:**
the attestation can be forged by a caller and does not inspect kernel firewall rules.
Production operators must enforce destination restrictions independently at the
container/host network layer, and must test DNS rebinding, redirects, and IPv6.
Do not enable arbitrary external MCP calls based on this gate alone.

## v0.34.0 – Networkless container isolation baseline

A new opt-in `compose.sandbox.yaml` defines a separate **networkless** MCP
sandbox test container. It has no network namespace connectivity, drops all
Linux capabilities, uses a read-only filesystem, runs unprivileged, limits
processes/memory/CPU, and enables `no-new-privileges`.

Run on a host with Docker Compose installed:

```bash
# Builds and runs a network-denial probe; exit code 0 means the probe passed.
docker compose -f compose.sandbox.yaml --profile sandbox-test run --rm --build mcp-sandbox-check
```

This test container is deliberately **unable to reach any MCP server**.
It does NOT implement destination-specific egress, does not run arbitrary
MCP calls, and does not establish a production-ready network sandbox.
The probe is a useful runtime smoke test, not a complete security proof.
A future dedicated egress proxy plus kernel-level rules must be verified
before allowing external MCP execution. Do not run the MCP worker with
unrestricted network access on the strength of this profile.

## v0.35.0 — Egress proxy policy foundation

Added `nexus.egress_proxy_policy`: explicit HTTPS origin and method allowlisting,
IP literal/local hostname rejection, and request-size budgets. Tests cover common
bypass attempts. **This is a policy module, not an actual proxy or network sandbox.**
Next: build a dedicated proxy process with DNS pinning, TLS validation, no redirects,
per-connection authentication and OS-enforced worker-to-proxy-only networking.
Do not enable arbitrary external MCP execution based on this module alone.

## v0.36.0 – Experimental single-origin egress relay

`python -m nexus.egress_proxy` starts a loopback-only relay on port 8787, using
`NEXUS_PROXY_ORIGIN` (trusted fixed HTTPS MCP URL) and `NEXUS_PROXY_SECRET`
(a random secret of at least 32 characters). Clients POST to `/mcp` with
`Authorization: Bearer <secret>`. The relay performs pinned TLS requests through
existing MCP transport and enforces the origin policy, request/response limits,
and rejects redirects. Never expose port 8787 publicly or commit the secret.

**Not production-ready:** No Docker network policy is provisioned here, and a
loopback relay does not prevent a worker from making direct outbound connections.
Before deployment, place the worker and relay in separate network namespaces,
block worker egress except to the relay, constrain relay egress to approved IPs,
and test the rules on the actual Docker host. The relay does not yet implement
per-client rate limits, concurrency caps, or durable audit records. Credentials
for upstream MCP authentication are not yet integrated.

## v0.37 — experimental two-network Docker deployment

`compose.egress.yaml` places the test worker on an **internal-only** Docker network.
The relay joins that network and a separate egress network, with **no host ports**
published. The worker cannot use the relay network as a default route. The
relay requires an explicit HTTPS origin and a strong shared secret.

Example (Docker required, run on a dedicated trusted host):

```bash
export NEXUS_PROXY_ORIGIN=https://approved.example.org/mcp
export NEXUS_PROXY_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker compose -f compose.egress.yaml --profile egress-test up --build --abort-on-container-exit --exit-code-from mcp-worker
```

The worker executes a **network topology smoke test**, not an MCP tool call.
The probe checks default IPv4/IPv6 routes and relay reachability. The relay
container remains able to reach other public hosts at the network layer;
application origin validation is not equivalent to a host firewall. This
deployment has NOT been validated against a running Docker engine here.
Secrets passed through environment variables are visible to Docker admins;
use Docker secrets or another secret manager before production.

## v0.38.0 — Opt-in MCP relay client

`nexus.mcp_relay_client.MCPRelayTransport` implements the existing MCP
`exchange`/`notify` interface through the `/mcp` relay endpoint. It sends no
requests directly to upstream MCP hosts. It is **disabled by default** and
requires an explicit relay hostname and a 32+ character runtime secret.
Request and response sizes are capped, and tests use injected fake connections.

This is **not** proof of end-to-end container isolation: the Docker integration
has not been executed here, and MCP `tools/call` remains disabled. Deploy only
on a restricted internal network, not across an untrusted HTTP link.

### v0.39.0: read-only relay integration

`inspect_via_relay(db, session_id, relay_host=..., relay_secret=..., enabled=True)`
connects initialize, initialized notification, paginated tools/list and manifest
reconciliation using the relay transport. Disabled by default. It never grants
approval or executes tools. The relay's upstream destination must be configured
and bound independently by deployment; this Python API cannot prove that binding,
or that a Docker network sandbox is active. Production use requires real-host
isolation and upstream binding verification.


### v0.40.0: explicit relay upstream binding and read-only gate

`inspect_via_relay` now requires `upstream_url` to exactly match the
registered connection URL before opening the relay connection. This is a
configuration consistency check, **not cryptographic or runtime proof** that
the proxy is using that upstream. Provision the proxy independently with the
same destination, and verify it on the Docker host.

The relay client only permits `initialize`, `notifications/initialized`,
and `tools/list`. `tools/call` and other methods fail before any network
request. Real container egress isolation remains unverified in this build.


## v0.43.0 — Relay request validation hardening

The read-only MCP relay client now rejects duplicate JSON keys (including nested keys), JSON batches, nonstandard JSON constants, malformed request IDs, notification IDs, and invalid params **before** attempting attestation or network I/O. This is application-layer validation, not proof of network sandboxing.

## v0.46.0 — relay hostname validation

Relay hostnames now require valid DNS label syntax and reject ambiguous numeric-only hosts, empty labels, trailing dots and invalid hyphen placement. This is input validation, **not** a network isolation boundary. External MCP tool execution remains disabled.

### v0.47.0: Docker isolation CI gate

`.github/workflows/docker-isolation.yml` runs the existing egress-isolation
probe inside a real Docker Compose worker container on GitHub-hosted Ubuntu.
The worker must have neither a default IPv4 nor IPv6 route and must be able
to reach its internal relay. The test uses a dummy upstream and does **not**
call the upstream. A failing probe fails the workflow. This is a runtime smoke
test, not proof of resistance to container escapes or host compromise.
The workflow only runs after the repository files are published to GitHub.

### v0.48.0 — isolation probe hardening

The Docker worker isolation probe now evaluates IPv4, IPv6 and relay reachability
independently, and fails closed when either procfs route table is empty or
unreadable. Regression tests cover default routes and missing route data.
This remains a **smoke test**, not a formal proof of network isolation; run the
Docker workflow on a real Docker host before relying on the deployment.


### v0.49.0 — fail-closed Docker route checks
The worker probe rejects malformed IPv4/IPv6 route-table rows instead of treating them as safe. The Docker isolation CI step now runs the probe exactly once; retrying a failed isolation assertion could mask intermittent routing escapes. Docker runtime verification still requires GitHub Actions or a real Docker host.

### v0.50.0 isolation-probe parser hardening

The local Docker isolation smoke-test parser now rejects truncated IPv4 hexadecimal route fields and extra columns in IPv4/IPv6 route rows. These checks are defensive parsing, **not** evidence that a Docker host has passed the isolation smoke test. A real Docker CI run is still required.
