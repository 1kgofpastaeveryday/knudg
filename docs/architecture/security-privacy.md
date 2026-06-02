# Security and Privacy

Knudg has three hard trust boundaries:

- user workspace to Knudg ingestion
- public/private card storage to active agent prompt
- public namespace to private/team namespaces

Default visibility is private. A card can become public only after redaction, review, user approval, reviewer publish, and indexing eligibility checks have all succeeded.

## Read-Path Privacy

Before any query leaves the local session, the crawler must build an outbound query profile. The default outbound profile must exclude raw logs, full stack traces, absolute paths, usernames, hostnames, private repo names, customer names, secrets, tokens, and full file contents.

Allowed outbound query fields:

- normalized goal category
- sanitized error signature or hash
- public package names
- public framework/tool names
- normalized command family and stack-frame fingerprint only when the
  server-side classifier proves the values are public/non-identifying
- coarse operating system and language/runtime
- dependency major versions when not identifying
- repo shape category, not repo identity
- client-claimed publicness, risk, and privacy-budget classes only as hints;
  server-derived verdicts decide retrieval, ranking, telemetry, and cache use

If a useful query would require sensitive identifiers, the crawler must use a private/team namespace, local cache, or no-query fallback. Public search should prefer hashed or normalized signatures where exact text could identify the workspace.

Public exact-match fingerprints use keyed HMAC or another keyed server-side
fingerprint, not unsalted public hashes. Rare combinations of package, version,
framework, error, OS, and repo shape are suppressed from public search unless
they meet private operator-configured distinct-tenant and cohort-size thresholds
for the active wedge. Exact threshold values are not public-facing material.
Search must normalize timing and failure reasons so callers cannot distinguish
"rare private fingerprint", "not indexed", "redacted", and "no match". Rare
public queries return a generic abstention, consume privacy budget, and are
subject to stricter private rate limits.

Distinct-tenant thresholds are only one control, not the privacy proof. Public search for a wedge or fingerprint family must stop when test probes show singling-out, cohort differencing, timing-envelope leakage, distributed enumeration, or auxiliary-information linkage against a tenant, user, repo, host, customer, or incident. Stop decisions must consider result shape, abstention class, latency, retry behavior, and rate-limit behavior, not just returned card bodies.

Public abuse budgets are enforced before candidate generation. The MVP must define per-subject, per-IP, per-API-key, and per-fingerprint-family budgets for:

- rare-fingerprint probes
- high-cardinality normalized error probes
- repeated generic abstentions
- namespace or wedge enumeration patterns
- requests containing path, hostname, repo, token-shape, or credential-like material

Budget exhaustion returns the same generic public abstention or a coarse rate-limit class. It must not reveal which budget, fingerprint family, or policy gate fired.

## Abuse Identity And Enforcement

Knudg needs an abuse-enforcement lane for repeated malicious submissions,
review manipulation, fake experience claims, harassment, spam, brigading, and
attempts to use the platform to target companies, stores, staff, interviewers,
or users. This lane is separate from experience-card retrieval and separate
from respondent/business inquiry products.

The abuse lane may maintain protected identity signals such as account ID,
verified contact channel, payment/customer account when applicable, device or
session risk label, IP/network risk bucket, submission fingerprint, and
moderation history. These signals are enforcement data, not card content. They
must not be exposed in retrieval panels, public cards, aggregate reports,
business dashboards, respondent inquiry responses, exports, or ranking
features except through coarse abuse-state gates.

Abuse identity storage requirements:

- identity signals use tenant- or service-keyed protected fingerprints where
  raw values are not required
- raw identifiers are minimized, encrypted, TTL-bound where possible, and
  access-controlled to trust-and-safety roles
- every privileged lookup requires a case reason, purpose, and audit event
- normal reviewers may see only the enforcement status needed for the case,
  not raw identity signals
- target companies, stores, respondents, or B2B customers never receive user
  identity signals, raw source material, or re-identification hints through the
  inquiry or insights surface
