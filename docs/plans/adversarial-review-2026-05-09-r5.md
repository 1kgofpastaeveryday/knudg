# Adversarial Design Review - 2026-05-09 R5

## Review Configuration

- Project: Knudg repository root
- Tier: full loop, focused final confirmation
- Review targets: root README and normative docs under `docs/`, excluding `docs/plans/**` and `.codex/**`
- Execution: Codex subagents with fresh context; prior findings and diffs were not supplied to reviewers

## Result

PASS.

Final focused reviewer found no Tier 1 findings and scored:

| Axis | Score |
|---|---:|
| Correctness | 7 |
| Completeness | 6 |
| Implementability | 6 |
| Resilience | 7 |

## Main Fix Areas

- Split undoable discard and public-approval withdrawal into `discard_pending` and `publication_withdrawn`.
- Made RFC 0001 an accepted design with explicit M0 code-start blockers for DDL appendix and DEC-019 key custody.
- Added event-stream position bijection requirements and domain event types.
- Added active verification integrity, break-glass DDL contract, outbox/job uniqueness, and circuit-control DDL requirements.
- Added RFC 0003 for WEDGE-001 and clarified that M1 is blocked until it is accepted.
- Added consent/revocation UX recovery, explanation schema, pending-publication withdrawal, consent-record revocation choices, RB-008, and team-sharing consent mapping.

## Remaining Non-Blocking Tier 2

- M0 still needs the SQL DDL appendix before implementation can start.
- DEC-019 must select the M0 claim-signing key custody profile before M0 DDL migration.
- RFC 0003 must be accepted with measured/named gate values before M1 starts.

## Verification

- `git diff --check`: no whitespace errors; only existing CRLF normalization warnings.
