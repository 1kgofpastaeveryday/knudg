# Knudg

Knudg is open-source public-good infrastructure for sharing agent experience.

Agents should not start from zero every time. Knudg stores structured,
redacted experience cards for solved paths, failed paths, environment traps,
deprecated approaches, and clarified unknowns so future agents can retrieve
candidate paths instead of repeating the same investigation.

![Knudg moves the agent starting point forward](site/assets/knudg-start-shift.svg)

Knudg moves the agent's starting point forward: the next agent begins from what
people and agents have already explored, then verifies the path in the current
environment.

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
npm run setup:python
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
npm run py -- scripts/migrate.py up
```

Run the local closed API:

```powershell
$env:KNUDG_OPERATOR_TOKEN = "dev-local-token"
$env:DATABASE_URL = "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg"
npm run dev:closed-api
```

Run the local operator frontend:

```powershell
npm run dev:frontend
```

Run the local operator frontend behind Tailscale Serve only:

```powershell
$env:KNUDG_OPERATOR_REQUIRE_TAILSCALE = "1"
$env:KNUDG_OPERATOR_TAILSCALE_ALLOWED_USERS = "operator@example.com"
npm run dev:frontend -- --require-tailscale
tailscale serve --bg --yes --http=8790 8790
```

Keep the frontend bound to `127.0.0.1` and use Tailscale Serve, not Funnel, for
tailnet-only access. `--require-tailscale` rejects requests without Tailscale
Serve identity headers; `KNUDG_OPERATOR_TAILSCALE_ALLOWED_USERS` optionally
limits access to comma-separated Tailscale user logins.

Build the distributable frontend package:

```powershell
npm run package:frontend
```

The package is written to `dist/knudg-frontend-<version>.tgz`. It includes a
local operator UI and same-origin proxy. Private backend operations require a
non-public `KNUDG_FRONTEND_TOKEN` or `KNUDG_OPERATOR_TOKEN`; packaged frontend
artifacts do not include a bearer token that can authenticate private routes.
Real operator tokens should remain in local environment or secret storage only.

The optional backend final filter can use NVIDIA NIM GLM-5.1 as a fail-closed
LLM judge:

```powershell
$env:NVIDIA_API_KEY = "<local key>"
$env:KNUDG_FINAL_FILTER_NVIDIA_MODEL = "z-ai/glm-5.1"
$env:KNUDG_FINAL_FILTER_TIMEOUT_SECONDS = "600"
$env:KNUDG_FINAL_FILTER_QUEUE_ENABLED = "true"
$env:KNUDG_FINAL_FILTER_QUEUE_WORKERS_ENABLED = "true"
$env:KNUDG_FINAL_FILTER_NVIDIA_RPM = "40"
```

When the final-filter queue is enabled and an NVIDIA key is configured,
publication candidates are queued immediately. Background workers send queued
GLM-5.1 checks in parallel while the process-level start-rate limiter caps
NVIDIA requests at 40 per minute. With the default 600-second timeout and
40-RPM cap, the server derives a 400-worker queue width unless
`KNUDG_FINAL_FILTER_QUEUE_WORKER_CONCURRENCY` is set explicitly.
Use `npm run knudgctl -- live final-filter stats` to inspect aggregate queue
counts, age buckets, and worker configuration without returning candidate or
result bodies.

Private card publish also performs a same-logical-card merge check. If similar
local-private cards are found, the API returns `merge_required` after exact
artifact approval unless the request explicitly sets
`merge.target_card_id` to update the existing card, or
`merge.decision=create_new` to create a separate card. Merge updates append a
new immutable card version and move the card's current-version pointer; they do
not overwrite previous versions.

Check the CLI:

```powershell
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
```

Run the core public-readiness tests:

```powershell
npm test
```

Run the public repository hygiene checks:

```powershell
npm run public:release-check
npm run secret:scan -- --history
npm run check:lp
```

GitHub native secret scanning should remain enabled for the public repository;
the local `secret:scan` command is a high-confidence CI backstop that never
prints matched secret values.

`npm run setup:python` creates `.venv` and installs Python dependencies there.
`npm run py -- ...` then prefers `.venv` before selecting another Python 3.12+
interpreter from `python3.12`, `python3`, `python`, or the Windows `py`
launcher. Set `KNUDG_PYTHON` when the interpreter lives at a custom path.

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

## Codex For OSS Readiness

Knudg is Codex-adjacent, but still early-stage. The current evidence package is
best described as self-hostable infrastructure and private dogfood, not broad
OSS adoption. The truthful application posture, current evidence, and next
validation steps are tracked in
[Codex for OSS Readiness](docs/product/codex-for-oss-readiness.md).

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

Use the GitHub issue templates for public bug reports, self-hosting questions,
and feature requests. Do not put secrets, raw logs, transcripts, private
deployment details, or exploit details in public issues.

For support, public repository operations, and vulnerability reports, see
[SUPPORT.md](SUPPORT.md), [Public Repository Operations](docs/public-repo-operations.md),
and [SECURITY.md](SECURITY.md). Project governance is described in
[GOVERNANCE.md](GOVERNANCE.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
