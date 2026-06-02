# Landing Page Design

Status: Implemented static prototype, synchronized May 12, 2026

This document defines the public English landing page implemented in
`site/index.html` with shared styling in `site/styles.css`.

Document authority:

- classification: internal project design, not public landing-page copy
- owns: public message boundary, reading order, visible content intent, and
  localization parity with the Japanese page
- does not own: deployment steps, rollback procedure, mechanical release checks,
  or production incident handling

## Public Disclosure Boundary

The landing page is a public-facing preview. It must explain the effect of
Knudg and the safety posture without exposing the product mechanics in enough
detail to copy the product.

The page may communicate:

- what problem Knudg targets
- what changes for teams using coding agents
- why remembered experience must be treated as a clue, not an instruction
- why the current page is information-only
- what proof is needed before public access opens

The page must not communicate:

- internal retrieval mechanics, schemas, state names, or field names
- implementation channel details
- approval queue internals, identifiers, data handling mechanics, or policy tables
- public corpus design, ranking, indexing, or storage strategy
- any route, form, command, or product action that looks usable today
- exact process detail that would let a reader reconstruct the product system

If a detail helps builders reproduce Knudg more than it helps a buyer trust
Knudg, it does not belong on the landing page.

## Product Frame

Knudg is agent experience infrastructure.

The public page must not position Knudg as personal memory, a generic notes
tool, or a single plugin. The simple first-viewport idea is:

```text
Agents should not start from zero.
```

The plain-language bridge is:

```text
Knudg is designed to turn hard-won agent troubleshooting into reusable paths,
starting with repeated developer-tooling failures.
```

Audience bridge:

```text
For engineering teams using coding agents across repeated build, CI, migration,
and developer-tooling failures.
```

Developer-tooling failures are the first wedge because they repeat often.
Knudg remains shared agent experience infrastructure for solved paths, failed
paths, unknowns, deprecations, and environment traps.

## Current Public State

The current implementation is an information preview:

- information only
- no public product web app, MCP, CLI, hook, search, or product access from the
  preview
- no public search results
- no active intake, account creation, download, command, or access route
- no live product data in the mock surface

The no-access state is shown through plain status chips and short copy, not
through disabled product-action controls.

The page intentionally avoids funnel language. It must not invite self-serve
account creation, setup, contact, trial, application, list-join, or product
access.

## Audience

Primary readers:

- engineering managers, tech leads, and senior engineers using coding agents on
  repeated build, release, migration, or tooling failures

Secondary readers:

- agent platform builders
- developer tooling teams
- technical founders
- privacy and security reviewers

Primary readers should understand the effect before they encounter any product
terminology.

The first viewport should name the audience in one sentence so readers know
whether the page is for an individual developer, an agent runtime builder, or a
team operating coding agents.

## Localization Parity

English, Japanese, and Simplified Chinese pages must carry the same product
commitments:

| Commitment | English page | Japanese page |
| --- | --- | --- |
| Audience | teams operating coding agents | teams operating coding agents |
| Product frame | shared agent experience infrastructure | shared agent experience infrastructure |
| First wedge | repeated developer-tooling failures | repeated developer-tooling failures |
| Safety | clue to verify, not instruction | clue to verify, not instruction |
| Access state | no public product web app, MCP, CLI, hook, search, or product access | no public product web app, MCP, CLI, hook, search, or product access |
| Publication | human-reviewed and scoped before sharing | human-reviewed and scoped before sharing |

The Japanese page can change cadence, line length, and label density, but not
these commitments. The Simplified Chinese page can change terminology and
sentence rhythm for Chinese developer readers, but not these commitments.

## Reading Rhythm

The implemented page follows a scan-first hierarchy:

1. hook headline
2. one short supporting paragraph
3. status strip
4. illustrative Knudg action mock
5. problem cards
6. outcome cards
7. public-safe private validation replay
8. example cards
9. in-practice list
10. safety basis
11. access-state and proof sections

