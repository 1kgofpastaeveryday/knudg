# WEDGE-001 Validation Workbook

Status: draft research workbook

This workbook is the operational companion to
`pre-m1-validation-protocol.md` and RFC 0003. It defines what to record before
RFC 0003 can move from `draft gate` to `accepted`. It must not contain real
prospect names, raw logs, repository URLs, credentials, customer incidents, or
private diagnostic artifacts.

The private evidence repository and private prospect registry hold source
artifacts. This repository may reference only opaque IDs, artifact digests,
source classes, consent states, owners, and evidence links.

## Workstreams

| Workstream | Owner | Evidence location | RFC 0003 output |
|---|---|---|---|
| Prospect registry | Knudg operator | private registry | opaque participant/team IDs, segment, consent state |
| Research protocol | Knudg operator | private research repository | accepted protocol link and decision memo |
| Seed dry run | Knudg operator | private research repository | 30-50 candidate dry-run summary |
| Seed corpus | Knudg operator | private research repository | 100 labeled candidate summary |
| Baseline replay | Knudg operator | private research repository | baseline systems and evaluation bands |
| Reviewer operations | reviewer-operations owner | private research repository | staffing, rubric, capacity, pause rule |
| Commercial validation | product owner | private research repository | buyer/user hypothesis and procurement blockers |

Owners may be renamed before acceptance, but RFC 0003 must not be accepted with
unnamed owners.

## Evidence Register

Each external artifact referenced by RFC 0003 uses this shape:

| Field | Requirement |
|---|---|
| `evidence_id` | opaque stable ID, no human names |
| `evidence_type` | `prospect`, `interview`, `seed_candidate`, `baseline_replay`, `review_calibration`, `decision_memo` |
| `storage_location` | private registry or private evidence repository link |
| `artifact_digest` | digest of the redacted or source artifact, as applicable |
| `source_class` | internal dogfood, design partner, public issue/build log, synthetic fixture |
| `consent_state` | not_required_for_synthetic, requested, granted, denied, withdrawn, expired |
| `retention_deadline` | date or policy reference |
| `owner` | accountable role |
| `allowed_repo_reference` | opaque ID, digest, and status only |

## Participant Registry Minimum

The private registry must record:

- opaque participant or team ID
- segment and ICP fit
- buyer/user role split
- recruiting source
- allowed research activities
- consent or authorization state
- compensation or explicit no-compensation acceptance
- evidence links
- retention and deletion date
- opt-out or deletion request path

RFC 0003 may summarize counts by segment and consent state. It must not include
real names, company names, email addresses, repository URLs, or raw artifacts.

## Seed Candidate Record

Each seed candidate must be labeled before it can count toward the dry run or
the 100-candidate seed corpus:

| Field | Requirement |
|---|---|
| `candidate_id` | opaque ID |
| `source_class` | internal dogfood, design partner, public issue/build log, synthetic fixture |
| `source_rights_state` | clear, unclear_private_only, rejected |
| `consent_artifact_id` | opaque ID or not_required_for_synthetic |
| `source_digest` | digest only |
| `redacted_artifact_digest` | digest of exact redacted candidate |
| `fallback_visibility` | synthetic, single_workspace_private, team_only, public_candidate |
| `outcome_type` | solved, failed_only, inconclusive, unknown_clarified |
| `exact_error_signature` | normalized public-safe signature or withheld |
| `tool_coordinates` | public package/tool/framework coordinates or withheld |
| `environment_bounds` | public-safe bounds or withheld |
| `risk_band` | low, medium, high |
| `high_risk_flags` | executable, dependency_change, credential, deletion, network, repo_migration, ci_cd, billing, security_posture |
| `redaction_minutes` | measured minutes |
| `review_minutes` | measured minutes |
| `reproduction_required` | yes/no |
| `reproduction_minutes` | measured minutes or not_applicable |
| `reviewer_confidence` | low, medium, high |
| `useful_summary_eligible` | yes/no |
| `decision` | accepted_private, accepted_team, accepted_public_candidate, rejected, abandoned |
| `rejection_reason` | required when rejected or abandoned |

Any candidate with unclear source rights, unclear submitter authority, or
unresolved third-party contribution rights cannot count as a public candidate.

## Dry Run Summary

The 30-50 candidate dry run validates the protocol, not product value. The
decision memo must report:

- candidate count by source class
- candidate count by decision
- abandonment count and primary reasons
- useful-summary eligibility rate after safety withholding
- high-risk fraction
- median and p90 redaction minutes
- median and p90 review minutes
- median and p90 reproduction minutes where reproduction was required
- reviewer disagreement count
- source-rights rejection count
- consent denial, withdrawal, expiry, and abandonment counts
- changes required before the 100-candidate seed corpus

## Seed Corpus Summary

The 100-candidate seed corpus cannot begin until the dry-run protocol and
consent artifact are accepted. The summary must report the same fields as the
dry run plus:

- useful-card yield by evaluation band
- exact-error, semantic-only, failed-only, unknown-clarified, deprecated, and
  disputed candidate counts
- public, team-only, single-workspace private, and synthetic split
- expected candidate arrival rate for the first private dogfood slice
- estimated reviewer weekly capacity using measured review and reproduction
  minutes
- public-vs-private pivot recommendation

## Baseline Replay Register

Each replay task must freeze its baseline set before evaluation:

- current agent web search
- official docs
- package or framework issue trackers
- Stack Overflow or equivalent public Q&A
- repo-local search
- team-local history search when available

For each replay task, record opaque task ID, evaluation band, source candidate
IDs, baseline result, Knudg candidate result, time-to-useful-path, harmful or
stale suggestion flag, and evaluator notes. Do not store raw private work in
this repository.

## Reviewer Calibration

Before RFC 0003 acceptance, record:

- reviewer qualification rubric
- calibration fixture IDs
- dual-review sampling policy
- disagreement escalation path
- false-approval pause rule
- malicious-card seeded test result summary
- p90 and p95 review-time budgets by risk band
- high-risk reproduction lab profile
- reviewer capacity model and admission pause rule

Reviewer reputation may route work later, but it cannot bypass dual-review
sampling or high-risk verification.

## RFC 0003 Acceptance Memo

RFC 0003 can move to `accepted` only after a decision memo names:

- accepted wedge scope
- accepted protocol version
- evidence register snapshot ID
- prospect registry snapshot ID
- seed dry-run summary ID
- seed corpus summary ID
- baseline replay definition ID
- reviewer-operations summary ID
- commercial validation summary ID
- public-vs-private pivot recommendation
- remaining decisions that block M1, M2, or public pilot

The memo may contain estimates where RFC 0003 allows estimates, but every
estimate must name its source and uncertainty range. Unknown values remain
blockers, not defaults.