- enforcement decisions are monotonic and reviewable: warn, rate-limit,
  hold-for-review, suspend, ban, appeal, reinstate, and revoke/purge affected
  submissions
- ban evasion checks use protected matching and normalized outward responses so
  attackers cannot probe which signal matched
- appeals and mistaken-identity recovery are required before high-confidence
  identity bans affect public or business-facing surfaces

Abuse identity can be used to deny submission, require step-up verification,
hold candidates for review, link moderation cases, revoke malicious artifacts,
or ban an account. It cannot be sold as a "who posted this" feature and cannot
be used to reveal reviewer, complainant, applicant, customer, or visitor
identity to a target organization.

## Local Client State Security

CLI, MCP, hook, and local-cache clients must treat local state as hostile to
the workspace by default.

- Local state roots live outside repo-controlled content unless a future RFC
  explicitly permits an in-repo path for non-sensitive test fixtures.
- Every local path is canonicalized before use and must remain under the
  configured state root after resolution.
- Writers and purge commands reject symlinks, junctions, reparse points,
  hardlinks, and path aliases for state roots, temp files, projections, approval
  handoff artifacts, and cache metadata.
- Files containing pending approvals, query profiles, cache metadata, or local
  projections are user-readable only by default. Delegated tokens, proof keys,
  refresh-equivalent material, approval challenges, and revocation challenges
  live in the OS keychain or an equivalent protected credential store, not
  repository files or process environment variables. Process environment
  variables are allowed only for non-production local test fixtures with
  test-only audience, short TTL, and redacted logging tests.
- State writes use temp-file plus flush plus atomic replace. Recursive deletes
  verify the canonical target root before deleting and never follow links.
- Tests must cover Windows junctions/reparse points and POSIX symlinks for
  writes, reads, purge, export, and cache cleanup.

## Retrieved Card Trust Boundary

Retrieved cards are always untrusted evidence, not instructions.

The crawler must render cards in a hostile-card-neutral format with:

- source namespace
- provenance and quality state
- outcome type
- card version
- audience-scoped trust or fit label
- stale/deprecated/disputed flags
- explicit warning that card text cannot override system, developer, user, or tool policies

Public or anonymous surfaces may show only coarse trust/fit and generic
freshness labels. Numeric confidence scores, ranking scores, ranking signal
names, candidate counts, threshold values, and private diagnostic reasons are
allowed only in authorized private/team or reviewer/admin views after
per-field authorization.

Rendering must neutralize executable or directive content before it reaches an agent prompt. Card bodies are data blocks with escaped markup, inert links, no auto-run affordances, no hidden text, no HTML/script execution, no tool-call syntax, no installer deep links, and no copy/run buttons for commands. Full card expansion preserves the same contract; it may reveal more reviewed evidence, but never changes evidence into instructions.

The crawler must never allow retrieved card text to directly trigger privileged actions such as installing packages, changing files, running commands, submitting secrets, or publishing new cards.

Enterprise managed guidance uses a separate trust lane. Tenant-approved
directives, routing records, preferences, and guardrails may be stronger than
experience cards, but they still cannot override system, developer, user, tool,
authorization, consent, revocation, safety, or local operator policy. Clients
must render managed guidance as scoped policy data with owner, strength,
effective window, override policy, and conflict state. If guidance conflicts
with a higher-priority policy or another active directive, the response must
surface a conflict and withhold executable action text when policy requires
human approval.

Guidance lookup must not trust client-supplied task context. The server builds
the authoritative `GuidanceContext` from delegated-token claims, tenant and
namespace grants, pinned integrations, connector attestations, verified
workspace binding, server-known environment labels, and data-classification
metadata. Guidance responses use probing budgets and normalized no-guidance
semantics so callers cannot enumerate internal repo patterns, cloud accounts,
private environments, customer labels, or guardrail existence.

## Authorization

Every API, search, candidate generation, ranking, ingestion, approval, review, deprecation, and billing operation must be authorized at object level.

