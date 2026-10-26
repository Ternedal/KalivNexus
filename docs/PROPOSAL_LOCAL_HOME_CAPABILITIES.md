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

## Decision needed

From ChatGPT (cross-review) and Anders: choose A, B or C. Until then:

- the schema stays at v0.1;
- no LAN egress is added to Nexus;
- nothing is activated.
