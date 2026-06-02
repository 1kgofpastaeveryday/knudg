# Experience Domains

Knudg can grow beyond technical worklogs, but it must not collapse into an
unbounded personal memory app. The product boundary is structured,
agent-readable experience: reusable observations, decisions, fit patterns,
failed paths, and public-safe aggregate signals that an agent can use as
candidate evidence.

This document defines the domain split for that broader direction. It is a
design contract, not an implementation approval. WEDGE-001 and the
closed-launch technical backend remain the active implementation priority.

## Domain Separation

Experience domains are retrieval, consent, redaction, and retention boundaries.
Cards from one domain must not be searched from another domain unless the
request context explicitly authorizes cross-domain retrieval.

Initial domains:

| Domain | Primary use | Default retrieval | Default visibility |
|---|---|---|---|
| `technical_work` | coding, debugging, deployment, CI, environment traps, architecture decisions | automatic for technical tasks | private or team; public only after product gates |
| `personal_reasoning` | private decision patterns, repeated preferences, "we discussed this before" wall-bouncing | contextual, not automatic during technical work | private only |
| `career_private` | job-search positioning, company fit, interview reflection, application strategy | explicit or strong career context | private only |
| `place_service_experience` | restaurants, stores, services, support experiences, product/service impressions | explicit or strong place/service context | private by default |
| `public_experience_candidate` | redacted, reviewed, non-identifying public signals derived from one or more private/public sources | never searched as public until published | candidate only |
| `public_aggregate_signal` | moderated, aggregated public-facing signal about a subject or pattern | public search after public gates | public |

The current technical card types remain valid inside `technical_work`:
`solved_path`, `failed_path`, `environment_trap`, `deprecated_approach`, and
`unknown`. Broader domains add different card intents but use the same
lifecycle, consent, redaction, revocation, and untrusted-evidence semantics.

## Broader Card Intents

Broader experience cards should be compact summaries, not raw diary entries or
chat logs.

Suggested intents:

- `decision_revisited`: a topic was considered before and had a conclusion,
  rationale, or unresolved boundary.
- `repeated_pattern`: a recurring preference, constraint, reaction, or
  evaluation heuristic.
- `personal_constraint`: a private constraint that affects future advice.
- `career_positioning`: resume, interview, or company-fit positioning that
  worked or failed.
- `company_experience`: a company-level observation, with public company name
  allowed but selection details redacted by default.
- `interview_experience`: private interview-process learning, never public by
  default.
- `place_experience`: store, restaurant, venue, or service observation.
- `service_quality_signal`: a subjective or factual service-quality note.
- `public_aggregate_signal`: a reviewed public synthesis that avoids
  singling-out individuals or exposing private selection/status details.

## Required Payload Facets

Every non-technical experience card should separate subject, claim, sensitivity,
and evidence strength so retrieval can stay useful without overstating truth.

Minimum logical facets:

```yaml
domain: career_private
intent: company_experience
subject:
  type: company
  public_name: Example Inc
  aliases: []
claim_type: subjective_impression
evidence_strength: single_observation
sensitivity: medium
retrieval_policy: explicit_or_contextual
visibility_target: private
human_summary:
  content: "Example Inc fit review emphasized evaluation clarity and assignment certainty."
  redaction_summary: "Removed selection status, people, dates, direct messages, offer details, and private circumstances."
source_policy:
  raw_source_retention: none
  publication_eligible: false
```

Allowed `claim_type` values:

- `factual_observation`: directly observed, low-interpretation fact.
- `subjective_impression`: a personal impression or preference.
- `inference`: a conclusion drawn from observations.
- `aggregate_summary`: synthesis across multiple eligible observations.
- `unverified_report`: third-party report that must not be treated as fact.

Allowed `evidence_strength` values:

- `single_observation`
- `repeated_personal_observation`
- `corroborated`
- `public_source_supported`
- `operator_judgment`

## Career Redaction Policy

Company names may remain plain when they are useful retrieval keys. The default
career policy is not to hide the company name; it is to hide the sensitive
selection context around it.

Plain by default:

- company name
- industry
- role family
- public job-posting attributes
- high-level fit criteria
- abstracted lessons for communication and positioning

Redacted by default:

- selection status
- recruiter, interviewer, employee, and referrer names
- emails, chat text, calendar details, interview dates, and message excerpts
- compensation numbers, offer terms, and negotiation details
- non-public interview content or company information
- raw comparison notes involving other companies
- private personal circumstances unless explicitly approved for private-only
  retention

`career_private` cards are not public publication candidates unless a new
redacted artifact is authored for that purpose and the exact-artifact approval
flow explicitly marks it as public-eligible.

## Place And Service Experience Policy