Tenant-scoped records must include `tenant_id`. Tenant identity must be included in primary keys, foreign keys, search filters, cache keys, object storage manifests, and audit events. Search authorization must happen before candidate generation, ranking, and reranking.

Public cards keep the publisher's `tenant_id` for ownership, audit, revocation, billing, and abuse response. Public discoverability is granted by `namespace.visibility = public`, not by removing tenant ownership. Search indexes therefore use both `tenant_id` and `namespace_id`: public queries can read eligible public namespace records, while private/team queries must still match the caller's tenant or explicit sharing grant.

Required authorization dimensions:

- subject: user, delegated agent, ingestion worker, approval challenge worker,
  redaction worker, review worker, trust-and-safety worker, abuse enforcement
  worker, index worker, compaction worker, revocation worker, billing worker,
  reviewer, tenant admin, platform admin
- namespace: public, private, team, enterprise
- operation: read, search, submit, approve, redact, review, publish, deprecate, supersede, delete, bill
- object: card, card version, event, consent record, object blob, index entry

Postgres row-level security should be used for tenant-scoped tables. Application authorization is still required at the API boundary.

Tenant-scoped tables use `(tenant_id, id)` primary or unique keys, and foreign keys include `tenant_id`. Row-level security is mandatory for normal application roles. Policies must define both `USING` and `WITH CHECK`. Roles with `BYPASSRLS` are prohibited for application traffic; break-glass access is a separate audited role with time-bound approval.

## Minimal Role-Operation Matrix

| Role | Public Search | Private Search | Submit Candidate | Approve Publication | Redact/Review | Reviewer Publish | Revoke Own Consent/Artifact | Revoke Any Subject | Supersede/Deprecate | Billing/Admin |
|---|---|---|---|---|---|---|---|---|---|---|
| Anonymous | no until M6/DEC-013 and wedge public-search gates; then yes, rate-limited | no | no | no | no | no | no | no | no | no |
| User | no public search until M6/DEC-013 and wedge public-search gates; eventual capability after gates | own/shared tenant only | own tenant | own candidate only | no | no | own consent records, private candidate collection, retained artifacts, derived-use grants, raw/source retention, model/eval use, public cards | no | propose only | no |
| Agent delegated by user | no public search until M6/DEC-013 and wedge public-search gates; eventual capability after gates | user's allowed tenant scope | draft only | no | no | no | no | no | no | no |
| Ingestion worker | no | scoped source read only | create queued artifacts | no | no | no | no | no | no | no |
| Approval challenge worker | no | assigned approval artifact only | no | challenge handoff creation only | no | no | no | no | no | no |
| Redaction worker | no | assigned artifact only | no | no | redact only | no | no | no | no | no |
| Review worker | no | assigned review queue only | no | no | queue routing only | no | no | no | no | no |
| Trust-and-safety worker | no | assigned abuse case only | hold/reject only | no | assigned abuse review only | no | no | no | no | no |
| Abuse enforcement worker | no | enforcement metadata only | enforce deny/hold only | no | no | no | no | no | no | no |
| Index worker | public index write only | authorized namespace read for indexing | no | no | no | no | no | no | no | no |
| Compaction worker | public index write only | authorized namespace read for compaction | no | no | no | no | no | no | propose only | no |
| Revocation worker | no | tombstone propagation only | no | no | no | no | tombstone propagation only | tombstone propagation only | no | no |
| Billing worker | no | no | no | no | no | no | no | no | no | metering only; no billing until meter reconciliation passes |
| Reviewer | no public search until M6/DEC-013 and wedge public-search gates; reviewer/admin fixtures only before then | assigned tenant only | no | no | assigned queue | yes after approval | no | no | yes within policy | no |
| Tenant admin | no public search until M6/DEC-013 and wedge public-search gates | own tenant | own tenant | policy/admin review only; cannot satisfy user consent | own tenant if enabled | no unless reviewer-assigned | own tenant policy/admin artifacts only; cannot revoke another user's consent, private retention, raw/source retention, model/eval permission, or public approval except through audited break-glass | no | own tenant | own tenant |
| Platform admin | no public search until M6/DEC-013 and wedge public-search gates; break-glass fixtures only before then | break-glass only | no | no | yes | break-glass only | break-glass only | break-glass only | break-glass only | admin only; mutations require break-glass |

