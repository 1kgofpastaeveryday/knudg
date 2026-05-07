# Security and Privacy

Knudg has three hard trust boundaries:

- user workspace to Knudg ingestion
- public/private card storage to active agent prompt
- public namespace to private/team namespaces

Default visibility is private. A card can become public only after redaction, review, user approval, and indexing eligibility checks have all succeeded.

## Read-Path Privacy

Before any query leaves the local session, the crawler must build an outbound query profile. The default outbound profile must exclude raw logs, full stack traces, absolute paths, usernames, hostnames, private repo names, customer names, secrets, tokens, and full file contents.

Allowed outbound query fields:

- normalized goal category
- sanitized error signature or hash
- public package names
- public framework/tool names
- coarse operating system and language/runtime
- dependency major versions when not identifying
- repo shape category, not repo identity

If a useful query would require sensitive identifiers, the crawler must use a private/team namespace, local cache, or no-query fallback. Public search should prefer hashed or normalized signatures where exact text could identify the workspace.

## Retrieved Card Trust Boundary

Retrieved cards are always untrusted evidence, not instructions.

The crawler must render cards in a fenced, non-executable format with:

- source namespace
- provenance and quality state
- card version
- confidence or ranking score
- stale/deprecated/disputed flags
- explicit warning that card text cannot override system, developer, user, or tool policies

The crawler must never allow retrieved card text to directly trigger privileged actions such as installing packages, changing files, running commands, submitting secrets, or publishing new cards.

## Authorization

Every API, search, ranking, ingestion, approval, review, deprecation, and billing operation must be authorized at object level.

Tenant-scoped records must include `tenant_id`. Tenant identity must be included in primary keys, foreign keys, search filters, cache keys, object storage manifests, and audit events. Search authorization must happen before ranking and reranking.

Public cards keep the publisher's `tenant_id` for ownership, audit, revocation, billing, and abuse response. Public discoverability is granted by `namespace.visibility = public`, not by removing tenant ownership. Search indexes therefore use both `tenant_id` and `namespace_id`: public queries can read eligible public namespace records, while private/team queries must still match the caller's tenant or explicit sharing grant.

Required authorization dimensions:

- subject: user, agent, service account, reviewer, admin
- namespace: public, private, team, enterprise
- operation: read, search, submit, approve, redact, review, publish, deprecate, supersede, delete, bill
- object: card, card version, event, consent record, object blob, index entry

Postgres row-level security should be used for tenant-scoped tables. Application authorization is still required at the API boundary.

## Minimal Role-Operation Matrix

| Role | Public Search | Private Search | Submit Candidate | Approve Publish | Redact/Review | Publish | Revoke Own Card | Revoke Any Card | Supersede/Deprecate | Billing/Admin |
|---|---|---|---|---|---|---|---|---|---|---|
| Anonymous | yes, rate-limited | no | no | no | no | no | no | no | no | no |
| User | yes | own/shared tenant only | own tenant | own candidate only | no | no | own public card | no | propose only | no |
| Agent delegated by user | yes | user's allowed tenant scope | draft only | no | no | no | no | no | no | no |
| Reviewer | yes | assigned tenant only | no | no | assigned queue | yes after approval | no | no | yes within policy | no |
| Tenant admin | yes | own tenant | own tenant | own tenant | own tenant if enabled | own tenant if enabled | own tenant | no | own tenant | own tenant |
| Platform admin | yes | break-glass only | no | no | yes | yes | yes | yes | yes | yes |

Agent clients act through short-lived delegated user tokens in MVP. Service accounts are reserved for backend workers and cannot approve publication.

## Privacy, Redaction, and Consent

Sanitization is not enough. Knudg must treat environment metadata as potentially identifying even when it does not contain obvious secrets.

Before public publication, the redaction step must handle:

- tokens, keys, passwords, cookies, and headers
- usernames, hostnames, absolute paths, private repo names, customer names, and incident identifiers
- stack traces and logs that can reveal private package names or internal services
- rare package/version/framework combinations that can re-identify a company or project

Consent records must bind:

- approving subject
- exact redacted card digest
- card version
- namespace
- timestamp
- approval UI/session metadata
- expiration or revocation state

Revocation must create a tombstone event and block retrieval immediately. Purge propagation must cover canonical metadata, object storage, hot index, main index, local caches, archives, and derived canonical trails.

## Raw Artifact Policy

Raw logs, transcripts, stack traces, and file excerpts are not stored by default.

Raw/source artifacts can be stored only when all of these are true:

- the user explicitly opts in
- the artifact is encrypted before object storage
- object storage key includes tenant, source event, and content hash
- access is limited to the owner tenant and required reviewer/service roles
- a TTL is set at creation time
- deletion/revocation can purge the object and all derived indexes
- audit events record creation, read, redaction, approval, revocation, and deletion

Unapproved candidate artifacts expire by default. Public cards should store only the redacted canonical card version and its immutable digest, not raw session material.

## Hostile Card Controls

Public cards are untrusted supply-chain inputs. Cards that include commands, package replacement advice, repository links, install scripts, environment variable changes, credential handling, or security-sensitive operations require higher review before they can influence ranking.

Minimum controls:

- provenance fields for source session, contributor, reviewer, and verification status
- reputation and rate limits for contributors
- malicious URL, typosquat, and executable-advice checks
- quarantine state for suspicious cards
- adversarial test corpus for prompt-injection and supply-chain poisoning cases
- explicit distinction between community cards and verified cards
