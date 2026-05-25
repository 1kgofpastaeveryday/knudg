# Product Strategy

Knudg should not begin as a broad public memory network. WEDGE-001 is the
provisional initial wedge: developer tooling failures for agentic coding
environments. M1 remains blocked until RFC 0003 is accepted with the named and
measured gate values. The wedge is limited to single-workspace private dogfood
until the accepted wedge RFC and milestone gates allow broader scopes. Before M2, this
means single-workspace private dogfood only; team namespace alpha waits for
private-retention consent and namespace grants, and public search/publication
waits for the public gates.
The wedge RFC must prove repeatability, acceptable privacy friction, measurable
reuse, and reviewer capacity for this domain before generalized ingestion
begins.

WEDGE-001 scope:

- package manager, framework, CI/test/build, and mobile build pipeline failures
  encountered by coding agents
- public dependencies and public toolchains first; private repository,
  customer, incident, credential, billing, and destructive-migration cases stay
  private/team-only unless a later RFC accepts their public profile
- retrieval-panel summaries only; inline hints stay disabled until hostile-card
  and harmful-suggestion gates pass
- first ICP: small teams already running coding agents on repeated build,
  migration, and release tasks
- first target users or teams must be recorded in a private prospect registry
  before non-synthetic M1 ingestion or protected submit code starts. Local
  synthetic and model-only helpers are exempt from this gate. The wedge RFC may
  reference opaque participant IDs,
  segment, consent status, owner, and evidence links, but must not store real
  prospect names unless the repository is approved for that data class.
  The registry is a controlled external artifact owned by product/security,
  with minimum fields for opaque participant ID, segment, consent status, data
  class, retention date, evidence link, and approval owner. Repo docs may
  reference only opaque IDs and aggregate segment counts.

Public corpus growth should not depend primarily on user private work. The
main public growth engine is public-source resolution history: OSS issues,
pull requests, commits, release notes, and public build logs that can be
processed under source-policy review, API rate limits, attribution, and
takedown/update behavior. The detailed roadmap lives in
[`public-corpus-roadmap.md`](public-corpus-roadmap.md). User-derived private
cards can still become public candidates, but only through exact-artifact
approval; inactivity or opt-out defaults must not publish them.

Before M1 planning completes, the wedge RFC may include a viability estimate: expected
candidate arrival rate, approval rate, high-risk fraction, median review and
reproduction cost, useful-card yield, and the minimum corpus size needed to
detect the target retrieval lift. It must name the initial ICP, reference the
private prospect registry, buyer/user split, current alternative workflow,
expected weekly usage frequency, pricing hypothesis, and a manual concierge
launch path. It
must also set measured pass/fail thresholds before M1 product ingestion can
open: maximum cost per useful approved card, maximum review minutes per
accepted card by risk band, and the minimum useful-card yield needed to keep
building the public corpus. If
public-only yield is too low or high-risk verification dominates reviewer
capacity, the product must redirect to private/team retrieval before building
public publication machinery. Team-shared private corpora are a first-class
enterprise path: a company can share solved paths inside its tenant without
publishing them to the public corpus.

The same RFC must include a pre-M1 validation protocol separate from the public
landing page: owner, research questions, participant criteria, recruiting
source, consent script, interview or usability artifacts, evidence repository,
decision thresholds, and the exact process for updating WEDGE-001 from the
results. The protocol contract lives in
[`pre-m1-validation-protocol.md`](pre-m1-validation-protocol.md). The
information-only LP cannot be the evidence capture path.

The wedge RFC must include a manual seed-corpus acquisition protocol before M1
code starts:

- source channels: internal dogfood sessions, consenting design partners,
  public issue/build logs that can be linked to a consenting submitter,
  source-policy-reviewed OSS issue/PR/release timelines from allowed public
  repositories, and synthetic fixtures derived from public documentation
- source-rights check: submitter authority over the artifact, project/license
  terms, platform API terms and rate limits, third-party comments, maintainer
  or organization approval when needed, customer/incident data screening,
  source deletion/edit reflection, and downgrade to private/team-only or
  synthetic fixture when authority is unclear
- consent artifact: exact redacted candidate digest, source category,
  visibility target, raw/source retention choice, derived-use policy, expiry,
  and withdrawal path
