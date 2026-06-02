# M1 Writer Backlog

Status: closed-launch aligned

The legacy synthetic writer-draft command and local-only writer path have
been removed. The remaining writer-relevant implementation is the database and
closed-launch backend substrate for bounded structured card submission,
approval-required write candidates, and private publication disabled by
default.

Authority by surface:

- Greencloud closed-launch implementation for operator-private structured card
  submission.
- Product design for non-synthetic product-path candidate intake.
- Consent/revocation design for trusted approval completion.
- Production-readiness gates for protected-data durability, intake safety,
  audit, and no-log ingress.
- `knudgctl writer *` for backend primitive tests/support only, not as a
  product path.

Do not restore the removed writer-draft helper unless a new accepted
design explicitly requires an offline fixture generator.
