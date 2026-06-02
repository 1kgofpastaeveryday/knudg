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
python -m pytest tests/test_knudg_closed_api.py tests/test_knudg_live_agent.py
```

Use `npm run gates:all` only when you need the full validation sweep.

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

## Reporting Security Issues

Do not open public issues for vulnerabilities or accidental private-data
exposure. Follow [SECURITY.md](SECURITY.md).