Place and service cards can preserve subject names such as a restaurant, store,
hotel, or product because subject names are essential retrieval keys. They must
separate fact from impression.

Plain by default:

- business or product name
- location at city/neighborhood granularity when useful
- visit or use context at coarse granularity
- factual observations such as wait time category, reservation friction, or
  menu/service availability
- subjective impression labeled as subjective

Redacted by default:

- employee names, physical descriptions, shift/time details that could identify
  staff, and direct quotes from staff
- receipt numbers, reservation identifiers, account IDs, contact details, and
  payment details
- exact timestamps unless needed privately and approved
- allegations of illegal conduct unless routed to a high-risk review lane
- single-observation insults or personal attacks

Negative public-facing signals must be transformed into non-identifying,
reviewed summaries. For example, "the staff member was awful" is not a public
card. A possible private card is "the visit left a negative service
impression"; a possible public aggregate signal is "some reports describe
unclear guidance during busy periods," only if aggregation and review gates
allow it.

## Public Candidate Gates

`public_experience_candidate` is a separate lane from private experience. A
private card never becomes public by changing visibility in place. Public
publication requires a new redacted artifact, exact-artifact approval, and
reviewer publish.

Public candidates must satisfy all of the following before indexing:

- no raw transcript, email, calendar, receipt, or message body
- no person-level target unless the subject is a public figure and a separate
  policy permits that use
- clear `claim_type`, with subjective impressions labeled as subjective
- company/place names allowed only when the card avoids exposing private
  selection status, staff identity, or non-public operational details
- high-risk claims routed to human review or withheld
- no synthetic or AI-generated fake review presented as human experience
- source provenance retained privately for audit and revocation, not exposed as
  raw public text
- takedown, correction, withdrawal, and revocation paths defined before public
  serving
- public display avoids implying that a single private observation is a
  representative fact

Public aggregate signals need stronger gates than private retrieval:

- minimum source count or reviewer-approved exception
- dedupe and manipulation checks
- abuse reporting and moderation queue
- abuse identity enforcement for repeated malicious submissions, ban evasion,
  fake experience claims, spam, brigading, and harassment, with identity
  signals kept out of public/B2B-facing surfaces
- freshness and stale-signal expiry
- jurisdiction-aware legal/privacy review for consumer reviews, job-search
  content, and platform moderation duties

Respondent and business inquiry products may receive only redacted case
summaries, aggregate signals, response workflows, correction/takedown outcomes,
or moderated follow-up channels. They must not receive raw source material,
submission identity, device/network signals, applicant/customer identity,
reviewer identity, or re-identification hints. Trust-and-safety may use
protected identity signals internally to investigate malicious submissions and
apply bans, but that lane is not a B2B data product.

Relevant external constraints include the FTC consumer review rule, EU Digital
Services Act platform accountability and content moderation expectations, and
Japanese personal-information guidance for pseudonymized/anonymized
information. These are reference constraints, not a complete legal analysis:

- <https://www.ftc.gov/business-guidance/resources/consumer-reviews-testimonials-rule-questions-answers>
- <https://digital-strategy.ec.europa.eu/en/policies/illegal-content-online-platforms>
- <https://www.ppc.go.jp/files/pdf/260401_guidelines04.pdf>

## Retrieval Policy

Retrieval should default to the narrowest relevant domain.

- Technical tasks search `technical_work` only.
- General "what do you think" wall-bouncing may search
  `personal_reasoning` after the user has opted into that domain.
- Job-search requests may search `career_private`.
- Place, restaurant, store, travel, product, or service requests may search
  `place_service_experience`.
- Public search never reads private domains directly. It reads only published
  public artifacts or public aggregate signals.

Cross-domain retrieval is allowed only when all domains are authorized and the
response labels the source domain. A career card must not silently influence a
technical implementation task; a technical card must not pollute a job-search
conversation unless the user asked about technical portfolio or tooling
positioning.

## Write Policy

All broader-domain writes remain approval-based.

The writer may propose a candidate when a conversation produces a reusable
lesson, but it must show the exact redacted card summary and redaction summary
before retention. It must never store raw conversation text as the primary
artifact.

Default write outcomes:

- `technical_work`: private candidate, team/public only after existing gates.
- `personal_reasoning`: private candidate, no public path by default.
- `career_private`: private candidate, public path disabled by default.
- `place_service_experience`: private candidate; public candidate requires a
  new artifact and stronger review.
- `public_aggregate_signal`: reviewer-created or reviewer-approved artifact
  only.

This keeps the long-term "experience database" direction compatible with the
current Knudg invariants: private by default, exact approval, retrieval
abstention, revocation, and cards as untrusted evidence rather than authority.
