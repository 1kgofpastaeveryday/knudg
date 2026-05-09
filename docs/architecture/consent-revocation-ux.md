# Consent and Revocation UX

Knudg can postpone a polished knowledge-base UI, but it cannot postpone consent and revocation UX. Publication is a human decision surface.

## Consent Surface Matrix

| Surface | Default | User-visible artifact | Inherits public-card consent | Separate consent required | Revocation effect | Monetization allowed |
|---|---|---|---|---|---|---|
| Redacted public card | off | exact redacted card version | no | yes | block retrieval immediately, purge projections | no direct sale by default |
| Canonical trail | off | deterministic cluster summary and source list | yes, only for deterministic aggregation of already-public cards | yes if edited or meaning changes | remove source, recompute or unpublish if invalid | no by default |
| Aggregate stats | off | metric definition, no raw/card text | yes if k-anonymous and non-identifying | yes for rare or identifying cohorts | remove source contribution on next recompute | allowed only after policy review |
| Verified rewrite | off | rewritten artifact and verifier notes | no | yes | unpublish rewrite if required source is revoked | no by default |
| Curated pack | off | pack preview, included artifacts, commercial terms | no | yes | remove source or unpublish pack if source is required | yes only with explicit commercial consent |
| Model/eval use | off | purpose, retention, dataset type | no | yes | remove from future training/eval sets when feasible | no by default |
| Raw/source retention | off | raw artifact class, readers, purpose, TTL | no | yes | block reads immediately, delete or crypto-shred by TTL | no |

If a surface is not listed here, consent is denied by default.

## Approval Flow

The approval surface must offer separate actions:

- `Publish redacted card`
- `Request more redaction`
- `Keep private`
- `Discard candidate`
- `Set derived use permissions`
- `Opt in to raw/source retention`

The same screen or CLI review must show:

- exact redacted artifact
- redaction diff or summary
- remaining identifying-risk warnings
- target namespace and visibility
- derived-use selections
- retention period
- revocation path
- digest that will be approved

Any edit, re-redaction, namespace change, derived-use change, or retention change invalidates the approval digest and returns the candidate to review.

## Approval Security

Publication approval uses a one-time signed approval challenge:

- challenge binds subject, tenant, namespace, card version, redacted digest, derived-use policy, raw-retention policy, origin, and expiry
- challenge TTL is 10 minutes
- challenge is single-use
- publish, raw retention, commercial derived use, and model/eval use require step-up reauthentication
- CSRF protection and same-site browser protections are required for web approval
- replay returns a hard error and creates an audit event

## Raw Artifact Consent

Raw/source retention is never bundled with public-card approval.

Raw retention is:

- default off
- separate step
- TTL required, maximum 30 days in MVP
- reader role list required
- purpose required
- revocable independently
- visible in consent history

The CTA must describe the consequence, for example: `Store raw source for 7 days for reviewer redaction`, not `Continue`.

## Revocation Flow

Users need a clear revocation cockpit:

- `My published cards`
- `Consent history`
- `Derived uses`
- `Raw/source retention`
- `Revoke`

Before revocation, show:

- public card version
- derived artifacts that depend on it
- raw/source artifacts tied to it
- audit/legal records that cannot be physically deleted
- expected propagation states

After revocation, show:

- `retrieval blocked`
- `hot index purge pending/done`
- `main index purge pending/done`
- `derived artifact update pending/done`
- `local cache invalidation pending/done`
- `raw/source purge pending/done`

The user-facing rule is: retrieval blocks first, cleanup follows. If cleanup fails, the UI shows the failed projection and retry/escalation path.

## Accessibility Baseline

Consent, revocation, warning, and sidecar surfaces must meet WCAG 2.2 AA.

Required behavior:

- keyboard access for every action
- deterministic focus order
- visible focus state
- screen-reader labels for state and risk
- ARIA live/status regions for async publish/revoke states
- target size suitable for touch
- no color-only risk signaling
- reduced-motion safe status updates
- clear error recovery text

## User-Visible Retrieval States

`no_suggestion` is not silent. It must report one of:

- no authorized match
- low confidence
- safety gate blocked result
- service degraded
- rate limited
- private identifiers required, no public query sent

Sidecar suggestions must allow:

- dismiss
- snooze
- report harmful
- show provenance
- show why this was suggested
- disable inline hints for this workspace
