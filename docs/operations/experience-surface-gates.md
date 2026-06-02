# Experience Surface Gates

Status: draft blocked

`fixtures/experience-surface-gates.draft.json` is the machine-checkable gate
manifest for the later broader-experience surfaces:

- actual career/company/place/service experience storage
- public candidate conversion
- B2B respondent portal
- real abuse identity and BAN operations
- raw detail escrow
- company/store dashboard

Validate it:

```powershell
npm run experience:surfaces
npm run experience:activation
npm run experience:storage
npm run public:candidate-conversion
npm run b2b:respondent-portal
npm run abuse:identity-enforcement
npm run raw:detail-escrow
npm run dashboard:company-store
```

The manifest intentionally keeps every enablement flag false. It does not
create real ingest, public serving, B2B delivery, identity processing, raw
detail escrow, or dashboard behavior. It only records the required gates and
forbidden output classes that must remain true before any future implementation
can start.

The DB domain-policy lookup migration is also policy metadata only. It makes
domain policy queryable by the database, but it does not expand stored card
payloads, create broader-domain body tables, or permit non-synthetic
career/place/company submissions.

`candidate_domain_facets` is metadata-only scaffolding for future broader
storage. It stores domain, intent, claim type, subject type/name, payload
digest, policy version, and ingest policy, but DB constraints keep
`stores_raw_body`, `creates_card`, and `indexes` false. Broader domains remain
`disabled_until_gate` or `reviewer_only_after_gate`; this table is not a body
store and does not make candidate facets ingestable.

`experience-surface-activation-request-v0` is the preflight contract for later
attempts to activate items 8-13. It can model the requested surface and the
requested enablement flag, but the validator is preflight-only: it writes no
real data, creates no card, indexes nothing, opens no public/B2B/dashboard
surface, performs no identity processing, and stores no raw detail. Activation
is blocked until the surface gate manifest and every required gate evidence item
are accepted.

`experience-storage-record-v0` is the redacted private record contract for item
8. It models the shape of a future career/place/service experience record after
redaction, while keeping `database_write_enabled`,
`record_visible_to_retrieval`, public conversion, B2B delivery, identity
processing, raw detail escrow, and dashboard serving false. Company, place, or
service names may be represented as public entity names, but selection status,
private messages, private people, exact dates, raw source material, protected
identity signals, and device/network signals must remain absent.

Migration `0012_redacted_experience_storage` is a dormant DDL scaffold for
those redacted private records, not product storage activation. The table can
represent sanitized career and place/service experiences when a future gated
write path exists, but application and worker roles receive no insert, update,
or delete grants today. Row-level security is enabled and forced, raw source and
raw escrow columns are constrained closed, and all future public/B2B/identity
dashboard flags remain false.

The closed private publication-candidate API may also return a disabled
`public-exposure-contract-v0` read model for items 9, 10, and 13. That contract
is bound to the candidate and payload digests and lists required gates and
forbidden outputs, but public candidate conversion, B2B response delivery, and
company/store dashboard serving all remain disabled.

`public-candidate-conversion-request-v0` is the item 9 preflight contract. It
requires conversion to create a new redacted public-candidate artifact digest
rather than mutating the private source record in place. Exact-artifact approval,
consent challenge, and reviewer publish are required, but incomplete in the
draft fixture; the validator therefore reports conversion blocked while keeping
public card creation, public serving, B2B delivery, identity processing, raw
escrow, and dashboards disabled.

`b2b-respondent-portal-request-v0` is the item 10 preflight contract. It can
model only a redacted response outline tied to a public-candidate digest. The
draft fixture keeps respondent identity verification, contact channel,
response availability, portal enablement, B2B delivery, public serving,
identity processing, raw escrow, and dashboard serving disabled. Submitter
identity, raw source material, source metadata, device/network signals,
protected fingerprints, raw moderation evidence, and respondent-visible user
attribution must stay withheld.

`abuse-identity-enforcement-request-v0` is the item 11 preflight contract for
real user identification and BAN operations. It can model a requested abuse
action, including `ban`, but identity resolution is not performed, protected
fingerprints and subject rows are not created, audit events are not written,
and every enforcement transition has `real_effect_enabled = false`. Public,
B2B, respondent, retrieval, export, ranking, raw escrow, and dashboard surfaces
remain disabled, and match status is never disclosed.

`raw-detail-escrow-request-v0` is the item 12 preflight contract. It can model
that a raw-detail escrow would be needed for review, but it creates no escrow
handle, encrypted payload, key material, reviewer access lease, or decrypt
operation. Raw source material, raw review bodies, ciphertext, key material,
source metadata, and reviewer private notes stay withheld, and raw values must
not appear in model input, validator errors, audit output, client responses,
public surfaces, B2B surfaces, dashboards, retrieval, export, or ranking.

`company-store-dashboard-request-v0` is the item 13 preflight contract for
company/store dashboards. It is restricted to the `public_aggregate_signal`
domain and keeps dashboard serving, aggregate signal queries, B2B delivery,
respondent portal access, public serving, identity processing, raw escrow,
retrieval, export, and ranking disabled. It also blocks single-observation
display and any review-suppression surface until aggregate signal, disclosure,
moderation, minimum source count, manipulation resistance, no-identity-leakage,
no-single-observation, no-suppression, and correction/takedown gates pass.
