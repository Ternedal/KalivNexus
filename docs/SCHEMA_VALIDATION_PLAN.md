# KalivNexus manifest schema validation plan

The draft machine-readable schema is at [`schemas/capability-manifest-v0.1.schema.json`](../schemas/capability-manifest-v0.1.schema.json). It implements **structural** checks, not runtime security enforcement.

## Minimum fixtures to add to automated tests

| Case | Expected |
| --- | --- |
| Documented read-only weather example | Accept structurally |
| Missing required field | Reject |
| Unknown property | Reject |
| `enabled_by_default: true` | Reject |
| `operation: destructive` with `approval: modelrig_policy` | Reject |
| Negative timeout or zero concurrency | Reject |
| HTTP URL or literal IP in allowed hosts | Reject |
| Redirects enabled | Reject |
| Unknown auth mechanism | Reject |
| Malformed input/output JSON Schema | Reject at separate schema-compilation step |

## Security boundaries not guaranteed by this schema

- DNS resolution, IP range blocking and re-resolution on connect
- Secret-vault existence, secret access policy and redaction
- User/session authorization and consent receipts
- Rate limits, costs, idempotency and actual retry behavior
- Provider identity, signed manifests, trust and version revocation
- Correct JSON Schema compilation for nested `input_schema` and `output_schema`

## Release gate

Do not activate any provider until automated positive/negative fixture tests, runtime egress controls, approval enforcement and real provider contract tests have passed at a pinned revision. The JSON Schema file is an initial design artifact, **not** an activated integration.
