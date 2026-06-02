# WEDGE-001 Opaque Evidence Helpers

Status: local helper for pre-M1 research evidence

`scripts/wedge_evidence.py` validates private-research snapshot metadata and
writes repo-safe summaries for WEDGE-001 dry-run evidence. It is not an intake
surface and does not store raw prospect, candidate, transcript, repository, or
customer data.

## Commands

Validate a private snapshot export:

```powershell
npm run wedge:evidence -- validate --input path\to\private-snapshot.json
```

Write a repo-safe summary:

```powershell
npm run wedge:evidence -- summary --input path\to\private-snapshot.json --output path\to\summary.json
```

The summary contains only opaque IDs, snapshot digests, counts, consent-state
counts, decision counts, risk counts, and median/p90 timing summaries.

## Input Boundary

The helper accepts the fields defined by
`docs/product/wedge-001-validation-workbook.md` for evidence-register rows and
seed-candidate rows.

The helper rejects:

- unknown fields
- raw URLs, email addresses, local absolute paths, repository hosting URLs, and
  secret-looking strings
- non-opaque IDs
- non-`sha256:<hex>` digests
- unclear-rights candidates marked as public candidates
- rejected or abandoned candidates without a code-only rejection reason

Source artifacts, transcripts, raw logs, repository URLs, prospect names,
company names, customer incidents, credentials, and private diagnostic bodies
remain outside this repository.
