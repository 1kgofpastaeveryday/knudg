# Contributing

Thanks for working on Knudg. The project is intended to be public,
self-hostable infrastructure for agent-readable experience cards.

## Development Setup

```powershell
npm install
python -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
```

Run focused tests before broad suites:

```powershell
npm run py -- -m pytest tests/test_knudg_closed_api.py tests/test_knudg_live_agent.py
```

Before opening a pull request that changes public docs, CI, schemas, fixtures,
or publication/security gates, run:

```powershell
npm run public:release-check
npm run secret:scan -- --history
```

## Contribution Rules

- Keep examples and fixtures synthetic unless a maintainer explicitly approves a
  reviewed, redacted artifact.
- Do not commit raw logs, transcripts, local draft outputs, private browser
  artifacts, `.env` files, database dumps, credentials, or machine-specific
  notes.
- Prefer schema-backed structured data over ad hoc JSON.
- Add or update tests when changing schemas, migrations, API contracts, CLI
  behavior, consent/revocation gates, or domain policy.
- Keep retrieval output advisory. A retrieved card must never become an
  executable instruction by itself.

## Pull Request Checklist

- The change is scoped and documented.
- New or changed public behavior has tests.
- Any fixture is synthetic or explicitly redacted.
- No secrets, personal data, local paths, hostnames, or raw transcript excerpts
  were added.
- Public docs do not mention private deployment credentials or operator-local
  state.

## Issues

Use the GitHub issue templates for public bug reports, self-hosting questions,
and feature proposals. Keep issue content synthetic and redacted. Vulnerability
reports or accidental private-data exposure reports belong in the private
security reporting path described in [SECURITY.md](SECURITY.md), not in public
issues.

## Reporting Security Issues

Do not open public issues for vulnerabilities or accidental private-data
exposure. Follow [SECURITY.md](SECURITY.md).
