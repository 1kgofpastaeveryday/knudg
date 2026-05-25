# Local Private-Use Notice

Status: draft disabled

The local private-use notice is defined as a machine-readable artifact in
`fixtures/private-use-notice.local-draft.json` and validated by
`schemas/private-use-notice-v0.schema.json`.

This notice does not enable non-synthetic collection. It exists so the future
M1 writer path can be implemented against a fixed consent artifact instead of
inventing collection copy inside a CLI command.

Current local dogfood rules:

- collection is disabled
- publication is disabled
- data does not leave the local workspace
- acknowledgement is required before any future non-synthetic private
  collection
- raw transcripts, raw logs, full stack traces, source file bodies, absolute
  paths, usernames, hostnames, private repository names, customer names,
  secrets, tokens, credentials, and unredacted command output are forbidden

The only active writer helper today is the synthetic local draft path documented
in `docs/operations/local-writer-draft.md`.
