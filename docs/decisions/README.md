# Decision Backlog

This backlog prevents deferred design decisions from disappearing into prose. Status values: `open`, `defaulted`, `accepted`, `superseded`.

| ID | Decision | Status | Current default | Blocking milestone | Owner | Deadline |
|---|---|---|---|---|---|---|
| DEC-001 | MVP queue backend | defaulted | Postgres-backed queue | M1 | platform | first wedge RFC |
| DEC-002 | Agent access transport | defaulted | HTTPS API plus MCP Streamable HTTP, optional stdio wrapper | M5 | platform | M5 start |
| DEC-003 | Object storage provider | open | S3-compatible interface; not required while raw/source artifacts are disabled | M2 | platform | deployment RFC before first raw/source artifact storage |
| DEC-004 | Consent surfaces and commercial derived use | accepted | commercial derivative products are retired as a product direction; commercial/model-use scopes remain fail-closed safety boundaries | M2 | product/security | M2 start |
| DEC-005 | pgvector index parameters | defaulted | pgvector disabled for serving until retrieval RFC accepts HNSW parameters, manifest rules, and rollback criteria before M4 | M4 | search | M4 start |
| DEC-006 | Numeric production SLOs | defaulted | M3 exact/FTS thresholds in operations; later wedge RFC may replace with measured targets | M3 | ops | M3 start |
| DEC-007 | Quality promotion automation | open | operator-assigned only | M6 | product/search | M6 start |
| DEC-008 | Lifecycle value storage | accepted | lookup tables plus transition tables, fixed by RFC 0001 for M0 | M0 | data | M0 start |
| DEC-009 | Raw artifact retention | defaulted | off by default, max 30 days | M2 | security/product | M2 start |
| DEC-010 | Local card body cache | defaulted | disabled in MVP | M3 | platform/security | M3 start |
| DEC-011 | Mojibake source quote recovery | open | English intent summaries are authoritative for M0 schema only until source text is restored | External review | product | before external review |
| DEC-012 | M0 migration framework | accepted | repo-owned SQL migration runner plus Docker Compose Postgres default, fixed by RFC 0001 | M0 | data | before M0 code |
| DEC-013 | Public-search privacy thresholds | open | blocked until first wedge RFC defines numeric `k`, cohort floor, timing envelope, budget composition, HMAC key rotation, and rare-fingerprint probe corpus | M6 | security/search | first wedge RFC |
| DEC-014A | M3 internal protected-data sender-constrained proof profile | open | DPoP unless the M3 auth RFC accepts mTLS; protected-data harness blocked until accepted | M3 | platform/security | M3 start |
| DEC-014B | M5 external MCP/CLI sender-constrained proof profile | open | DPoP for public clients unless the M5 auth RFC accepts mTLS or another profile | M5 | platform/security | M5 start |
| DEC-015 | Circuit control plane | accepted | Postgres-backed `operational_circuits` table for MVP, protected by RLS/audit; if unavailable, auth/revocation/data-integrity circuits fail closed and cost/quality circuits use last-known-safe for at most 5 minutes | M3 | platform/ops | M3 start |
| DEC-016 | Production Postgres HA and PITR topology | accepted | managed Postgres HA with daily base backups, WAL archiving, PITR restore drill, replica failover within RPO, and restore into a quarantined new cluster before cutover | M2/M3 | platform/data | before M2 external exposure |
| DEC-017 | Production retrieval surface name | accepted | `retrieval_panel`; RFC 0002 may keep `subconscious sidecar` as a draft local experiment name | M3 | product/platform | M3 start |
| DEC-018 | Review and verification operations | open | separate RFC required before M1/M2 review queues or high-risk public display; defines reviewer lanes, assignment, verification expiry, re-verification, escalation, and malicious-card tests | M1/M2 | product/security | before M1 private writer queue |
| DEC-020 | Agent-native role orchestration | accepted | summoned per-task searcher/writer/nudger/reviewer roles before automatic hook or subconscious adapter; role verdicts are compact orchestration signals, not card delivery or action authority | M1/M3 | product/platform | before role wrapper implementation |
| DEC-021 | Current-work retrieval strategy | defaulted | derive bounded task profiles and hybrid query views from current work; exact/FTS remains first-class, vector search is additive after gates, and retrieval is adaptive/abstention-first | M3/M4 | search | before real retrieval implementation |
| DEC-022 | OSS public-good direction | accepted | Knudg is fully open-source public-good infrastructure; B2B monetization, paid private namespaces, paid retrieval tiers, respondent portals, and company/store dashboards are not revenue tracks | All | maintainers | accepted 2026-06-02 |
| WEDGE-001 | Initial MVP wedge | defaulted | developer tooling failures for agentic coding environments; M1 remains blocked while RFC 0003 is not accepted; private/team dogfood first, public pilot only after RFC 0003 public gates pass | M1 | product | before M1 private writer queue |
| DEC-019 | M0 claim-signing key custody | defaulted | local M0 uses DB-verified HS256 request contexts only for Docker/local development; key rows are disabled/rotated by `kid`, ordinary app roles cannot read keys or execute generic crypto helpers, and production/team custody remains blocked on asymmetric or KMS/Vault verification before publication flows | M0 | platform/security | before non-local M0 deployment |