Reference findings used for the page:

- Nielsen Norman Group's F-pattern guidance: important points need strong
  headings, meaningful groupings, and short body copy.
  <https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/>
- Nielsen Norman Group's Layer-Cake pattern: descriptive headings and
  subheadings let readers scan before reading detail.
  <https://www.nngroup.com/articles/layer-cake-pattern-scanning/>
- NN/g's reading-volume research: visitors often read only a small share of
  page text, so key claims must appear in headings and summaries.
  <https://www.nngroup.com/articles/how-little-do-users-read/>
- U.S. and U.K. public content guidance: use short headings, short sentences,
  plain language, and content chunking.
  <https://www.gsa.gov/reference/gsa-web-style-guide/content-standards>
  <https://www.gov.uk/guidance/content-design/content-types/>
- Material Design writing guidance: UI copy should be clear, accurate, and
  concise.
  <https://m1.material.io/style/writing.html>

## Implemented Page Outline

### Header

Navigation:

- Problem
- Outcomes
- Examples
- Safety
- Status
- Proof

Status labels:

- `Information preview`
- `Information only`

Mobile behavior:

- at `767px` CSS width and below, hide header navigation and status labels and
  keep only brand plus language switch in the sticky header
- at `768px` CSS width and above, show navigation and status labels
- do not add a hamburger, disclosure button, or scripted menu
- the same closed-access state remains visible in the hero status strip

### Hero

Headline:

```text
Agents should not start from zero.
```

Supporting copy:

```text
Knudg is designed to turn hard-won agent troubleshooting into reusable paths,
starting with repeated developer-tooling failures.
```

Audience copy:

```text
For engineering teams using coding agents across repeated build, CI, migration,
and developer-tooling failures.
```

Wedge copy:

```text
Developer-tooling failures are the first wedge because they repeat often.
Knudg is broader shared experience infrastructure, not a CI knowledge base.
```

State strip:

```text
Information preview. Product access is not open.
```

Action status:

```text
Product access closed
```

Hero mock:

- use a console-style log block
- show that similar prior work was found
- show that repeated trial and error was skipped
- show cumulative saved time, token count, and estimated token cost
- avoid extra explanatory panels that weaken the cost-reduction image

### Problem

Purpose: show the repeated-work cost.

Cards:

- Docs get reread
- Failed fixes repeat
- Environment traps stay local

### Outcomes

Purpose: make outcomes feel like Knudg product behavior, not abstract
mechanics.

Each card should include a short console-style log that sounds like an agent
starting work with a reusable clue. Use concrete but public-safe examples such
as Windows PowerShell local validation failures, failed dependency reinstall
attempts, deploy version checks, or a reminder to verify before use.

Layout: stack the outcome log blocks vertically. Do not force these examples
into the generic card grid; they should read top-to-bottom like a sequence of
Knudg nudges.

Cards:

- Find similar work
- Avoid dead ends
- Carry it forward
- Do not turn it into an order

### Private Validation Replay

Purpose: show that Knudg starts a task by suggesting what to suspect first.

The replay should read like a public-safe task log, not a terminal transcript
or internal system trace. Use direct examples such as Playwright blank
screenshots, Windows sandbox command failures, OS update environment drift, and
deploy smoke/version checks.

The replay must not include:

- commands
- routes
- identifiers
- schema or state names
- exact card contents
- private paths
- raw prompt text or transcripts

### Examples

Purpose: show the kind of reusable lesson Knudg preserves without exposing
underlying system design.

The first example should feel closer to something an agent would actually read,
while remaining public-safe. It may use familiar developer-tooling terms, but
must not expose internal schema names, retrieval fields, product APIs,
workspace identifiers, exact stack/runtime versions, named remediation
commands, or step-by-step proprietary process detail.

Featured example:

- public label: CI environment clue
- title: Package build passes locally but fails in hosted CI
- agent-facing sample: A hosted CI environment may resolve tooling differently
  from the local run. Compare the resolved toolchain or environment before
  retrying known fixes. If the context does not match, abstain from using this
  clue.
