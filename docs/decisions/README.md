# Decision Backlog

This backlog prevents deferred design decisions from disappearing into prose. Status values: `open`, `defaulted`, `accepted`, `superseded`.

| ID | Decision | Status | Current default | Blocking milestone | Owner | Deadline |
|---|---|---|---|---|---|---|
| DEC-001 | MVP queue backend | defaulted | Postgres-backed queue | M1 | platform | first wedge RFC |
| DEC-002 | Agent access transport | defaulted | HTTPS API plus MCP Streamable HTTP, optional stdio wrapper | M5 | platform | M5 start |
| DEC-003 | Object storage provider | open | S3-compatible interface; not required while raw/source artifacts are disabled | M2 | platform | deployment RFC before first raw/source artifact storage |
| DEC-004 | Consent surfaces and commercial derived use | defaulted | commercial curated packs require separate consent | M2 | product/security | M2 start |
| DEC-005 | pgvector index parameters | open | define in retrieval RFC before M4 | M4 | search | M4 start |
| DEC-006 | Numeric production SLOs | open | provisional budgets in implementation readiness | M3 | ops | M3 start |
| DEC-007 | Quality promotion automation | open | operator-assigned only | M6 | product/search | M6 start |
| DEC-008 | Lifecycle value storage | accepted | lookup tables plus transition tables, fixed by RFC 0001 for M0 | M0 | data | M0 start |
| DEC-009 | Raw artifact retention | defaulted | off by default, max 30 days | M2 | security/product | M2 start |
| DEC-010 | Local card body cache | defaulted | disabled in MVP | M3 | platform/security | M3 start |
| DEC-011 | Mojibake source quote recovery | open | English intent summaries are authoritative for M0 schema only until source text is restored | External review | product | before external review |
| DEC-012 | M0 migration framework | accepted | repo-owned SQL migration runner plus Docker Compose Postgres default, fixed by RFC 0001 | M0 | data | before M0 code |

## Decision Rules

- A default is binding until changed by an accepted RFC.
- Open decisions cannot block earlier milestones unless listed in the table.
- A decision that changes privacy, consent, tenant isolation, revocation, or billing requires a review note in `docs/plans/`.
- A superseded decision must link to its replacement.
