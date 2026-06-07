# Adversarial Review R2: Codex for OSS Strengthening

Date: 2026-06-04

## Verdict

FAIL.

The strengthening work improved the story, but it also introduced new
review-blocking inconsistencies. The biggest blockers are now concrete and
fixable: the advertised quickstart still checks the wrong profile, the new
synthetic demo can be misread as measured evidence, the report path conflicts
with the public-release validator, and the new Python launcher/setup path lacks
dependency and interpreter trust controls.

This is no longer mainly a "no adoption" problem. It is now a "do not submit or
publish this exact strengthening package until the evidence and quickstart
contracts are coherent" problem.

## Review Targets

- `README.md`
- `CHANGELOG.md`
- `package.json`
- `.github/workflows/ci.yml`
- `.gitignore`
- `scripts/run-python.js`
- `scripts/install-python-deps.js`
- `scripts/validate_public_release.py`
- `scripts/knudg_client_config.py`
- `scripts/knudgctl.py`
- `docs/product/codex-for-oss-readiness.md`
- `docs/reviews/adversarial-review-2026-06-04.md`
- `fixtures/codex-oss-demo-wedge-evidence.sample.json`
- updated operations and development docs

## Top Findings

### 1. README Quickstart Still Fails The Local CLI Check

Severity: Tier 1

`README.md` starts the local closed API, then tells users to run:

```text
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
```

In the current workspace this resolves to the default `cloud` profile and
returns `status: not_configured`. `scripts/knudg_client_config.py` defaults to
`active_profile="cloud"`, and copying `.env.example` does not change that.

Required fix: make the quickstart explicitly configure or select the local
profile, then add a CI smoke test that starts the local API and verifies
`server status` and `server capabilities` against it.

### 2. Review Reports Must Stay Out Of `docs/plans/`

Severity: Tier 1

The previous review report and this R2 report were initially drafted under
`docs/plans/`, but `scripts/validate_public_release.py` denies tracked paths
with the `docs/plans/` prefix. Public review artifacts should live under
`docs/reviews/`.

Required fix: keep public review reports in `docs/reviews/`, or remove them
from public-facing references if they are not intended to be public artifacts.

### 3. Synthetic Demo Fixture Looks Like Evidence But Is Only Schema-Valid

Severity: Tier 1

`docs/product/codex-for-oss-readiness.md` lists
`fixtures/codex-oss-demo-wedge-evidence.sample.json` under available evidence.
The fixture contains plausible-looking review minutes, reproduction minutes,
confidence, and `accepted_private` decisions, but the digests are placeholder
values and the validator checks only shape, not artifact truth or replay.

Required fix: rename this as a synthetic schema/demo fixture, not evidence.
Either remove metric-like fields or mark them as synthetic estimates. If the
goal is real evidence, add canonical source/redacted artifacts and recompute
digests during validation.

### 4. Evidence Register And Candidates Are Not Linked

Severity: Tier 1

The demo fixture has `evidence_register` and `seed_candidates` as parallel
lists. Candidates do not reference supporting evidence records, and the
validator checks each list independently.

Required fix: add `evidence_id` or source/redacted evidence references to each
candidate and validate referential integrity, digest role compatibility, and
one-to-one or many-to-one rules.

### 5. Python Setup Is Now Easier, But Trust And Reproducibility Are Weak

Severity: Tier 1 / Tier 2

`npm run setup:python` installs live PyPI ranges without a lockfile or hashes.
`KNUDG_PYTHON` can bypass the documented `.venv` runtime path. Existing stale
`.venv` directories are not version-checked before dependency installation.
The launcher also has no direct tests for interpreter selection, stale venvs,
exit-code propagation, Windows launcher behavior, or failure messages.

Required fix: add a Python lock or constraints path for CI/public quickstart,
define `KNUDG_PYTHON` as either venv-creation-only or runtime override, validate
`.venv` before install, and add direct Node tests for the wrapper scripts.

### 6. Cloud Runbook Normalizes A Static Bearer API On `0.0.0.0`

Severity: Tier 1

`docs/operations/cloud-closed-launch-runbook.md` shows a non-loopback server
bind. The server uses a static bearer token. The runbook does not put the TLS,
private network, reverse proxy, or "do not expose directly" requirement next to
the command.

Required fix: require TLS-terminating reverse proxy or private network plus
firewall, prohibit direct internet exposure, and add startup fail/warning logic
for non-loopback binds unless an explicit reviewed deployment flag is present.

### 7. Release And Readiness State Contradict Each Other

Severity: Tier 2

`CHANGELOG.md` says `0.1.0 - Initial Public Release`; `package.json` is already
`0.1.0`; `docs/product/codex-for-oss-readiness.md` says there are no tagged
releases. These can all be true only if the wording distinguishes package
metadata, public repository publication, and tagged release.

Required fix: choose one status: unreleased `0.1.0`, initial public repository
drop, or tagged release. Update the changelog and readiness doc accordingly.

### 8. New Demo Command Is Not In CI Or `gates:all`

Severity: Tier 2

`package.json` adds `codex:oss-demo`, and the readiness doc cites it. CI and
`gates:all` do not run it, so the cited fixture can drift while normal gates
pass.

Required fix: add `npm run codex:oss-demo` to CI and `gates:all`, or stop
presenting it as readiness evidence.

### 9. Clean-Machine Setup Is Still Incomplete

Severity: Tier 2

CI installs Playwright browsers, but README does not. README also uses
PowerShell-only commands while claiming npm commands are the cross-platform
entry point. README uses `npm install` while CI uses `npm ci`.

Required fix: document `npm ci` for clean checkout, add `setup:browsers`, and
provide POSIX plus PowerShell command variants or shell-neutral npm scripts.

## Required Design Changes

1. Fix local profile setup in README and CI.
2. Decide where public review reports live, then align
   `validate_public_release.py`.
3. Rename or harden the Codex demo fixture so it cannot be mistaken for
   measured evidence.
4. Add candidate-to-evidence references and digest/replay semantics before
   using demo data as evidence.
5. Add Python dependency locking or constraints for public setup and CI.
6. Harden `run-python.js` and `install-python-deps.js` with a clear
   `KNUDG_PYTHON` contract, `.venv` validation, and direct tests.
7. Strengthen the non-loopback closed API runbook and startup behavior.
8. Clarify release status across `CHANGELOG.md`, `package.json`, and readiness
   docs.

## Deferred Risks

- `gates:all` remains a long `&&` chain that is hard to triage.
- B2B/company-store scripts are still named like product tracks even though
  strategy says those surfaces are retired except as blocked/safety checks.
- Full `npm audit` should be considered because the repo's operational JS
  tools are dev dependencies; `npm audit --omit=dev` is not enough evidence for
  this toolchain.

## Scores By Lane

| Lane | Correctness | Completeness | Implementability | Resilience |
| --- | ---: | ---: | ---: | ---: |
| Attack Surface | 6 | 5 | 7 | 4 |
| Production Stress | 5 | 4 | 5 | 4 |
| Assumption Challenger | 6 | 5 | 6 | 4 |
| Implementation Reality | 6 | 5 | 6 | 4 |
| Data Integrity | 4 | 4 | 6 | 4 |
| Coherence Auditor | 4 | 5 | 4 | 4 |

## Next Fix Round

Fix in this order:

1. Make README quickstart pass exactly as written.
2. Keep review reports under `docs/reviews/`, not `docs/plans/`.
3. Downgrade the Codex demo to a schema fixture or add real digest/replay
   validation.
4. Put `codex:oss-demo` into CI only after its semantics are corrected.
5. Add direct tests and trust policy for the Python launcher/setup scripts.