## Options And Dependent Docs

Open/defaulted decisions must name viable options and the docs that change when
the decision is accepted.

| ID | Options | Dependent docs |
|---|---|---|
| DEC-001 | Postgres queue; dedicated queue service after M1; managed cloud queue after deployment RFC | `docs/architecture/implementation-readiness.md`, `docs/architecture/operations.md`, future M1 queue RFC |
| DEC-003 | S3-compatible managed object storage; self-hosted S3-compatible storage; disabled raw/source artifacts | `docs/architecture/security-privacy.md`, `docs/architecture/operations.md`, deployment RFC |
| DEC-005 | pgvector disabled; pgvector HNSW with filtered-recall gates; external vector store after M4 RFC | `docs/architecture/retrieval.md`, `docs/architecture/operations.md`, future M4 retrieval RFC |
| DEC-013 | conservative public thresholds; private/team-only wedge; no public search until measured cohort floor exists | `docs/product/strategy.md`, `docs/architecture/security-privacy.md`, first wedge RFC |
| DEC-014A | DPoP; mTLS for confidential internal clients; HTTPS-only synthetic/public harness until proof profile accepted | `docs/architecture/agent-access.md`, `docs/architecture/implementation-readiness.md`, M3 auth RFC |
| DEC-014B | DPoP; mTLS for confidential external clients; no external MCP/CLI until interop tests pass | `docs/architecture/agent-access.md`, `docs/architecture/implementation-readiness.md`, M5 auth RFC |
| DEC-015 | Postgres-backed circuit state; Redis/control-plane service; managed feature-flag/control-plane service | `docs/architecture/operations.md`, `docs/architecture/implementation-readiness.md`, deployment RFC |
| DEC-016 | managed Postgres HA; self-managed primary/replica with PITR; local-only dev Postgres before external exposure | `docs/architecture/operations.md`, `docs/architecture/implementation-readiness.md`, deployment RFC |
| DEC-017 | `retrieval_panel`; `sidecar`; `suggestion panel` | `README.md`, `docs/architecture/retrieval.md`, `docs/architecture/agent-access.md` |
| DEC-018 | minimal reviewer queue in M1; full review-ops RFC before M2; private/team-only until review-ops RFC accepted | `docs/product/strategy.md`, `docs/architecture/security-privacy.md`, future review-ops RFC |
| DEC-020 | automatic hooks first; complete `agent-subconscious` before Knudg roles; direct inline hinting from retrieved history | `docs/architecture/summoned-roles.md`, `docs/architecture/agent-access.md`, `docs/architecture/retrieval.md` |
| DEC-021 | manual search only; vector-only current-work similarity; hybrid task-profile retrieval with fusion and abstention | `docs/architecture/search-strategy.md`, `docs/architecture/retrieval.md`, `backlog/m3-retrieval.md` |
| DEC-022 | fully open-source public-good project; convenience hosted mirrors over the same open code; no B2B monetization or paid public retrieval | `README.md`, `GOVERNANCE.md`, `docs/product/strategy.md`, `docs/product/intent-crosswalk.md` |
| WEDGE-001 | accept RFC 0003 with measured pre-M1 values; choose private/team-only wedge; choose different first wedge and update strategy/readiness docs | `README.md`, `docs/product/strategy.md`, `docs/architecture/implementation-readiness.md`, `docs/rfcs/0003-wedge-001-agentic-coding-tooling.md` |
| DEC-019 | asymmetric verifier with public key in DB; external KMS/Vault verification; local HS256 only with envelope encryption and emergency rotation | `docs/rfcs/0001-m0-schema-event-log.md`, M0 DDL appendix |

## Decision Rules

- A default is binding until changed by an accepted RFC.
- Open decisions cannot block earlier milestones unless listed in the table.
- A decision that changes privacy, consent, tenant isolation, revocation,
  public-interest sustainability, cost controls, or billing requires an accepted
  RFC amendment or decision record update. Supporting review evidence must be
  public-safe before it is committed.
- A superseded decision must link to its replacement.
