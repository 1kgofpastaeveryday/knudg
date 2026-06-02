# Public Corpus Growth Roadmap

This roadmap makes public-source ingestion the primary growth path for the
Knudg public database. User private work remains a secondary contribution path:
it can create private cards and public candidates, but it must not be the main
source of public corpus growth because exact-artifact approval creates real
friction.

The initial public growth source is GitHub public issue, pull request, commit,
and release history for OSS projects where agents repeatedly encounter build,
test, dependency, framework, and tooling failures.

## Product Bet

Knudg should learn the shape of resolution, not just collect issue text:

```text
public issue opened
  -> reproduction details
  -> maintainer diagnosis
  -> attempted workarounds
  -> linked pull request or commit
  -> release note or fixed version
  -> later confirmations, regressions, or deprecations
  -> structured solved/failed/unknown/deprecated cards
```

The public corpus becomes valuable when it captures reusable resolution
timelines: what the symptom looked like, what did not work, which version or
change fixed it, what environment bounds mattered, and when the advice became
stale.

## Boundaries

- Use GitHub's official APIs and obey primary and secondary rate limits.
- Prefer GitHub App or fine-scoped token access with cache, ETag, and backoff.
- Do not scrape aggressively or bypass platform limits.
- Store structured summaries, fingerprints, source URLs, and provenance, not
  full mirrored issue/comment bodies.
- Preserve source attribution and source URLs on every generated card.
- Track source artifact IDs and update cursors so deletion, edits, locks, and
  stale or superseded resolutions can be reflected.
- Do not ingest private repositories, private logs, credentials, customer data,
  support incidents, or unpublished security issues.
- Do not treat public availability as proof that commercial derivatives,
  model-training exports, or curated packs are allowed; those surfaces need
  separate policy review.
- Do not let public-source cards bypass hostile-card, prompt-injection,
  privacy, quality, revocation, and abuse gates.

Reference constraints:

- GitHub REST API rate limits: <https://docs.github.com/en/rest/rate-limit>
- GitHub GraphQL API rate and node limits:
  <https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api>
- GitHub Terms of Service API terms:
  <https://docs.github.com/en/site-policy/github-terms/github-terms-of-service/>

## Seed Scope

Start with repos and ecosystems that match WEDGE-001:

- agent coding tools and SDKs
- package managers and build systems
- test runners and browser automation
- web frameworks
- Python API/runtime frameworks
- managed-cloud developer deployment surfaces
- mobile build and release tooling

Initial target selection should be allowlisted and small. Candidate repos are
chosen for high public issue quality, frequent agent-visible failures, clear
release practice, and permissive enough source-policy review for summary
indexing.

## Card Types

The ingestion pipeline should generate multiple card types from one resolution
timeline:

- `solved`: a confirmed fix, version, patch, configuration change, or
  workaround.
- `failed_only`: attempted fixes that maintainers or users showed were not
  sufficient.
- `unknown_clarified`: missing reproduction detail, unsupported environment,
  expected maintainer question, or boundary condition.
- `deprecated`: old fix path that is superseded by later releases, changed
  APIs, or security guidance.

Each card must include:

- normalized public package/tool coordinates
- normalized error or symptom fingerprint
- bounded environment tags
- source issue, PR, commit, and release URLs
- evidence strength
- freshness and version bounds
- source processor version
- source artifact IDs and update cursors

## Quality Signals

Rank and admit public-source cards using explicit signals:

- linked PR was merged
- release note or fixed version references the issue/PR
- maintainer confirmed diagnosis or fix
- multiple independent users confirmed the fix
- reproduction exists and is not customer/private data
- issue was closed as completed, not stale or invalid
- later issue references the same failure as regression or duplicate
- advice is version-bounded and not executable by default

Negative or caution signals:

- issue closed as stale, duplicate without target, invalid, or unanswered
- fix requires destructive commands, credential changes, billing changes, or
  security-sensitive operations
- discussion contains private-looking logs, tokens, hostnames, customer names,
  or personal data
- workaround is contradicted by later maintainer guidance
- source project license or policy review does not permit the intended use

## Phased Roadmap

### Phase 0: Source Policy And Allowlist

Status: proposed

- define source-policy review for GitHub public-source ingestion
- create a repo allowlist with owner/repo, ecosystem, license/policy notes,
  allowed source surfaces, and rate-limit budget
- define takedown, source deletion/edit reflection, and source attribution
  behavior
- define storage contract: summaries and provenance only, no full mirror

Exit:

- 5 to 10 allowed repos with documented source policy and rate budgets

### Phase 1: Collector Dry Run

Status: proposed

- implement a read-only collector that fetches closed issues and linked PR
  metadata through official APIs
- persist only a dry-run manifest first: source IDs, URLs, timestamps,
  labels, linked PR references, release references, and rate-limit evidence
- support ETag/cache and backoff
- do not create product cards yet

Exit:

- 100 candidate timelines discovered across the allowlist without storing full
  bodies or violating rate budgets

### Phase 2: Timeline Extraction

Status: proposed

- extract issue -> comment -> maintainer signal -> PR -> release timelines
- classify solved, failed-only, unknown-clarified, deprecated, duplicate, and
  stale outcomes
- record uncertainty when linked PR or release evidence is missing
- keep source snippets out of durable storage unless a source-policy review
  explicitly allows bounded excerpts

Exit:

- 50 timelines manually spot-checked against source URLs

### Phase 3: Card Synthesis

Status: proposed

- generate `card-payload-v1` summaries from public-source timelines
- include exact source provenance, source processor version, and evidence
  strength
- withhold executable steps by default for high-risk cards
- add deterministic scanners for secrets, personal data, private hostnames,
  credential-looking values, and customer/incident markers

Exit:

- 100 public-source seed cards in a non-serving review namespace

### Phase 4: Review, Dedup, And Deprecation

Status: proposed

- deduplicate duplicate issues and repeated stack signatures
- link supersession, contradiction, and deprecation edges
- apply reviewer QA sampling and malicious-card seeded tests
- mark cards `verified` only when reproduced or externally validated

Exit:

- approved seed set has measured useful-card yield, stale rate, rejection
  classes, and review minutes per card

### Phase 5: Retrieval Evaluation

Status: proposed

- evaluate public-source corpus against baseline web search, GitHub issue
  search, official docs, Stack Overflow or equivalent public Q&A, and local
  repo search
- measure exact-error recall, semantic recall, deprecation awareness,
  failed-path usefulness, harmful suggestion rate, and no-suggestion accuracy
- keep public serving closed until public-search privacy and abuse gates pass

Exit:

- WEDGE-001 evidence shows public-source cards improve replayed agent tasks

### Phase 6: Controlled Scale

Status: proposed

- expand allowlist by ecosystem based on measured yield
- add webhooks or scheduled incremental refresh for allowed repos
- maintain source tombstone/edit reflection and stale-card review queues
- expose public retrieval only after PR-BE public gates pass

Exit:

- corpus growth rate, cost per useful public card, stale-card cost, and abuse
  controls meet accepted launch thresholds

## Interaction With Private Work

Private user work is not the main public growth engine. It contributes by:

- creating private cards that improve the user's own retrieval
- creating generalized public candidates when the user explicitly approves the
  exact redacted artifact
- revealing high-value public-source ingestion targets, such as a repo, issue
  family, package, or error fingerprint worth crawling

No private card becomes public due to timeout, inactivity, or opt-out default.
Public-source ingestion is the scale path; explicit approval remains the path
for user-derived public publication.
