# Closed-Launch Private-Use Notice

Status: draft disabled

The closed-launch private-use notice is defined as a machine-readable artifact in
`fixtures/private-use-notice.closed-launch-draft.json` and validated by
`schemas/private-use-notice-v0.schema.json`.

This notice does not enable non-synthetic collection. It exists so the future
M1 writer path can be implemented against a fixed consent artifact instead of
inventing collection copy inside a CLI command.

Current private-use rules:

- collection is disabled
- publication is disabled
- candidate writes use the configured closed-launch backend only when the
  operator explicitly submits a bounded structured card
- acknowledgement is required before any future non-synthetic private
  collection
- raw transcripts, raw logs, full stack traces, source file bodies, absolute
  paths, usernames, hostnames, private repository names, customer names,
  secrets, tokens, credentials, and unredacted command output are forbidden

Legacy local writer-draft and synthetic dogfood helpers have been removed. Use
the closed-launch backend runbook for the current operator path.
