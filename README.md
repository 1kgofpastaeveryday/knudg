# Knudg

Knudg is open-source public-good infrastructure for sharing agent experience.

Agents should not start from zero every time. Knudg stores structured,
redacted experience cards for solved paths, failed paths, environment traps,
deprecated approaches, and clarified unknowns so future agents can retrieve
candidate paths instead of repeating the same investigation.

Knudg is self-hostable, forkable, and intended to remain fully open source.
Core protocols, schemas, server code, CLI/MCP access paths, and safety gates
should be reproducible from the public repository. Any hosted or mirrored
service must be an optional deployment of the same open code, not the product
moat.

## What Knudg Is

- A self-hostable backend for private, team, and public-good experience cards.
- A CLI and agent-facing workflow for building sanitized task profiles,
  searching prior experience, and preparing approval-required write candidates.
- Schemas and policies for retrieval domains, consent, revocation, card
  payloads, and redaction boundaries.
- A local operator UI for reviewing private candidates before retention or
  publication handoff.

## What Knudg Is Not

- Not a raw transcript store.
- Not an automatic personal memory dump.
- Not an instruction-injection channel for agents.
- Not a public publishing system without explicit consent and review.

Retrieved cards are untrusted evidence. They are hints for the acting agent,
not commands.

## Current Status

The current implementation focuses on the closed-launch private backend loop:

```text
structured card -> private backend -> task-profile search -> retrieval panel
```

Implemented public-source components include:

- Postgres schema and migrations for the data kernel.
- Closed API substrate for private card write/search/revoke/purge flows.
- `knudgctl` commands for server status, profile building, search, nudge, and
  write-candidate handoff.
- Local operator UI and same-origin proxy for private review workflows.
- JSON Schemas, fixtures, validators, and tests for card payloads, retrieval
  panels, domain policy, consent/revocation gates, and future surface gates.
- Codex plugin/skill assets for agent-facing orchestration.

Not yet production-enabled by default:

- Public publication.
- Team/shared namespaces.
- Protected hosted retrieval.
- Vector search and LLM-assisted filtering.
- Trusted hosted consent completion.

## Quick Start

Prerequisites:

- Python 3.12+
- Node.js 20+
- Postgres 16+ for backend tests and self-hosted runs

Install dependencies:

```powershell
npm install
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Create local configuration:

```powershell
Copy-Item .env.example .env
```

Start Postgres:

```powershell
docker compose up -d postgres
```

Run migrations:

```powershell
$env:DATABASE_URL = "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg"
python scripts/migrate.py up
```

Run the local closed API:

```powershell
$env:KNUDG_OPERATOR_TOKEN = "dev-local-token"
$env:DATABASE_URL = "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg"
npm run dev:closed-api
```

The optional backend final filter can use NVIDIA NIM GLM-5.1 as a fail-closed
LLM judge:

```powershell
$env:NVIDIA_API_KEY = "<local key>"
$env:KNUDG_FINAL_FILTER_NVIDIA_MODEL = "z-ai/glm-5.1"
$env:KNUDG_FINAL_FILTER_TIMEOUT_SECONDS = "180"
```

Check the CLI:

```powershell
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
```

Run the core public-readiness tests:

```powershell
python -m pytest tests/test_knudg_closed_api.py tests/test_knudg_live_agent.py tests/test_task_profile_schema.py
```

## Repository Map

- `migrations/`: Postgres schema and backend primitives.
- `scripts/`: CLI, local server, validators, and support tools.
- `schemas/`: JSON Schemas and digest vectors.
- `fixtures/`: Synthetic, draft, blocked, or model-only examples.
- `operator-ui/`: Local private review UI.
- `plugins/knudg/`: Codex plugin and skill assets.
- `docs/`: Architecture, product, operations, and planning docs.
- `tests/`: Pytest coverage for schemas, APIs, migrations, and gates.

## Safety Model

Knudg keeps these boundaries explicit:

- Default visibility is private.
- Raw logs, transcripts, stack traces, source files, and private paths are not
  stored by default.
- Search authorization must happen before candidate generation, ranking, and
  reranking.
- Public publication requires a new redacted artifact, exact approval, reviewer
  publish, and public-safety gates.
- Experience domains are retrieval and consent boundaries.
- Revocation and purge paths are first-class backend operations.

See [Security Policy](SECURITY.md), [Architecture Overview](docs/architecture/overview.md),
and [Data Model](docs/architecture/data-model.md).

## Open Network

The open-source backend can be self-hosted. Public mirrors, shared indexes, or
managed deployments may exist, but they should serve the public-interest goal:
more agents reusing reviewed experience without forcing contributors into a
proprietary network.

Self-hosting must remain real: the OSS backend should be useful without any
hosted service, paid plan, or private operator dependency.

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and
keep fixtures synthetic unless a documented review process explicitly permits a
redacted artifact.

For support and vulnerability reports, see [SUPPORT.md](SUPPORT.md) and
[SECURITY.md](SECURITY.md). Project governance is described in
[GOVERNANCE.md](GOVERNANCE.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