Agent clients act through delegated user tokens as defined in [Agent Access](agent-access.md). Non-human principals are separate worker identities, not a generic service-account role. Each worker has one purpose-bound credential, no user-consent or reviewer-publish scope, tenant and namespace filters in every query, and append-only audit events for reads and writes. Trust-and-safety and abuse-enforcement workers may see only case-scoped protected identity signals and coarse enforcement state; they cannot publish, complete consent, sell identity data, or answer respondent requests with user-identifying material. Worker database roles must use RLS like application roles; `BYPASSRLS` is prohibited outside audited break-glass access.

Compaction workers cannot commit `superseded` or `deprecated` lifecycle
transitions. They may emit a policy-bound proposal event that names the source
card version, replacement or deprecation evidence, compaction policy version,
cluster manifest, and deterministic digest. A reviewer must accept that proposal
through the canonical lifecycle transition table before the card status changes.
Policy events are evidence for a reviewer decision, not an independent mutation
authority.

Approval completion is written only by a user-bound approval endpoint after step-up authentication. The stored actor is `app_user` or a future explicitly delegated human subject role. Challenge workers and agents can request a trusted approval handoff but cannot emit `private_approved` or `publication_approved`.

Break-glass access requires a DB-backed case record, case ID, time limit, two-person approval, immutable audit event, and post-access review. The case record must name the exact subject, tenant, namespace, operation, objects or object class, reason, expiry, approving humans, and whether access is read-only or mutating. Platform admin access to private/team search is read-only during break-glass unless a separate emergency mutation approval exists. Each mutation type, such as publish, revoke, delete, purge, supersede, deprecate, billing adjustment, or consent-state change, requires mutation-specific two-person approval bound to the case and cannot inherit approval from a read case.

All read paths must pass the revocation fence before returning data. This includes search, `get_card`, approval artifacts, raw/source artifacts, derived canonical trails, ranking/reranking inputs, cache reads, exported artifacts, and reviewer/admin views. A missing, stale, or unreachable tombstone/epoch check fails closed with no body. Caches store the revocation epoch used to create the entry and must revalidate it before serving.

Revocation read algorithm:

1. Read the requester tenant revocation epoch at request start. For public or
   cross-tenant search, collect the publisher tenant IDs for candidate rows
   before ranking/body expansion and read each publisher tenant epoch.
2. Build candidates only inside the authorized tenant/namespace scope.
3. Apply tombstone anti-joins or equivalent deny predicates for tenant,
   namespace, card, card version, source artifact, derived artifact, and index
   generation before ranking or body expansion. Public search applies these
   predicates for every candidate publisher tenant, not only the requester.
4. Recheck returned IDs and every involved tenant epoch after ranking and
   before response serialization.
5. If any involved epoch advanced mid-request, retry once inside the request
   deadline or return `stale_or_revoked` with no body.
6. Cache hits must carry the epoch used to create the entry and must revalidate
   against the current epoch before display; stale cache entries are discarded,
   not refreshed in place.

Tests must cover revoke-during-search, revoke-during-body-expansion,
stale-local-cache, stale-index-generation, and reviewer/admin read paths.

## Privacy, Redaction, and Consent

Sanitization is not enough. Knudg must treat environment metadata as potentially identifying even when it does not contain obvious secrets.

Before public publication, the redaction step must handle:

- tokens, keys, passwords, cookies, and headers
- usernames, hostnames, absolute paths, private repo names, customer names, and incident identifiers
- stack traces and logs that can reveal private package names or internal services
- rare package/version/framework combinations that can re-identify a company or project

