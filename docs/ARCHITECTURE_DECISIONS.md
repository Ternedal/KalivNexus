# KalivNexus architecture decisions (draft)

Date: 2026-10-23. **Status: proposed.** These decisions are not proof of a working runtime.

## ADR-001: Authority and trust

KalivNexus is a broker for curated external API capabilities. ModelRig retains user identity, policy, approval and durable-memory authority. Nexus must not independently execute user-visible side effects without an explicit scoped authorization from ModelRig.

## ADR-002: Provider manifests

Each adapter should have a versioned manifest with: stable capability ID, provider, schema version, input/output JSON schemas, auth mechanism, permission scopes, data classification, outbound domains, rate and cost limits, timeouts, retry/idempotency behavior, and explicit approval level.

The API-mega-list is a discovery source only. Provider entries require manual review before activation.

## ADR-003: Runtime security

- Default deny, allowlisted outbound hosts, DNS-rebinding/SSRF defenses and TLS verification.
- Secrets from dedicated secret storage; no secrets in Git, traces or prompts.
- Per-capability quotas, response-size limits, bounded concurrency and circuit breakers.
- Redacted, correlated audit events; explicit user confirmation for writes or destructive actions.
- Remote responses are untrusted input and must not override system policy.

## ADR-004: Integration lifecycle

Proposed sequence: discover -> curate -> configure -> validate credentials -> contract test -> approve -> activate -> monitor -> suspend/revoke. Any contract change requires compatibility testing and versioning.

## ADR-005: Release evidence

Keep proposed, implemented, automated-test verified, physically tested and released separate. Acceptance should include adapter tests, negative authorization tests, secret-leak checks, provider failure handling, quotas and real ModelRig end-to-end invocation.

## Open decisions

- Transport between ModelRig and Nexus
- Manifest schema and versioning format
- Credential vault and rotation implementation
- Cost accounting and billing enforcement
- Offline behavior and caching
- Multi-user tenancy and audit retention

Do not treat these undecided topics as implemented.
