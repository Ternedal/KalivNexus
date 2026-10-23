# KalivNexus capability manifest v0.1 — proposal

**Status: draft schema, not a deployed registry or runtime contract.** This file describes a candidate provider capability manifest for design review. It does not confer authorization or enable external access.

## Example: read-only weather lookup

```json
{
  "manifest_version": "0.1",
  "capability_id": "weather.current.read",
  "provider_id": "example-weather",
  "adapter_version": "0.1.0",
  "display_name": "Current weather",
  "description": "Read current conditions for a user-approved location.",
  "operation": "read",
  "approval": "modelrig_policy",
  "enabled_by_default": false,
  "auth": {
    "type": "api_key",
    "secret_ref": "vault://kalivnexus/example-weather"
  },
  "network": {
    "allowed_https_hosts": ["api.example.invalid"],
    "allow_redirects": false,
    "timeout_ms": 5000,
    "max_response_bytes": 262144
  },
  "privacy": {
    "data_classification": "location",
    "external_transfer": true,
    "retention": "provider_terms_review_required"
  },
  "limits": {
    "max_requests_per_minute": 30,
    "max_concurrency": 2,
    "max_cost_per_call_usd": 0
  },
  "retry": {
    "max_attempts": 2,
    "backoff_ms": 250,
    "idempotent": true
  },
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["location"],
    "properties": {
      "location": {"type": "string", "minLength": 1, "maxLength": 160}
    }
  },
  "output_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["summary"],
    "properties": {
      "summary": {"type": "string", "maxLength": 2000}
    }
  }
}
```

The host `api.example.invalid` and secret reference are **deliberately nonfunctional placeholders**. No real provider is registered.

## Proposed validation rules

1. Reject unknown manifest versions, duplicate capability IDs, unknown operations and unknown approval modes.
2. Require explicit opt-in: `enabled_by_default` must be `false`; an approved, persisted registry state is separately required to activate a capability.
3. Reject URLs, credentials, IP addresses, wildcards and local hostnames where `allowed_https_hosts` expects DNS hostnames. Resolve and revalidate addresses at connection time to prevent DNS rebinding and private-network SSRF.
4. Reject non-HTTPS transport and cross-host redirects; bound payload size, latency, concurrency and retries.
5. Treat the declared `operation` and `approval` as metadata only. ModelRig must independently authorize each invocation and require confirmation for side effects.
6. Resolve `secret_ref` only inside the trusted execution service; never return its contents to models, clients or logs.
7. Validate input and output against the declared schemas; sanitize output before passing it into prompts or downstream tools.
8. Do not allow a provider to change scopes, domains, prices or schemas without re-review and an explicit manifest version bump.
9. Keep the provider's terms, data-transfer disclosures and retention policy alongside approval evidence.

## Acceptance before implementation claims

- [ ] Publish a machine-readable JSON Schema for this manifest and negative validation fixtures.
- [ ] Implement a signed/approved registry with version pinning and revocation.
- [ ] Implement ModelRig authorization and user confirmation, tested with denied and forged requests.
- [ ] Implement DNS/IP enforcement, redirect blocking, rate/cost limits and secret redaction.
- [ ] Exercise contract tests against a fake provider, then one approved real provider.
- [ ] Verify end-to-end traces, failure handling and rollback.

See [architecture decisions](ARCHITECTURE_DECISIONS.md) and [repository overview](../README.md).
