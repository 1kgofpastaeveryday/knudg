# Adjacent Work

Knudg shares a premise with other agent knowledge projects: agents should reuse
prior experience instead of starting from zero. Knudg deliberately occupies a
different layer than knowledge formats and curated workflow libraries.

## Knowledge Formats

Knowledge formats standardize how reusable knowledge is written. For example,
an open format may pair Markdown with structured metadata so knowledge can move
between tools.

That is a notation, not the whole system. Knudg can emit and ingest such
formats, but the format itself does not solve capture, the upload boundary,
redaction, revocation, retrieval, or trust. Those are system responsibilities.

## Curated Workflow Libraries

Curated workflow libraries distill reusable workflows from public official
sources and public user reports, then ship them as installable skills or
plugins. Their inputs are already public, and their artifacts are installed
ahead of time.

Because those inputs are public, they do not need a governed
private-to-shareable transformation. Knudg targets that transformation, and
retrieves candidate cards at task time rather than shipping a fixed bundle.

## Knudg's Layer

Knudg's chosen problem is the governed transformation and retrieval of private
and team experience, not the curation or distribution of public knowledge. That
boundary is enforced in schemas and serving rules, not only described in prose:

- **Synthetic-only portable payloads.** A card payload's
  `privacy.source_class` and `provenance.source_class` are fixed to
  `synthetic`. A payload carrying raw source data fails validation; redaction is
  a schema invariant, not a convention.
- **No identity or tenancy in portable payloads.** The card payload schema
  forbids `tenant_id`, `namespace_id`, `visibility`, `card_id`, timestamps, and
  similar fields, so a portable card cannot leak its origin or tenancy.
- **Safety quarantine is first-class.** Every card carries a `safety` block
  with `review_state` (`unreviewed`, `quarantined`, `cleared`, or `blocked`),
  explicit credential, billing, deletion, and network-call risk flags, and a
  `withheld_reason`, so retrieved evidence can be held back or blocked rather
  than blindly surfaced.

| Dimension | Knowledge format | Curated workflow library | Knudg |
| --- | --- | --- | --- |
| Input source | Author-supplied | Public sources only | Private and team experience |
| Unit of reuse | A document | A distilled skill or plugin | An evidence card |
| Governance | Out of scope | Not required for public input | Upload boundary, revocation, purge, redaction |
| Retrieval timing | Not applicable | Install-time bundle | Task-time retrieval by task profile |
| Safety model | Format-dependent | Lightweight | Schema-enforced quarantine and risk flags |

Retrieved cards remain untrusted evidence under all of the above.
