# Proposal: how KalivNexus relates to local home capabilities (Home Assistant, rig status)

Date: 2026-10-26. **Status: proposal for decision.** Nothing in this file is
implemented. The schema and the validator are unchanged. Tracking: #1.

## The question

Issue #1 asks for a read-only NAS/Home Assistant journey. Manifest v0.1 cannot
describe one:

- `network.allowed_https_hosts` rejects `localhost`, `*.local` and IP literals,
  and it is HTTPS-only. A LAN Home Assistant is typically
  `http://homeassistant.local:8123` or `http://192.168.x.y:8123`.
- `auth.type` is `api_key` only. Home Assistant uses a long-lived bearer token.
- This is deliberate. ADR-001 scopes Nexus to **external** API capabilities,
  and ADR-003, together with rule 3 in `CAPABILITY_MANIFEST_V0_1.md`, requires
  defences against **private-network SSRF**.

Before anyone adds LAN fields to the schema, the decision is whether Nexus
should reach the home network at all.

## What already exists (verified 2026-10-26)

- **ModelRig T-038** (`main`, #680–#685) is a software-complete, default-off,
  read-only pilot for Home Assistant entity state and RigGate rig status. It
  provides:
  - exact durable scopes and grants;
  - one-use T-032 permissions;
  - a deployment-injected origin and bearer **file**;
  - HTTPS by default, plaintext only with an explicit flag and only to
    non-global peers;
  - DNS pinned to one validated peer, with a check that the connected peer
    matches;
  - no redirects and bounded responses;
  - strict entity rebinding;
  - source, timestamp and freshness on every observation;
  - preview-only wake/control;
  - durable audit.

  ModelRig PR #2289 adds an end-to-end test of this chain over a real socket.
- **KalivHub** has a separate read-only Home Assistant reader on draft
  branches. It serves the Cast display path only.

## Options

### A. Nexus stays external-only. Local home capabilities stay in ModelRig. (Recommended)

Nexus gets no LAN egress. Home Assistant and RigGate reads remain ModelRig
T-038 connectors.

If one catalog should list both kinds, a later schema version could add a
**descriptive, non-executable** entry kind. For example, `delegated_connector`
would name ModelRig's capability (`home_assistant.entity_state.read`) and its
T-038 authority, but would have no `network` block and no Nexus execution path.

- **Pros:**
  - ADR-001 and ADR-003 stay intact.
  - No third Home Assistant client.
  - The LAN-specific safety logic (peer pinning, the plaintext rule) lives in
    one place, which already has tests.
- **Cons:**
  - Two places execute capabilities (Nexus for external APIs, ModelRig for
    local ones).
  - A unified catalog requires the new entry kind.

### B. Manifest v0.2 with a pinned-LAN network mode

Add a `network.mode: "pinned_lan"` with exact origins (scheme, host, port), an
explicit `allow_insecure_http` flag (non-global peers only), runtime peer
pinning, and an `auth.type` for a bearer held in a secret reference. Nexus
would then perform the LAN read itself.

- **Pros:** one broker for everything.
- **Cons:**
  - Reverses the private-network SSRF rule for a class of capabilities.
  - Duplicates T-038's transport and authority.
  - Needs its own credential storage for home tokens.
  - Moves a home-network attack surface into a component built for external
    APIs.

### C. Leave it unrepresented

Nexus does not mention local capabilities at all.

- **Pros:** no work.
- **Cons:** the catalog is silently incomplete, and #1's KalivNexus part has
  no outcome.

## Recommendation

**Choose A.** For #1 this means the read-only Home Assistant journey is
delivered and verified in ModelRig (T-038 plus #2289). The KalivNexus part of
#1 ends with this decision rather than with a new adapter.

A `delegated_connector` entry kind should be designed only if a unified
catalog is actually wanted, and it would be its own small schema change with
tests.

## Contract under option A

These rules would hold if A is chosen. Until a decision is made, they are
also the de facto state.

**Authority**

| Concern | Owner | Where |
| --- | --- | --- |
| User identity, policy, approval | ModelRig | ADR-001 |
| Home Assistant / RigGate scope, grants, revocation | ModelRig T-038 | `home_rig_connector_contract.py` |
| Per-read data-sharing permission (one use) | ModelRig T-032 | `data_sharing.py`, `home_rig_provider_gate.py` |
| LAN network access (pinned peer, plaintext only to non-global peers) | ModelRig T-038 transport | `home_assistant_provider_transport.py` |
| External API capability catalog and adapters | KalivNexus | manifest v0.1, ADR-002 |

**Prohibitions in KalivNexus**

- No LAN or loopback egress. Manifest v0.1 keeps rejecting `localhost`,
  `*.local` and IP literals, and keeps defending against private-network SSRF
  (ADR-003).
- No Home Assistant or RigGate client, token storage or service call.
- No write path for home capabilities anywhere. T-038 exposes reads and
  `would_execute=false` previews only.
- A future `delegated_connector` entry, if one is ever designed, is
  descriptive only. It has no `network` block, no credentials and no
  execution path, and it never grants authority. ModelRig's T-038 grant and
  T-032 permission remain the only authority.

## How #1 would be accepted under A

Issue #1 is done when a fixture-backed end-to-end task produces a checkable
report and a consented live read-only test is documented. The status of each
part:

| #1 requirement | Evidence | Status |
| --- | --- | --- |
| Fixture-backed end-to-end task, real transport, no patching | ModelRig #2289, `tests/worker_home_rig_e2e_fixture.py`; CI workflow `t038-home-assistant-e2e` | In review |
| Negative cases: auth, timeout, redaction, no-write, unscoped entity | Same test, 31 checks, mutation-checked | In review |
| Report bound to its checkout (commit plus file hashes; not signed) | `--check` in #2289 | In review |
| Deterministic operator entry point for the live read | ModelRig #2290, `scripts/t038_operator_read.py` | In review |
| Consented live read-only test against Anders' Home Assistant | `docs/T038_HOME_ASSISTANT_LIVE_READ.md` | **PENDING**: needs Anders' consent and token |
| Windows token-file protection verified | Design in progress; see ModelRig #2289 | **PENDING** |
| KalivNexus role decided | This document | Waiting for a decision |

## Decision status

- **ChatGPT (cross-review, KalivNexus #1, comment 6428653971):** supports
  option A as the direction. ChatGPT states that this is a reviewer
  recommendation, **not** Anders' approval, and not permission to merge.
- **Anders:** not yet decided.

Until Anders decides:

- the schema stays at v0.1;
- no LAN egress is added to Nexus;
- nothing is activated.