- safety note: Candidate evidence only; verify in the current workspace.

The visible layout should read as a single public example card, not as a full
internal data model. Labels are presentation aids, not product fields. Use at
most three visible public-safe labels in the card, and on mobile keep the title
outside the row budget. If the list starts to look like a schema, merge rows
into plain-language sentences.

Cards:

- CI environment clue
- Worked before
- Tried already
- Still unclear
- Known limit
- Needs recheck

Each card has:

- label
- title
- one-sentence summary
- one plain-language value sentence

Cards must not include internal fields, identifiers, state machines, or
reproducible mechanics.

### In Practice

Purpose: explain the practical value of remembering lessons without exposing
private work.

List:

- Remember the failure class
- Share the lesson without exposing the source material
- Mark clues as requiring validation
- Let people approve what can be shared

### Safety

Purpose: provide confidence without implementation disclosure.

Cards:

- Private posture
- Approval requirement

Allowed claims:

- no raw transcripts on the landing page
- no automatic public publishing
- no public search results from this page
- shared experience is not automatic; human review and scoped sharing are
  launch requirements
- retrieved experience is untrusted candidate evidence
- retrieved experience cannot authorize tool use, bypass local checks, or
  replace current workspace verification
- scope and withdrawal controls are launch requirements
- stale or unsafe clues are reasons to stop reuse

### Status

Purpose: state that the page is not a product gate.

Cards:

- Information preview
- Private validation
- Agent access
- Public details

### Proof

Purpose: define the evaluation frame before public opening.

Proof questions:

- Does it reduce repeated investigation?
- Do agents treat remembered work as a clue to verify?
- Can useful lessons be shared without exposing raw work?
- Can people understand and control what becomes shared?

Private validation criteria:

- repeated investigation is measured against comparable baseline tasks
- reused suggestions are presented as evidence to verify, never as commands
- reviewed public artifacts contain no raw transcripts, private logs, or
  implementation internals
- approval, scope limitation, withdrawal, and deprecation behavior are
  demonstrated before any public or team publication flow opens

## Visual System

Direction: infrastructure-grade Neo Brutalism.

Use:

- hard black borders
- small radii
- offset shadows
- dense but readable information blocks
- strong contrast
- product-like preview surfaces instead of abstract decoration

Avoid:

- playful poster brutalism
- marketing hero decoration
- nested cards inside cards
- one-hue palettes
- CTA-colored closed-state controls

Core palette remains:

| Token | Value | Usage |
| --- | --- | --- |
| `--ink` | `#101010` | Text, borders, shadows |
| `--paper` | `#fffdf5` | Main page background |
| `--panel` | `#ffffff` | Primary surfaces |
| `--yellow` | `#f7d84a` | Warning and attention |
| `--cyan` | `#4dd6ff` | Technical effect accents |
| `--red` | `#ff5a4f` | Failed paths and warnings |
| `--green` | `#62d26f` | Solved/control accents |
| `--muted` | `#ece7d8` | Secondary bands |

No remote fonts are used in the static prototype.

## Message Acceptance

The visible landing page should satisfy these message and disclosure checks:

- it identifies engineering teams operating coding agents as the primary reader
- it frames developer-tooling failures as the first wedge, not the whole product
- it does not position Knudg as personal memory, a generic notes tool, or a
  single plugin
- it makes the current no-access state clear without inviting self-serve
  account creation, setup, contact, trial, application, list-join, or product
  access
- it contains no visible product-action controls
- no internal state names or schema fields
- no public technical route to deeper implementation detail
- hero is understandable without reading any card metadata
- safety claims are specific enough to create confidence, but not system
  replication instructions
- featured example is no more than three visible labeled rows on mobile

Mechanical release validation, local target enumeration, headers, deployment,
and rollback are owned by the internal operator runbook.