Package and repository identifiers are not considered public just because a
client labels them that way. Before a query profile, candidate, or card payload
can include package/repository identifiers as public metadata, Knudg must run a
classifier that performs ecosystem-specific canonicalization, registry or host
existence checks, private-scope deny rules, org-scope allowlists,
Unicode/confusable normalization, and a fail-closed verdict when publicness is
not proven. The classifier version and verdict are stored in query/audit
metadata.

Writer and redactor workers process source material as untrusted data, never as
instructions. Any model-assisted candidate generation or redaction must use
structured output, no tools, no network access, no approval or publish scope,
and a positive allowlist of output fields. The pipeline runs secret scanners
before and after generation, rejects source text that attempts to override
redaction or publication policy, and keeps adversarial prompt-injection
fixtures for logs, transcripts, stack traces, commands, URLs, and credentials.

Database-side intake repeats the safety check before Knudg accepts
non-synthetic candidate content. Client-side sanitization is treated as a claim,
not authority. The intake gate combines deterministic scanners with a no-tool
LLM classifier that returns only structured verdicts. It checks for secrets,
customer or incident data, private repository identifiers, raw transcripts,
internal architecture disclosure, high-entropy credential-like strings, and
embedded prompt-injection or policy-override text. The gate fails closed when
scanner, classifier, policy-version, or audit persistence is unavailable.
`accept` may enter admission; `redact_then_retry` requires a new protected
fingerprint before storage; `human_review_required` stores no candidate body and
may create only a sealed, encrypted, TTL-bound human-review escrow with
step-up-auth access; and `reject` stores only a redacted audit event.

Post-publication withdrawal of `public_publication` consent is retrieval
affecting. It must terminate the consent record and create tombstones for every
affected public artifact/card version/index subject, or the read path must
prove an active-consent deny check before search, expansion, rerank, cache,
export, and derived use. Knudg uses tombstones as the canonical M0/M1 deny
source for published artifacts.

Legal hold never permits retrieval after revocation. When a revoked subject is
under legal hold, Knudg creates the same tombstones and denies all normal read,
search, export, model/eval, and derived-use paths immediately. Physical purge
is deferred or replaced by crypto-shred only when the hold policy allows it;
held bytes are visible only through audited break-glass/legal-review surfaces.
When the hold is released, the purge job replays the tombstone subjects and
completes physical deletion before the subject can be considered fully purged.

Intake responses must not become a DLP oracle. External responses return only
coarse classes and never include matched values, offsets, detector names,
customer/repository existence hints, entropy scores, classifier confidence, or
private policy details. Detailed findings are limited to authorized
reviewer/admin surfaces with audit and rate limits.

The LLM classifier is protected data processing. It requires deterministic
pre-filtering, no tools, no retrieval, private deployment or contractual
zero-retention inference, no training on prompts or outputs, disabled provider
logging where available, tenant-scoped encryption, prompt/output retention
limits, access audit, purge capability, and requalification before provider,
model, prompt, or policy changes. If those controls cannot be proven, the
classifier receives only derived features and ambiguous raw content routes to
human review.

Consent records must bind:

- approving subject
- exact redacted card digest
- card version
- namespace
- approved derived-artifact policy, if any
- timestamp
- approval UI/session metadata
- expiration or revocation state

Approval UI must show the exact public artifact and a clear redaction summary before approval. It must distinguish:

- public card publication
- short-TTL intake review escrow for ambiguous raw submissions
- raw/source artifact retention
- deterministic derived artifacts, such as canonical trails
- editorial or monetized derived artifacts, such as curated packs

Consent for a public card does not automatically grant consent for intake
review escrow, raw artifact retention, editorial rewriting, curated packs,
model training, or any derived artifact that reveals new detail or materially
changes meaning. Intake review escrow consent is narrower than raw/source
retention: it allows encrypted, TTL-bound, single-use human safety review of
the exact submitted artifact only, and withdrawal or expiry must purge the
escrow. Derived artifacts need an explicit inheritance rule or renewed
approval.

