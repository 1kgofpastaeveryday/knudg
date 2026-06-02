# Landing Page Operations Runbook

This maintainer runbook contains deployment, rollback, and smoke-test details
for the static Knudg landing page. It is public-safe project documentation, not
marketing copy.

Document authority:

- classification: public-safe maintainer runbook, not landing-page copy
- owns: deployment steps, rollback procedure, exact release checks, and
  production smoke expectations
- does not own: public marketing message, visible reading order, or localization
  positioning

## Production Configuration

- asset directory: `./site`
- Worker name: `knudg-site`
- canonical custom domain: `knudg.com`
- `www.knudg.com` must not resolve unless a redirect or route is added first
- `www.knudg.com` NXDOMAIN is intentional for the current preview; add a route
  plus 301 redirect before creating any `www` DNS record
- `workers_dev` and preview URLs disabled
- Workers Logs enabled at 10% request sampling; raise temporarily only during
  bounded incidents
- Web Analytics automatic JavaScript injection is blocked with
  `Cache-Control: public, max-age=0, must-revalidate, no-transform`
- Cloudflare Workers Logs use 10% request sampling for operations. Public URLs
  must not carry invite codes, email addresses, secrets, or sensitive query
  strings; raise sampling only during a bounded incident and lower it after the
  incident review.
- HSTS intentionally omits `includeSubDomains` while `www` and product
  subdomains are unsupported; revisit before any subdomain launch
- unknown routes use branded 404 pages through `not_found_handling: "404-page"`
- HTML handling is pinned to `auto-trailing-slash`
- security headers are defined in `site/_headers`

## Pre-Production Validation

- run `npm ci --ignore-scripts` when dependencies are not installed
- run `npm run check:lp` for local rendered overflow/form/button checks
- `npm run check:lp` must verify local English, Japanese, and Simplified
  Chinese pages at `320`, `375`, `767`, `768`, `899`, `900`, `1024`, `1100`,
  `1101`, and `1280` CSS px with zero horizontal document overflow
- `npm run check:lp` must verify each localized document language and reciprocal
  metadata: English uses `<html lang="en">`, Japanese uses `<html lang="ja">`,
  Simplified Chinese uses `<html lang="zh-CN">`, and every primary localized
  page includes canonical plus `hreflang="en"`, `hreflang="ja"`,
  `hreflang="zh-CN"`, and `hreflang="x-default"` links
- `npm run check:lp` must assert header navigation and header status labels are
  hidden at `767px` and visible at `768px`
- `npm run check:lp` must reject `<script>`, `<form>`, `<button>`,
  submit/image/button inputs, `[formaction]`, `mailto:` links,
  `[role="button"]`, clickable closed-state chips, and external anchor links
- `npm run check:lp` must enforce a strict anchor allowlist: section anchors,
  `/`, `/ja/`, `/zh-cn/`, locale equivalents, and documented 404 recovery links only.
  Reject `mailto:`, `tel:`, protocol URLs, downloads, product-route-looking
  relative paths, and every other `href`
- `npm run check:lp` must enforce a strict rendered resource allowlist: the page
  document plus same-origin `/styles.css` only. Reject `@import`, `@font-face`
  `src`, CSS `url()`, external `link` relations, `iframe`, `object`, `embed`,
  `video`, `audio`, `source`, `picture`, and any non-document/non-CSS network
  request
- `npm run check:lp` must assert every checked element's bounding rectangle has
  `left >= 0`, `right <= viewportWidth`, `top >= 0` for first-viewport elements,
  and no horizontal clipping caused by `scrollWidth > clientWidth`
- `npm run check:lp` must compare visible text-bearing element rectangles and
  fail when two non-ancestor rectangles overlap by more than `1px` on both axes,
  except intentional inline text flow inside the same block formatting context
- `npm run check:lp` must assert the closed-state hero strip is visible above
  the fold at all checked viewport widths
- `npm run check:lp` must assert mobile featured-example labeled-row count is no
  greater than three
- `npm run check:lp` must assert Japanese and Simplified Chinese body text
  blocks stay within `min(100%, 42rem)` and do not exceed `34em` on mobile
  widths unless they are cards constrained by the grid
- CSS release checks must keep global `box-sizing: border-box`, responsive
  `max-width` constraints, `min-width: 0` on grid/flex children that can shrink,
  and wrapping rules such as `overflow-wrap: anywhere` for mixed code and Latin
  tokens in cards
- run `npm run deploy:lp:dry-run`
- run `npm run deploy:lp:candidate` for candidate uploads that should not
  immediately receive production traffic
- run `npm run deploy:lp:list` before deploy and record the active version ID
  in release notes so rollback has a known last-good target
- keep preview URLs disabled so alternate public hostnames do not become
  canonical by accident
- future team or public publication flows must satisfy
  `docs/product/publication-control-requirements.md` before access opens

## Production Deploy

```powershell
npm run deploy:lp
```

## Post-Deploy Smoke

```powershell
npm run smoke:lp
```

Expected results:

- `/`, `/ja/`, `/zh-cn/`, and `styles.css` return `200`
- `/`, `/ja/`, and `/zh-cn/` include the expected canonical URL, reciprocal
  `hreflang="en"`, `hreflang="ja"`, `hreflang="zh-CN"`,
  `hreflang="x-default"` alternates, and the expected document language
- unknown English, Japanese, and Simplified Chinese paths return `404` with the
  branded localized 404 body
- `/`, `/ja/`, `/zh-cn/`, `styles.css`, and localized 404s include CSP,
  `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`,
  `Permissions-Policy`, HSTS, and exact cache headers
- expected CSP:
  `default-src 'self'; script-src 'none'; connect-src 'none'; img-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests`
- expected `X-Content-Type-Options`: `nosniff`
- expected `Referrer-Policy`: `strict-origin-when-cross-origin`
- expected `X-Frame-Options`: `DENY`
- expected `Permissions-Policy`: `accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()`
- expected `Strict-Transport-Security`: `max-age=31536000`
- expected `Cache-Control`: `public, max-age=0, must-revalidate, no-transform`
- `www.knudg.com` remains unresolved until an explicit redirect or route is
  configured
- served `/`, `/ja/`, and `/zh-cn/` HTML still contain no scripts, forms, buttons,
  product-action links, or client-side third-party resource loads after
  Cloudflare handling

## Rollback

Find current and prior deployment versions:

```powershell
npm run deploy:lp:list
```

Rollback procedure:

- inspect active and previous deployments with `npm run deploy:lp:list`
- run `npm run rollback:lp -- <version-id>` using the selected last-good version
- the rollback script passes `--message` and `--yes` for incident-safe
  noninteractive use
- run `npm run smoke:lp` immediately after rollback
- keep external synthetic checks for `/`, `/ja/`, `/zh-cn/`, `/styles.css`,
  `/missing`, `/ja/missing`, and `/zh-cn/missing`; alert on status, localized
  404, or security-header drift
