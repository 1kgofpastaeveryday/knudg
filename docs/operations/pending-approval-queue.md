# Pending Approval Queue

Status: model only

`schemas/pending-approval-queue-v0.schema.json` defines the local pending
approval queue item shape for the future writer path. The current fixture
`fixtures/pending-approval-queue.model-only.json` is not a live queue and does
not enable storage of non-synthetic candidates.

The queue item model stores only:

- opaque queue/candidate IDs
- tenant and namespace IDs
- card and artifact digests
- consent scope
- preview reference
- TTL
- discard and purge paths

The model does not store raw transcripts, raw logs, full card bodies, source
file bodies, secrets, tokens, private repository names, or unredacted command
output.

Live queue storage remains gated by:

- accepted WEDGE-001 protocol
- private-use notice acknowledgement
- protected-data durability gate
- non-local request-context verifier profile for protected data
- discard/purge behavior and idempotency tests