- labeling rubric: outcome type, exact error signature, tool/framework/package
  coordinates, environment bounds, high-risk flags, reproducibility evidence,
  reviewer confidence, rejection reason, and useful-summary eligibility
- workflow: two reviewers label the first calibration set, disagreements create
  an escalation item, and high-risk candidates require reproduction or remain
  private/team-only
- compensation: design-partner credit or written no-compensation acceptance must
  be recorded before collection
- minimum gate: at least 100 labeled seed candidates, with useful-card yield,
  approval/rejection rates, high-risk fraction, median review minutes, median
  reproduction minutes, and redaction abandonment measured before M1 ingestion

The wedge is a measurement strategy, not the global product ontology. Shared schema, consent, retrieval safety, outcome types, and agent access contracts must remain domain-general so Knudg does not collapse into a developer-worklog database.

Candidate follow-on wedges:

- package manager and framework migration errors outside coding-agent sessions
- CI/test/build failures with public dependencies at broader scale
- iOS/TestFlight and mobile build pipeline issues

MVP success requires evidence that retrieval improves outcomes in that wedge.

## MVP Gates

- at least 100 labeled seed cards in one wedge as bootstrap inventory, followed by a preregistered stratified holdout evaluation before public expansion; the 100-card floor is not statistical proof by itself
- exact-error recall@3 above the baseline search approach
- separate evaluation bands for exact-error, semantic-only, failed-only, unknown-clarified, deprecated, and disputed cards
- useful retrieval for failed-only and unknown-clarified cards
- measurable time-to-fix improvement in replayed tasks
- measurable improvement from remote shared corpus excluding same-session local cache
- harmful suggestion rate below a defined threshold
- no-suggestion rate, first-session useful suggestion rate, retrieval-panel open/read rate, and disable-after-no-suggestion rate measured by wedge
- public search abuse budgets defined and measured for rare-fingerprint probes, repeated abstentions, high-cardinality error probes, and wedge enumeration attempts
- high-risk card verification passing before summaries, retrieval-panel cards, inline hints, or ranking boosts expose executable, package, repository, migration, credential, billing, or security-sensitive guidance
- reviewer QA passing for the wedge, including dual-review sampling, calibration sets, malicious-card seeded tests, reviewer reputation limits, and a false-approval pause rule
- public-card approval and revocation flow tested end to end
- wedge privacy friction measured: public approval rate, redaction minutes per card, rare identifier rate, duplicate error rate, and useful retrieval rate
- tenant isolation tests passing for private and later team namespace paths
- gross-margin guardrail for free and paid query paths
- production cost metering enabled before billing, budget circuits, paid limits, or usage-based throttles can affect users
- review capacity and stale-card removal gates passing for the wedge
- public corpus, single-workspace private corpus, later team corpus, and same-session local cache evaluated separately
- public-only retrieval is not required to win before single-workspace private dogfood proceeds; public expansion is paused if private/team retrieval wins while public retrieval does not
- useful visible summary rate after safety withholding, measured as the share of
  retrieved useful WEDGE-001 cards that can show a non-executable public summary
  without exposing commands, package install lines, repository URLs, credentials,
  private paths, hostnames, or environment-specific identifiers

Reviewer capacity is a numeric launch gate. For the first public wedge:

- weekly capacity = active reviewer hours * 60 / measured median review minutes per public card, adjusted by dual-review rate, audit sampling, conflict escalation, and high-risk reproduction time
- p90 and p95 review-time budgets must pass by risk band; high-risk reproduction, malicious-card audits, conflicts, and emergency revocations are measured separately from median review time
- reviewer staffing, reviewer qualification, escalation-pool coverage, calibration cadence, and reviewer-session hardening are documented before public publication starts
- required weekly capacity must be at least 1.5x the trailing 7-day public candidate arrival rate
- oldest unreviewed public candidate must stay under 3 business days
- oldest unreviewed high-risk candidate must stay under the wedge-specific high-risk SLO
- emergency revocation and stale-card review reserve must keep 20 percent of reviewer capacity unallocated
- public candidate admission pauses automatically when backlog exceeds capacity for 2 consecutive business days

