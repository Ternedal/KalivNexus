# KalivNexus

KalivNexus is the proposed integration and capability-discovery layer for the Kaliv ecosystem. **Status: repository bootstrap / design proposal.** No runtime, API compatibility, deployed service or production readiness is asserted by this document.

## Purpose

Provide a governed way to discover, describe and invoke external capabilities without coupling ModelRig or Kaliv clients to each provider's API. The [API-mega-list](https://github.com/cporter202/API-mega-list) is an inspiration and candidate catalog, **not** an automatically trusted or enabled integration registry.

## Ecosystem boundaries

- [ModelRig](https://github.com/Ternedal/ModelRig): orchestration, cognitive state, authenticated client facade, tool authorization and user confirmations.
- [Kaliv](https://github.com/Ternedal/Kaliv): public website/product presentation; application clients use ModelRig's approved interfaces.
- [VoiceRig](https://github.com/Ternedal/VoiceRig): voice packages and TTS.
- [VisionRig](https://github.com/Ternedal/VisionRig): sensor ingestion and structured visual observations.
- [BodyRig](https://github.com/Ternedal/BodyRig): body identity and motor state.
- [LanguageRig](https://github.com/Ternedal/LanguageRig): language-model training and evaluation.
- [KalivHub](https://github.com/Ternedal/KalivHub) / [Receiver](https://github.com/Ternedal/KalivHub-Receiver): home dashboard and display-only Cast receiver.
- [SkyPlayer-Engine](https://github.com/Ternedal/SkyPlayer-Engine): XR/media primitives.

Nexus should describe and execute approved external integrations; it must not independently acquire durable-memory, perception-truth, identity, or unrestricted action authority.

## Proposed architecture

```mermaid
flowchart LR
  Client[Kaliv clients] --> MR[ModelRig policy and orchestration]
  MR --> NX[KalivNexus capability broker]
  NX --> Registry[Curated capability registry]
  NX --> Gate[Auth / consent / quotas / audit]
  Gate --> Adapter[Versioned provider adapters]
  Adapter --> External[External APIs]
```

## Proposed capability manifest

Each integration should declare a stable identifier, provider, version, input/output schema, authentication method, permissions, data classifications, rate limits, timeout/retry policy, idempotency, costs, health probes and approval requirements. Treat remote descriptions and responses as untrusted data.

## Security and operational requirements

1. Default deny; integrations are disabled until explicitly configured and approved.
2. Store secrets outside Git and logs; support rotation and per-provider isolation.
3. Enforce SSRF protection, network egress allowlists, TLS verification and response-size limits.
4. Require explicit ModelRig authorization for side effects; separate read-only from write/destructive operations.
5. Bound timeouts, concurrency, retries and monetary quotas. Use idempotency keys for repeatable writes.
6. Produce redacted audit trails with correlation IDs; never log access tokens or sensitive payloads.
7. Preserve provider attribution, terms of use and data retention restrictions.
8. Do not assume cloud providers are local-first or privacy-equivalent; surface external transfer before invocation.

## Suggested documentation roadmap

- [x] [Draft architecture decisions](docs/ARCHITECTURE_DECISIONS.md) for authority, manifest trust, lifecycle and release gates (not yet implementation decisions)
- [ ] Validated registry schema and example manifests
- [ ] Adapter SDK and contract tests
- [ ] ModelRig integration and approval flow
- [ ] Installation, configuration and rollback runbooks
- [ ] Observability, costs, quotas and failure modes
- [ ] End-to-end tests on exact pinned revisions

## Current prototype (not an active broker)

The repository now contains a draft JSON Schema, a Python manifest validator, an in-memory default-deny catalog and a **SQLite-backed prototype** with registration, revocation and lifecycle events. Neither catalog has an enable or execution path. The SQLite database persists local state, but is not a hardened tamper-proof audit log or multi-user approval system. Neither implementation connects to ModelRig, resolves secrets or calls external APIs.

To run the local contract tests with Python 3.11:

```bash
python -m pip install 'jsonschema==4.23.0'
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/validate_manifest.py examples/weather-readonly.manifest.json
```

The [CI workflow](.github/workflows/validate-manifests.yml) is configured to run these checks, but a passing CI run must be confirmed separately.

## Release discipline

Document **proposed**, **implemented**, **automated-test verified**, **physically tested**, and **released** separately. This README describes a proposal, not delivered functionality.
