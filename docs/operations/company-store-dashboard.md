# Company Store Dashboard Preflight

Status: blocked preflight scaffold

This gate covers goal item 13: company/store dashboard surfaces for public
aggregate signals. The current contract is intentionally preflight-only. It
does not serve a dashboard, create a dashboard view, query aggregate signal
data, show single observations, suppress or hide reviews, open public serving,
deliver to B2B, open a respondent portal, process identity, store raw detail,
make data retrievable, export dashboard data, or write audit events.

Artifacts:

- schema: `schemas/company-store-dashboard-request-v0.schema.json`
- fixture: `fixtures/company-store-dashboard.blocked.json`
- validator: `scripts/validate_company_store_dashboard.py`
- tests: `tests/test_company_store_dashboard.py`

Validate:

```powershell
npm run dashboard:company-store
python -m pytest tests/test_company_store_dashboard.py
```

The fixture must keep:

- `request_class = preflight_only`
- `surface = company_store_dashboard`
- `status = blocked`
- `dashboard_subject.domain = public_aggregate_signal`
- `aggregate_signal_available = false`
- `minimum_group_size_met = false`
- `single_observation_display_enabled = false`
- `negative_review_suppression_enabled = false`
- `review_suppression_surface_enabled = false`
- `manipulation_response_controls_enabled = false`
- `dashboard_enabled = false`
- `dashboard_serving_enabled = false`
- `public_serving_enabled = false`
- `b2b_delivery_enabled = false`
- `respondent_portal_enabled = false`
- `identity_processing_enabled = false`
- `raw_detail_escrow_enabled = false`

Required gates:

- `AGGREGATE_SIGNAL_POLICY`
- `PUBLIC_B2B_DISCLOSURE_POLICY`
- `MODERATION_WORKFLOW`
- `NO_IDENTITY_LEAKAGE_TESTS`
- `MIN_SOURCE_COUNT_POLICY`
- `MANIPULATION_RESISTANCE_POLICY`
- `NO_SINGLE_OBSERVATION_DISPLAY_TESTS`
- `NO_SUPPRESSION_SURFACE_TESTS`
- `CORRECTION_TAKEDOWN_POLICY`

Validator schema errors return only paths and validator names. Gate failures do
not echo raw source material, submitter identity, source metadata, protected
fingerprints, single-observation details, reviewer notes, or private moderation
evidence.