The wedge evaluation RFC must define baseline systems, per-band sample sizes, minimum detectable effect, confidence interval policy, labeling rubric, evaluator independence, harmful-suggestion threshold, privacy-friction threshold, and preregistered stop/pass conditions.
It must also define risk bands for the chosen wedge: cards safe to show as summaries, cards requiring verified full-card expansion, and cards withheld until high-risk verification capacity is proven.
No retrieval beyond synthetic fixtures or single-workspace private dogfood can
launch until the wedge evaluation RFC pins numeric thresholds and sample sizes
for the selected wedge. Team namespace retrieval additionally requires the M2
consent/grant gates.
Numeric privacy thresholds, `k` values, cohort floors, abuse budgets, rate-limit
budgets, and accepted stop/pass thresholds are private launch-control material
unless a later security/privacy review explicitly marks a redacted value
public-safe. Public-facing material may describe the existence of gates and
stop-condition categories, not the exact numbers attackers can tune against.
Baseline systems for WEDGE-001 must include, at minimum, current agent web
search, official docs, package/framework issue trackers, Stack Overflow or
equivalent public Q&A, repo-local search, and team-local history search where
available. The baseline definition must be fixed before evaluation tasks are
run.

The public-search privacy attack model is part of the wedge RFC. It must define adversary capabilities, auxiliary-information and linkage probes, singling-out tests, timing-envelope tests, distributed-abuse controls, and stop conditions. `k`-tenant thresholds are not sufficient by themselves.

MVP also needs stop conditions:

- pause public search for a wedge if timing, abstention, rate-limit, or result-shape behavior lets testers distinguish rare private fingerprints from generic misses
- pause public search for a fingerprint family if linkage probes, auxiliary-information probes, or cohort-differencing tests can single out a tenant, user, repo, host, customer, or incident even when `k` thresholds pass
- pause public corpus expansion if public-only retrieval does not beat baseline on replayed tasks
- pause public corpus expansion if useful cards in the selected wedge are mostly high-risk and reviewer capacity cannot verify them fast enough to make retrieval-panel summaries useful
- pause public corpus expansion if privacy friction exceeds the wedge threshold or public-only retrieval underperforms private/team/local baselines
- pause public candidate admission if review backlog exceeds the configured capacity
- pause public publication if malicious-card seeded tests or calibration reviews show false approvals above threshold
- pause reviewer self-serve privileges if reputation or throughput limits are exceeded; reputation can route work, but cannot bypass dual-review sampling or high-risk verification
- keep billing disabled if query gross margin, approved-card cost, metering correctness, and budget-circuit behavior are not measured
- keep inline hints disabled if harmful suggestion or dismissal rate exceeds the wedge threshold

Deferred until after these gates:

- broad public contributor incentives
- paid reranking tiers
- enterprise SSO/RBAC beyond the minimal tenant model
- large-scale data lake compaction
- curated packs
- multi-backend search abstraction

## Monetization

The product should not charge primarily for local memory.

Primary MVP revenue hypothesis:

- paid team private namespace for agentic coding teams that repeatedly hit
  build, migration, release, and CI failures across agents
- paid unit: seats plus indexed private experience volume
- free limit: local/synthetic fixtures and low-volume public search after M6
- buyer: engineering lead or platform/tooling owner; user: agent operator and
  developer reviewing retrieval-panel suggestions
- value claim: reduce repeated investigation time and preserve solved paths
  across agents without publishing private work
- backup hypothesis: paid high-rate API/MCP access over already-public cards
  after public-search privacy gates pass

Likely later monetization paths:

### Public Retrieval API

Free low-rate public search, paid high-rate API/MCP usage. Public search is a non-operational product contract until M6/DEC-013 accepts the first public-search privacy profile and wedge gates pass; no public endpoint serves results before that gate.

Paid retrieval over the already-public corpus is allowed only as an access, quota, latency, or reranking product. Public-card publication consent does not grant consent to sell a separate commercial artifact that rewrites, curates, packages, sponsors, trains on, or materially recontextualizes the card. Commercial or curated derivatives require a separate consent surface and revocation behavior.

Charge for:

- higher query limits
- lower latency
- better reranking
- more context-aware results
- usage-based retrieval volume