Charging for access, quota, latency, or reranking over the already-public corpus is separate from commercializing a new artifact. Public-card consent can support paid retrieval over the public corpus only when the returned artifact is the exact approved public card or a policy-allowed deterministic projection. Separate commercial or curated consent is required for sponsored packs, editorial rewrites, paid compilations, training/eval sets, or any derivative that packages, ranks, annotates, or recontextualizes the card beyond the approved retrieval surface.

The consent surface matrix and approval/revocation interaction requirements are defined in [Consent and Revocation UX](consent-revocation-ux.md). Publication approval uses a one-time signed challenge bound to subject, tenant, namespace, card version, redacted digest, derived-use policy, raw-retention policy, origin, and expiry. Publish, raw retention, commercial derived use, and model/eval use require step-up reauthentication.

Retrieval-affecting revocation must create a tombstone event and block
retrieval immediately. The tombstone table is a mandatory read-path deny source
independent of card lifecycle status. Consent-only termination writes a
`consent_terminated` event and updates `consent_records`; it creates no
tombstone unless the same user action revokes a tenant, namespace, card, card
version, source artifact, derived artifact, or index subject. Purge propagation
for retrieval-affecting revocation must cover canonical metadata, object
storage, hot index, main index, local caches, archives, and derived canonical
trails.

High-risk classification is part of the canonical card payload and indexed projections. Before `published`, `indexed_hot`, or `indexed_main`, every card version must carry safety metadata such as `safety_class`, executable-advice flags, URL/package/repository indicators, credential/billing/deletion/network-call indicators, verification state, and withheld reason when blocked. Cards lacking required safety metadata fail closed and are not indexable.

URL handling uses one security policy across ingestion, review, rendering, preview, and scanner paths. Only `https` links are allowed by default. The URL fetch primitive must validate the canonical URL, resolve all A/AAAA records through controlled resolvers, reject any non-global IP, connect only to the validated IP set with hostname/SNI verification, revalidate every redirect, route through an egress proxy or firewall that blocks private, loopback, link-local, multicast, reserved, and cloud metadata ranges, disable automatic unfurling, and store resolver/IP/verdict metadata before expansion or indexing.

## Raw Artifact Policy

Raw Knudg logs, transcripts, stack traces, command output, and file excerpts must
not be transmitted out of the local environment before explicit user approval.
Pre-approval live nudge/search calls may send only sanitized query profiles or
other bounded metadata that excludes raw logs, source excerpts, secrets,
credentials, private paths, customer identifiers, and full stack traces.

User approval is path-specific. Approval to create a redacted public card does
not approve raw artifact retention. Approval to retain a private artifact does
not approve team sharing, public publication, model/eval use, or commercial
derived use. Each transfer path must show the exact artifact or policy-bound
summary that will leave local control before completion.

Raw logs, transcripts, stack traces, and file excerpts are not stored by default.

Raw/source artifacts can be stored only when all of these are true:

- the user explicitly opts in
- the consent surface states who can read it, why, and for how long
- the artifact is encrypted before object storage
- object storage key includes tenant, source event, and content hash
- access is limited to the owner tenant and required reviewer/service roles
- a TTL is set at creation time
- deletion/revocation can purge the object and all derived indexes
- audit events record creation, read, redaction, approval, revocation, and deletion

Raw/source artifact encryption uses tenant-scoped envelope encryption. Each artifact stores the encrypted object key, content hash, KMS key ID, per-object data-key metadata, consent record ID, source event ID, expiry, retention policy, and deletion state. Key rotation, emergency rotation, break-glass decrypt, and crypto-shred on TTL expiry are mandatory operational capabilities.

Unapproved candidate artifacts expire by default. Public cards should store only the redacted canonical card version and its immutable digest, not raw session material.

## Hostile Card Controls

Public cards are untrusted supply-chain inputs. Cards that include commands, package replacement advice, repository links, install scripts, environment variable changes, credential handling, or security-sensitive operations require higher review before they can influence ranking.

Minimum controls:

