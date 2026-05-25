# Adversarial Review — Public Landing Page — 2026-05-12

## Target

- `site/index.html`
- `site/ja/index.html`
- `site/404.html`
- `site/ja/404.html`
- `site/styles.css`
- `site/_headers`
- `wrangler.jsonc`
- `package.json`
- `scripts/smoke-knudg-site.ps1`
- `scripts/check-knudg-layout.js`
- `docs/product/landing-page-design.md`
- `docs/product/landing-page-ja-design.md`
- Live: `https://knudg.com/`, `https://knudg.com/ja/`

## Result

PASS.

Five independent lanes completed with no score at or below the failure
threshold:

| Lane | Result | Notes |
| --- | --- | --- |
| Attack Surface | PASS | No active product access, forms, scripts, or external assets. Parked query-string/logging enforcement until invite/private preview URLs exist. |
| Production Stress | PASS | Rollback script, cache policy, smoke coverage, and deployment docs were tightened. External monitoring remains parked. |
| Assumption Challenger | PASS | Outcome and safety claims were softened to design/launch-requirement language. |
| Implementation Reality | PASS | Rollback and Japanese 404 smoke gaps were fixed. Mobile navigation issue was handled after Coherence review. |
| Coherence Auditor | PASS | Mobile overflow was fixed and verified with rendered checks. |

## Verification

- `npm run check:lp`
- `npm run deploy:lp:dry-run`
- `npm run deploy:lp`
- `npm run smoke:lp`
- Live 320px and 390px rendered overflow probes for English and Japanese pages

Latest deployed Worker version: `c09b1dca-e601-40ec-b291-54a54fd0782a`.

## Parked Findings

- External synthetic monitoring is documented but not created yet.
- `www.knudg.com` remains intentionally unresolved until a redirect policy is
  added.
- HSTS intentionally omits `includeSubDomains` while subdomains are unsupported.
- CSS keeps conservative revalidation instead of long-lived immutable caching.
- CSS selector cleanup and locale override consolidation are future maintenance
  work.
