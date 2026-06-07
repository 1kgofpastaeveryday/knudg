# Review Operations Gate Scaffold

Status: draft scaffold, reviewer publish and public display disabled

The review operations gate scaffold records DEC-018 prerequisites for reviewer
lanes, assignment, high-risk verification, malicious-card testing, and pause
rules. It does not enable reviewer publish, public display, or high-risk card
body expansion.

The final publication check must include an explicit "is this an ad or spam?"
assessment. Undisclosed ads, sponsorship, affiliate incentives, lead-capture
promotions, reputation manipulation, fake experience claims, and coordinated or
repeated low-signal submissions block publication rather than entering the
public corpus.

The LLM final filter returns exactly three operator-facing verdicts: `pass`
(Clear OK), `hold` (Suspicious), or `reject` (Clear NG). `hold` is not a
terminal human-review state. It starts an automated repair loop: three parallel
reviewers list OK points, NG points, and whether the candidate is worth
repairing. If repair is worthwhile, the writer LLM receives the NG points only,
attempts a fix, and the candidate is reviewed again by three parallel reviewers.
The loop passes only when all three reviewers pass it, or rejects when reviewers
judge it not worth repairing or after three writer attempts without a pass.

When an NVIDIA key and database are configured, publication candidates enter the
final-filter queue immediately instead of waiting for GLM-5.1 on the request
path. Queue workers process jobs in parallel behind a process-level start-rate
limiter capped at 40 NVIDIA requests per minute. Provider 429/5xx/timeouts are
requeued with backoff until the retry cap, then held for the repair loop. The
default GLM timeout is 600 seconds; at the 40-RPM cap the server derives 400
parallel workers so long-running checks can still saturate the allowed start
rate.

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
{"ad_or_spam_check_required": true, "high_risk_body_expansion_enabled": false, "hold_repair_loop_enabled": true, "llm_verdicts": ["hold", "pass", "reject"], "public_display_enabled": false, "reviewer_publish_enabled": false, "status": "ok"}
```

## Boundary

The scaffold may name lane IDs, fixture-set IDs, threshold labels, and blocking
gates. It must not contain real reviewer identities, customer examples, raw
candidate bodies, transcripts, repository URLs, credentials, or private
diagnostic artifacts.

Reviewer publish, public display, and high-risk body expansion remain disabled
until DEC-018 is accepted and the review-ops RFC, calibration tests,
malicious-card tests, high-risk reproduction lab, pause rules, and reviewer
session hardening all pass. The accepted review-ops evidence must also show
that the final publication check evaluates ad/spam risk before reviewer publish.