- provenance fields for source session, contributor, reviewer, and verification status
- reputation and rate limits for contributors
- reviewer QA with calibrated rubrics, dual-review sampling, malicious-card seeded tests, false-approval thresholds, and periodic reviewer calibration
- reviewer account hardening: MFA, step-up authentication for publish and high-risk decisions, short reviewer sessions, device/session binding where available, and signed reviewer decisions tied to the exact card version digest
- high-risk executable, package, repository, credential, billing, migration, or security-posture cards require two-person reviewer approval before public display or ranking influence
- immutable reproduction manifests for verified cards, including environment digest, inputs, outputs, version bounds, reviewer IDs, and remaining risk
- deterministic supply-chain verification profiles per ecosystem, including
  normalized package coordinates, registry source, publisher or maintainer
  signals, provenance attestations where available, lockfile or hash evidence,
  typosquat/confusable thresholds, repository ownership checks, and mandatory
  recorded verdicts before high-risk cards can affect display or ranking
- reviewer reputation can prioritize audit depth or queue routing, but cannot bypass high-risk verification, malicious-card tests, dual-review sampling, or revocation review
- malicious URL, typosquat, and executable-advice checks
- safety review state `quarantined` for suspicious cards; this is `payload_json.safety.review_state`, not a lifecycle status, and quarantined cards are not public-searchable, indexable, publishable, or eligible for retrieval-panel display until cleared by review
- adversarial test corpus for prompt-injection and supply-chain poisoning cases
- explicit distinction between community cards and verified cards

Public publication pauses for a wedge when seeded malicious cards are approved above threshold, calibration agreement falls below threshold, or a reviewer approves a false high-risk card. False approval events must create an audit case, remove affected cards from search until re-reviewed, and pause any reviewer reputation shortcut or expanded queue privileges for the involved reviewer until remediation is complete.

Residual prompt-injection and hostile-card risk must have an explicit
acceptance profile before public or inline retrieval launches. The profile
defines card classes that never become inline, maximum tolerated hostile-card
pass rate, mandatory regression corpus, model/provider change requalification,
and rollback when attack success exceeds threshold.

High-risk cards that include commands, package replacements, repository links, install scripts, environment variable changes, repo migration steps, or credential handling cannot appear as inline hints or retrieval-panel cards until verified. Before verification, the response may show only a generic "withheld pending verification" state with no command text, package name, repository URL, token shape, or credential-bearing detail. Package, repository, URL, install, migration, and credential advice requires typosquat checks where applicable, malicious URL checks where applicable, sandbox reproduction or equivalent isolated validation, and reviewer approval before it can improve ranking or be displayed.

High-risk wedge verification is mandatory before public display can include summaries. A card is high-risk if it can cause dependency changes, command execution, credential exposure, data deletion, network calls to a third party, repository migration, CI/CD mutation, billing impact, or security posture changes. Verification must record the isolated reproduction environment, inputs used, expected and observed outcome, reviewer identity, version bounds, and remaining risk. Summary displays for verified high-risk cards must show only the minimum actionable shape: affected public package/tool, verified version range, outcome type, freshness, and a non-executable next-step summary. They must omit raw commands, install lines, repository URLs, secrets, tokens, private paths, hostnames, and environment-specific identifiers until the user opens the full verified card inside an authorized client.

Renderer hostile-card tests must cover invisible Unicode, bidi controls,
zero-width characters, hidden HTML/CSS, Markdown autolinks, deceptive link
labels, oversized context padding, fake approval/reviewer text, and
screen-reader/model-delivery divergence. Golden tests compare raw payload,
rendered DOM, screen-reader text, copied text, and model-delivered card text.

High-risk reproduction must run in a containment profile before any verified
state is recorded. The profile uses an ephemeral VM or container with no
production secrets, no cloud metadata credentials, no host workspace mount
except explicit read-only fixtures, deny-by-default egress, package registry
allowlists for the wedge under test, bounded CPU/memory/time, transcript
redaction, and artifact hash capture. Any exception requires a policy record,
two-person approval, and a non-public verification state until the exception is
reviewed.
