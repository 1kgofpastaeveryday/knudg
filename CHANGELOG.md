# Changelog

All notable public changes to Knudg are tracked here.

## Unreleased

- Added public launch positioning with competitive context and announcement
  copy drafts.
- Reframed README and landing-page copy from generic memory to a coding-agent
  worklog.

## 0.1.1 - 2026-06-16

Release hardening after the initial public release.

- Added the verified v0.1.0 clean-machine quickstart transcript and moved the
  Codex for OSS readiness evidence from "missing" to "available."
- Added an adjacent-work architecture note that positions Knudg relative to
  knowledge formats and curated workflow libraries without changing the target
  upload boundary.
- Updated landing-page deployment scripts to use the pinned local Wrangler
  devDependency.
- Upgraded Wrangler and pinned transitive audit fixes for `esbuild` and `ws`.
- Optimized history secret scanning so the public CI gate scans unique git
  blobs instead of each file at each revision.
- Updated landing-page smoke checks and runbook anchor policy to allow the
  canonical GitHub repository link while still rejecting other external
  anchors.
- Synced `LICENSE` with the canonical Apache-2.0 license text for repository
  license detection.
- Fixed a stale trust-model link to point at the current target model.

## 0.1.0 - 2026-06-16

Initial public release.

- Published Apache-2.0 repository scaffolding with README, security,
  contributing, governance, support, and code of conduct documents.
- Added closed-launch private backend primitives, CLI commands, migrations,
  schemas, synthetic fixtures, validators, tests, and Codex plugin/skill assets.
- Documented the default-private safety model, consent/revocation gates,
  retrieval-domain boundaries, and public publication blockers.
- Added a Node-based Python launcher for npm scripts so local commands select a
  Python 3.12+ interpreter consistently across macOS, Linux, Windows, and CI.
- Added Codex for OSS readiness notes with truthful application language,
  current evidence, missing evidence, and validation steps.
- Added an adversarial review report for Codex for OSS fit.
- Documented trust model with lifecycle states and demotion paths.
- Hardened public repository security posture and constrained frontend
  distribution token.
- Added closed launch queue operations and structured logging for closed API
  access.
