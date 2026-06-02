# Review Operations Gate Scaffold

Status: draft scaffold, reviewer publish and public display disabled

The review operations gate scaffold records DEC-018 prerequisites for reviewer
lanes, assignment, high-risk verification, malicious-card testing, and pause
rules. It does not enable reviewer publish, public display, or high-risk card
body expansion.

## Files

- `schemas/review-ops-gates.schema.json` defines the gate fixture shape.
- `fixtures/review-ops-gates.draft.json` is the current draft scaffold.
- `scripts/validate_review_ops_gates.py` validates the fixture and blocks
  premature accepted status unless `docs/decisions/README.md` marks DEC-018
  accepted.
  Accepted status also requires an existing review-ops evidence artifact under
  `docs/operations/evidence/`; fixture fields alone cannot prove calibration,
  malicious-card, lab, pause-rule, or session-hardening completion.

## Command

```powershell
npm run review:gates
```

Expected current result:

```json
{"high_risk_body_expansion_enabled": false, "public_display_enabled": false, "reviewer_publish_enabled": false, "status": "ok"}
```

## Boundary

The scaffold may name lane IDs, fixture-set IDs, threshold labels, and blocking
gates. It must not contain real reviewer identities, customer examples, raw
candidate bodies, transcripts, repository URLs, credentials, or private
diagnostic artifacts.

Reviewer publish, public display, and high-risk body expansion remain disabled
until DEC-018 is accepted and the review-ops RFC, calibration tests,
malicious-card tests, high-risk reproduction lab, pause rules, and reviewer
session hardening all pass.
