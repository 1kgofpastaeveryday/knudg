# Codex for OSS Readiness

This note keeps the Codex for Open Source application story truthful and
reviewable. It is not a claim of broad adoption or production readiness.

## Current Position

Knudg is an early-stage Apache-2.0 project for Codex-style agents to reuse
structured, redacted experience cards for solved paths, failed paths,
environment traps, deprecated approaches, and clarified unknowns.

The project is currently strongest as a Codex-adjacent OSS infrastructure
candidate, not as a broadly adopted maintainer-workload case. The public repo
has a self-hostable closed-launch private backend loop, schemas, CLI/API
commands, migrations, fixtures, tests, safety gates, and Codex plugin/skill
assets. It does not yet have broad external adoption, public publication, team
namespaces, protected hosted retrieval, or trusted hosted consent
completion.

## Evidence Available Today

- Public repository with Apache-2.0 license, governance, contributing,
  support, and security policy.
- Node 20 and Python 3.12+ based quickstart with npm commands as the supported
  cross-platform entry point.
- Postgres migrations for the data kernel.
- Closed API substrate for private card write, search, revoke, and purge flows.
- `knudgctl` workflow for server status, task-profile building, search, nudge,
  and write-candidate handoff.
- Synthetic fixtures, JSON Schemas, validators, and pytest coverage for card
  payloads, retrieval panels, domain policy, consent and revocation gates, and
  future surface gates.
- A synthetic Codex for OSS demo evidence snapshot at
  `fixtures/codex-oss-demo-wedge-evidence.sample.json`, validated with
  `npm run codex:oss-demo`.
- A documented rule that retrieved cards are untrusted evidence, not agent
  instructions.
- Tagged release `v0.1.0` with GitHub Release and dated CHANGELOG entry.
- Clean-machine quickstart transcript on Ubuntu 24.04 (Node 20.20.2,
  Python 3.12.3, PostgreSQL 16.14 with pgvector): 58 passed, 1 skipped,
  public release validation passed. See
  `docs/evidence/quickstart-transcript-v0.1.0.md`.

## Evidence Not Yet Available

- Meaningful usage, monthly downloads, stars, forks, downstream dependencies,
  or external maintainer adoption.
- Public/team search or publication readiness.
- Reviewer capacity measurements for public-card admission.
- A WEDGE-001 replay evaluation proving retrieval lift over current baselines.
- Public-source corpus ingestion with source-policy review and stale-card
  handling.

## Application Posture

Apply only as an early-stage project that may not neatly fit the criteria but
could become important to OSS agent maintenance workflows. Do not imply
production traffic, broad adoption, or public retrieval. The strongest claim is
that Knudg is building reusable, self-hostable infrastructure for a class of
problems that Codex maintainers repeatedly hit: package, CI, migration, build,
test, and release failures.

## Form Drafts

### Why This Repository Qualifies

Knudg is early-stage Apache-2.0 infrastructure for Codex-style agents to reuse
redacted experience cards for solved paths, failed paths, and environment
traps. It targets repeated OSS maintainer/debugging work: package, CI,
migration, build, test, and release failures. The repo has schemas, CLI/API,
tests, safety gates, and Codex plugin assets, but is pre-adoption and seeking
validation.

### How API Credits Will Be Used

Use credits to test agent-facing retrieval and safety flows: task-profile
generation, redaction checks, hostile-card filtering, retrieval-panel
summaries, and replay evaluations for developer tooling failure cases. Credits
would support measured private dogfood and OSS readiness work, not production
user traffic.

### Anything Else

Knudg intentionally keeps default visibility private. Public/team retrieval is
disabled until consent, revocation, reviewer-capacity, abuse, and safety gates
pass. Codex Security would be useful for reviewing the private-loop boundary,
redaction validators, hostile-card handling, and authorization assumptions.

## Work That Would Strengthen A Later Application

1. ~~Tag an initial release and publish release notes.~~ Done: v0.1.0.
2. ~~Capture a clean-machine quickstart transcript.~~ Done: see
   `docs/evidence/quickstart-transcript-v0.1.0.md`.
3. Expand the synthetic/public demo corpus beyond
   `fixtures/codex-oss-demo-wedge-evidence.sample.json` and add provenance for
   any public-source examples.
4. Record a Codex plugin walkthrough that shows one retrieval-panel suggestion
   improving a repeat developer-tooling task.
5. Complete a WEDGE-001 dry run with candidate yield, rejection classes, review
   minutes, and privacy-friction measurements.
6. Run a replay evaluation against fixed baselines: web search, official docs,
   package/framework issue trackers, Stack Overflow or equivalent public Q&A,
   repo-local search, and team-local history where available.
7. Add external evidence: issues, PRs, tester notes, design-partner summaries,
   or use by another OSS maintainer.

## Minimum Validation Snapshot

Before claiming stronger fit, collect a snapshot with:

- release tag
- quickstart command transcript
- test command and result
- number of synthetic/public demo cards
- number of replay tasks
- retrieval useful rate by evidence band
- median review minutes per accepted card
- redaction rejection rate
- harmful suggestion count
- external maintainer/tester count