### Team Private Namespace

Teams pay for private experience indexes:

- internal repo work history
- CI failure resolution
- PR/review patterns
- migration notes
- incident workarounds
- private agent experience

### Enterprise Governance

Enterprise features:

- SSO
- RBAC
- audit logs
- managed directives, routing guidance, preferences, and guardrails for scoped
  agent work
- database-side intake safety gate with deterministic scanners plus a no-tool
  LLM classifier before accepting non-synthetic candidate content
- policy-based redaction
- private deployment/VPC/on-prem

Enterprise packaging must distinguish enforced governance from advisory
guidance. Knudg may claim governance enforcement only for Knudg-controlled
endpoints or integrations that pass host-enforcement conformance. Older,
unattested, or incompatible clients receive `advisory_only` guidance with no
destination/action-bearing details that would imply enforcement.
- retention controls
- compliance controls

### Paid Retrieval Quality Controls

Public DB can be free, while retrieval quality controls are paid access, quota,
latency, or ranking/filtering features over already-approved public cards or
policy-allowed deterministic projections:

- verified cards
- solved_many ranking
- deprecated detection
- disputed answer warnings
- high-confidence-only mode

### Commercial Derivative Products

Commercial derivative products require separate explicit consent and revocation
behavior before launch:

- curated packs

For MVP, `quality_state` values are operator-assigned only:

- `unreviewed`: generated but not reviewed
- `solved_once`: one approved source session
- `solved_many`: multiple independent approved source sessions
- `verified`: reviewer-approved with reproduced or externally validated evidence
- `disputed`: credible conflicting evidence exists

Deprecation is represented by lifecycle `status = deprecated`, not by `quality_state`.

Automated promotion based on contributor reputation, ranking outcomes, or monetized quality tiers is deferred to a separate ranking and governance spec.

Derived artifacts such as canonical trails and curated packs are product surfaces, not just storage optimizations. They need their own provenance, version, consent inheritance policy, and revocation behavior before launch.

### Curated Packs

Sell or sponsor packs:

- Next.js migration trails
- Python packaging trails
- iOS/TestFlight failure trails
- Kubernetes incident trails
- CUDA/PyTorch setup trails
- Codex/Claude Code/Cursor workflow trails

### Contributor Incentives

DB growth should not rely only on company-funded ingestion.

Possible incentives:

- credits for useful public cards
- bounty requests for missing trails
- verified contributor program
- revenue share for curated packs
- reputation/attribution for maintainers

## Unit Economics

The business should not assume that a shared corpus becomes cheaper just because the corpus is reusable. The first wedge implementation RFC must estimate and then measure:

- meter integrity for query count, rerank count, index writes, embedding runs, review time, revocation work, and abuse-control work
- cost per submitted candidate
- cost per approved public card
- cost per rejected candidate
- review minutes per public card
- embedding and re-embedding cost per card version
- hot-index and main-index storage cost
- cost per query with and without reranking
- cost per revocation propagation
- cost of free-tier abuse and rate-limit enforcement
- budget-circuit behavior before enforcement: dry-run alerts, tenant spend caps, degraded-mode policy, overage prevention, and auditability

Billing, paid quota enforcement, and automatic budget circuits should not launch until these costs are measured against retrieval value and the meters reconcile against audit events. The core monetization thesis is shared retrieval infrastructure, not paid local memory.

## Key Risks

- privacy leaks
- noisy or low-quality cards
- prompt injection through public cards
- stale/deprecated solutions
- duplicated cards
- over-trusting a single solved example
- high retrieval cost from free users
- poor ranking causing distraction instead of acceleration

Mitigations:

- explicit user consent before publish
- redact before approval
- approval bound to exact redacted artifact digest
- raw logs not published
- card-level provenance
- quality states: unreviewed, solved_once, solved_many, verified, disputed
- lifecycle states for superseded, deprecated, and revoked cards
- domain/environment filters
- public/private split
- object-level authorization before retrieval and ranking
- tenant keys in database, cache, object, and index layers
- rate limits, spend caps, and abuse throttles
- hostile-card and prompt-injection tests
- non-executable card rendering
- no-result abstention when confidence is low
- revocation/tombstone propagation across indexes and caches
