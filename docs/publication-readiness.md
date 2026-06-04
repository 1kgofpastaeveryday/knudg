# Public Repository Readiness

This checklist defines the minimum bar before making this repository public.

## Required Before Public Release

- Root README describes the OSS project, self-hosting path, safety model, and
  hosted-network positioning.
- `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `.env.example`, and
  `CODE_OF_CONDUCT.md` exist.
- `.gitignore` excludes local operator state, raw logs, generated drafts,
  browser artifacts, database dumps, dependency caches, and environment files.
- Fixtures are synthetic, blocked, draft, model-only, or explicitly redacted.
- No committed file contains real credentials, raw transcripts, generated local
  private draft bodies, personal operator notes, local hostnames, SSH details,
  or absolute machine paths.
- Public docs do not instruct users to rely on a private operator-only
  deployment.

## History Warning

Cleaning the working tree is not the same as cleaning git history. If sensitive
material was ever committed, rotate the secret and rewrite or recreate the
public repository before publishing.

For this repository, the public tip is expected to exclude local operator notes,
raw user intent logs, private deployment runbook details, generated local
candidate drafts, and browser/session artifacts. Before changing GitHub
visibility, create a fresh public repository from the cleaned tree or run a
reviewed history rewrite that removes historical private artifacts.

## Current Verification Commands

Use these checks before publishing:

```powershell
git status --short --ignored
npm run py -- -m pytest tests/test_knudg_plugin_manifest.py tests/test_knudg_client_config.py tests/test_knudg_local_frontend.py tests/test_task_profile_schema.py
npm run check:lp
```

Run a secret scanner such as GitHub secret scanning, Gitleaks, or TruffleHog on
the final public repository before making it discoverable.

## Current Intent

Knudg should be open-source and self-hostable. The official hosted network may
offer the largest reviewed corpus, managed retrieval, higher limits, and team
controls, but the OSS backend must remain useful without the hosted service.
