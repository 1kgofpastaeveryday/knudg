# Agent Access

Agent access is part of the product core, not a later integration layer. MVP must expose one narrow, auditable contract before adding more transports.

## MVP Transport Choice

MVP supports:

- local CLI using HTTPS to the Knudg API
- MCP over Streamable HTTP for protected tools
- optional local stdio wrapper that launches the CLI but does not hold long-lived credentials

The stdio wrapper is convenience glue only. Authorization is enforced by the HTTPS API boundary. The wrapper must not accept arbitrary remote server URLs unless the user explicitly configures and pins them.

HTTP MCP authorization follows the MCP authorization model for protected resources. Protected operations return HTTP `401` at the transport boundary, not tool-level soft errors.

## Credential Model

Agent clients use delegated user tokens with these default constraints:

- TTL: 15 minutes for write-capable tokens, 60 minutes for read-only search tokens
- refresh: no refresh token in MVP agent clients
- audience: `knudg-api` plus explicit environment, such as `prod` or `dev`
- scope: tenant, namespace, operation, and transport
- storage: OS keychain only; never plaintext config files
- binding: token includes a client instance ID and integration ID
- revocation: server-side token denylist checked on every protected request
- billing: paid/rerank scopes are separate from read/search scopes

Read and write scopes are separate. A token that can search private cards cannot submit, approve, publish, bill, or revoke unless those scopes are explicitly present.

## Protected Operations

| Operation | Purpose | Required scope | Idempotency | Timeout | Retry |
|---|---|---|---|---:|---|
| `search_similar` | Search authorized corpus from an outbound query profile | `search:{namespace}` | optional request ID | 2500 ms | yes, once |
| `get_card` | Fetch a specific authorized card version | `read:{namespace}` | no | 1000 ms | yes |
| `submit_candidate` | Submit a private candidate for admission | `submit:{tenant}` | required | 3000 ms | yes |
| `ask_approval` | Create a human approval challenge for a redacted artifact | `approval:create` | required | 3000 ms | yes |
| `approve_publication` | Complete one signed approval challenge | `approval:complete` | required | 3000 ms | no replay |
| `revoke_card` | Create a tombstone and block retrieval | `revoke:own` or `revoke:any` | required | 2000 ms | yes |
| `report_harmful_card` | Report prompt injection, stale, unsafe, or misleading card | `report` | optional | 1500 ms | yes |

All write operations require an idempotency key. Retried writes with the same request digest return the original effect. A reused key with a different digest is a hard error.

## Hook Events

Minimum hook events:

- `before_work`: optional bootstrap search before the agent starts a task
- `during_work`: sidecar retrieval during an active task
- `after_solve`: writer candidate generation after a solved, failed-only, or unknown-clarified case
- `before_prompt`: inline hint only when rollout stage allows it

Hook payloads must be sanitized outbound query profiles. They must not include raw logs, full stack traces, private paths, private repo names, secrets, tokens, full file contents, or customer identifiers.

## Search Response Contract

Every search response returns:

- `decision`: `show`, `sidecar_only`, or `no_suggestion`
- `abstention_reason`: `low_confidence`, `no_authorized_match`, `safety_gate`, `stale_index`, `rate_limited`, `service_degraded`, or `none`
- `threshold_version`
- `served_from`: `exact`, `fts`, `vector`, `hybrid`, `cache_metadata`, or `none`
- `latency_budget_ms`
- `index_generation`
- `revocation_epoch`
- `cards[]`

Each card item includes:

- card ID and card version
- namespace
- outcome type
- quality state
- trust label
- freshness status
- provenance summary
- deprecated, disputed, unsafe, or high-risk flags
- source event range
- signals used for ranking

## Display Labels

Agent and human surfaces must use the same trust labels:

- `Verified fix`
- `Repeated fix`
- `Single-session clue`
- `Known failed path`
- `Clarified unknown`
- `Disputed`
- `Deprecated`
- `Unsafe until reviewed`

These labels are presentation requirements, not just UI copy. They prevent solved, failed-only, unknown, and disputed cards from being shown as equivalent answers.

## Failure Behavior

Default failure behavior is no suggestion. A failed Knudg call must not block the main agent.

Failures return machine-readable reasons:

- `auth_required`
- `insufficient_scope`
- `rate_limited`
- `budget_exceeded`
- `service_degraded`
- `stale_or_revoked`
- `payload_rejected`
- `unsafe_candidate`

Inline hints must be disabled when the client cannot distinguish the failure reason.
