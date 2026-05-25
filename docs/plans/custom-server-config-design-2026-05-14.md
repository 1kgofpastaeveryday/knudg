# Custom Server Configuration Design - 2026-05-14

Status: reviewed and implemented for local CS1-CS3

## Goal

Knudg clients must support explicit custom server targets so local dogfood can
use the same eventual connection model as Knudg Cloud without enabling
protected remote custom-server behavior prematurely.

The immediate implementation goal is a local/synthetic contract, not a full
production auth rollout:

- let `knudgctl` read and report a configured server URL
- allow local development targets such as `http://localhost:<port>` only when
  explicitly selected as the `local` profile
- keep cloud as the default inert profile
- expose local server readiness and capability checks aligned with the existing
  operations health contract
- fail closed when a configured server does not advertise compatible
  capabilities
- avoid storing credentials or private card content in config

## Non-Goals

- No real hosted Knudg Cloud integration in this slice.
- No OAuth token issuance, refresh, DPoP key management, SSO, SAML, OIDC, or
  protected-resource metadata fetching in this slice.
- No protected-data retrieval enablement.
- No public publication or external MCP rollout.
- No enterprise server probing, self-host license enforcement, entitlement,
  support, update, SSO, or telemetry mechanism in this slice.

## Product Boundary

Custom server support is a product feature, not a license giveaway.

Profiles:

- `cloud`: default SaaS endpoint placeholder, no custom probing in this slice
- `local`: explicit loopback development endpoint for dogfood and CI
- `enterprise`: reserved profile name only; not accepted by `config set-server`
  until a later reviewed enterprise deployment design exists

The local path exists to make development and verification possible with
synthetic/local dogfood only. Enterprise/private deployment remains a future
commercial packaging, support, SSO, audit, compliance, entitlement, update, and
SLA surface.

Future enterprise activation requires a separate reviewed design covering:

- who may add or change enterprise URLs
- how tenants prove ownership
- how users revoke a server
- how paid private deployments are distinguished from local development
- how support/debug telemetry works
- how custom CA, proxy, DNS, TLS, deployment identity, entitlement, and signed
  capability rotation work

## Sources And Constraints

- `docs/architecture/agent-access.md` says arbitrary remote URLs are allowed
  only when explicitly configured and pinned.
- `docs/architecture/overview.md` keeps Knudg central infrastructure, not a
  personal local memory app.
- `docs/architecture/operations.md` already defines health endpoints such as
  startup/readiness/liveness.
- MCP authorization expects protected resource metadata for restricted MCP
  servers, and the metadata lists authorization servers.
- OAuth Resource Indicators let a client request tokens for a specific
  protected resource URI.
- DPoP later binds tokens to a proof key and request target, but this slice
  only reserves config fields and does not mint or validate tokens.

References:

- MCP Authorization specification:
  https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
- RFC 8707 OAuth 2.0 Resource Indicators:
  https://www.ietf.org/rfc/rfc8707.html
- RFC 9449 OAuth 2.0 DPoP:
  https://www.rfc-editor.org/rfc/rfc9449

## Configuration Model

Config is profile-scoped. The default profile is `cloud`.

Minimal config shape:

```json
{
  "schema_version": 1,
  "active_profile": "local",
  "profiles": {
    "cloud": {
      "server_url": "https://api.knudg.com",
      "auth_profile": "cloud",
      "pin": null,
      "tenant_id": null,
      "capabilities_cache": null
    },
    "local": {
      "server_url": "http://localhost:8787",
      "auth_profile": "local",
      "pin": null,
      "tenant_id": null,
      "capabilities_cache": null
    }
  }
}
```

Config storage:

- default path: `.codex/knudg/client-config.json` for local dogfood
- override path: `KNUDG_CONFIG`
- server URL env override: `KNUDG_SERVER_URL`
- tenant env override: `KNUDG_TENANT_ID`
- auth profile env override: `KNUDG_AUTH_PROFILE`

Config must not contain:

- access tokens
- refresh tokens
- private keys
- private card bodies
- raw approval artifacts
- raw retrieval profiles

Config file writes must be atomic:

- write a temporary file in the same directory, then replace
- create parent directories before writing
- reject symlink config paths
- reject symlink, junction, or reparse-point traversal in config parent
  directories when the platform exposes that metadata
- treat malformed JSON as `usage_error`
- use user-only permissions where the platform exposes them
- keep `.codex/knudg/client-config.json` out of review targets and support
  bundles unless explicitly requested

Effective config precedence:

1. explicit CLI flags for the current command
2. environment overrides
3. active profile in the config file
4. built-in cloud default

Overrides do not mutate the stored profile unless the command is `config
set-server` or `config use-profile`. If any effective `server_url`,
`auth_profile`, or `tenant_id` differs from the stored pinned tuple, the client
sets `pin_state = "override_unpinned"`, skips capability caching, and disables
all protected operations. This slice has no protected operations, but tests must
prove the effective state is visibly unpinned.

## Server URL Rules

Allowed schemes:

- `https` for `cloud` and `enterprise`
- `http` only for explicit `local` profile and loopback hosts

Allowed local hosts:

- `localhost`
- `127.0.0.1`
- `[::1]`

Rejected:

- URLs with userinfo
- non-HTTP schemes
- fragments
- enterprise/cloud `http`
- non-loopback `http`
- blank host

The normalized server URL:

- uses lowercase scheme and host
- strips a trailing slash
- rejects path, query, fragment, and userinfo for this slice
- rejects percent-encoded hosts
- rejects hostnames ending in a trailing dot
- preserves explicit ports

For the `local` profile, `http` is accepted only for exact loopback hostnames or
IP literals after parsing: `localhost`, `127.0.0.1`, or `::1`.

For `cloud`, only the built-in default URL is valid in CS1-CS3. `config
set-server --profile cloud` and all `enterprise` profile writes return
`not_configured` until the relevant commercial deployment design exists.

## Pinning Model

Every non-cloud profile must become pinned before protected operations. In
CS1-CS3, the only pinnable profile is `local`, and its pin class is explicitly
dev-only.

MVP pin shape:

```json
{
  "server_url": "http://localhost:8787",
  "server_id": "local-dev",
  "deployment_type": "local",
  "api_version": "v1",
  "capabilities_digest": "sha256:<hex>",
  "capability_resource_origin": "http://localhost:8787",
  "auth_profile": "local",
  "tenant_id": null,
  "pinned_at": "2026-05-14T00:00:00Z",
  "pin_class": "local_dev_non_authoritative"
}
```

The `local_dev_non_authoritative` pin:

- is valid only for local health/capability checks
- is never valid for protected operations
- must not be migrated into enterprise/cloud trust
- must be ignored by future protected-data gates unless a later reviewed design
  explicitly upgrades the trust model

`enterprise` later needs a stronger pin tuple before any probing or protected
operation:

- normalized origin
- TLS public-key or certificate fingerprint
- expected authorization issuer
- expected OAuth resource indicator
- tenant/deployment entitlement claim
- signed capabilities key or equivalent deployment identity

That stronger tuple is out of scope for CS1-CS3; therefore enterprise profile
writes and probes are disabled.

Initial local slice behavior:

- `knudgctl config set-server --profile local --server-url http://localhost:8787`
  writes the URL but does not claim the server is trusted.
- `knudgctl server capabilities --pin` stores the server identity and digest
  only after the server returns a valid capabilities document and the operator
  passes `--allow-insecure-loopback`.
- `knudgctl server status` reports `unpinned` when a custom server is configured
  but not pinned.

Pin changes are explicit. If a server returns a different `server_id`, resource
URI, deployment type, API version, or capabilities digest than the pinned value,
the client reports `server_pin_mismatch` and exits unavailable until the
operator repins. Since local pins are non-authoritative, this is a local
dogfood safety check, not an enterprise trust ceremony.

`cloud` later needs a built-in pinned HTTPS trust tuple before any OAuth
protected operation:

- normalized cloud origin
- expected OAuth resource indicator
- expected protected resource metadata origin
- expected authorization issuer allowlist
- TLS certificate/public-key validation through the platform trust store

Capabilities digest:

- algorithm: SHA-256 over canonical JSON encoded as UTF-8
- canonical JSON: sorted object keys, no insignificant whitespace, unchanged
  string values
- included fields: `schema_version`, `server_id`, `deployment_type`,
  `api_version`, `features`, `policy_versions`, and `auth`
- excluded fields: no dynamic fields are allowed in CS1-CS3; if a future field
  is dynamic, it must be excluded explicitly in a schema revision
- unknown feature keys are included in the digest but ignored for client
  enablement

Capabilities cache:

- CS1-CS3 store only the last pinned capabilities document and digest
- cache is informational for `config show`
- commands that need capabilities must fetch live capabilities
- any URL/profile/env override invalidates the cache for the effective command

## Health And Capabilities Contract

Client probe endpoints:

```text
GET /health/live
GET /health/startup
GET /health/ready
GET /capabilities
```

`/healthz` is allowed only as a compatibility alias for `/health/ready`; clients
must not prefer it.

`/health/live` response:

```json
{
  "status": "ok"
}
```

`/health/startup` response:

```json
{
  "status": "ok"
}
```

`/health/ready` response:

```json
{
  "status": "ok",
  "deployment_type": "local",
  "server_id": "local-dev",
  "api_version": "v1",
  "degraded_mode": "none",
  "components": {
    "postgres": "ready",
    "migration": "ready",
    "auth_policy": "disabled",
    "revocation_epoch": "ready",
    "active_index_manifest": "disabled"
  },
  "route_classes": {
    "search": "disabled",
    "card-read": "synthetic_only",
    "submit/write": "synthetic_only",
    "trusted-consent-revocation": "disabled",
    "reviewer-admin": "disabled",
    "worker-lane": "synthetic_only",
    "landing": "disabled"
  }
}
```

CS1-CS3 use a `local_synthetic` readiness profile. In that profile:

- `auth_policy: disabled` is acceptable only because every protected route is
  `disabled` or `synthetic_only`
- `active_index_manifest: disabled` is acceptable only because `search` is
  `disabled`
- `card-read`, `submit/write`, and `worker-lane` are `synthetic_only`; they do
  not claim production central-service readiness
- any component state other than `ready` or allowed `disabled` makes
  `server status` return `unavailable`

`/health/dependencies` is an authenticated operator endpoint in the operations
architecture. It is not called by CS1-CS3 because this slice has no operator
auth.

`/capabilities` response:

```json
{
  "schema_version": 1,
  "server_id": "local-dev",
  "deployment_type": "local",
  "api_version": "v1",
  "features": {
    "private_writer_flow": true,
    "protected_retrieval": false,
    "public_publication": false,
    "mcp_streamable_http": false
  },
  "policy_versions": {
    "private_retention": "private-retention-v1"
  },
  "auth": {
    "profile": "local",
    "protected_resource_metadata_url": null,
    "capability_resource_origin": "http://localhost:8787"
  }
}
```

Client validation:

- response must be a JSON object
- `schema_version` must be `1`
- `deployment_type` must match the selected profile expectations
- `api_version` must be supported
- unknown feature keys are allowed but ignored
- known disabled features must remain disabled client-side
- missing required fields fail closed
- `auth.capability_resource_origin` must equal the normalized server URL for
  `local`
- `protected_resource_metadata_url` must be null in CS1-CS3
- local route states must be one of `synthetic_only`, `disabled`, or
  `ready`; `ready` is reserved for non-card infrastructure checks in CS1-CS3

Capabilities validation types:

- `schema_version`: integer, exactly `1`
- `server_id`: non-empty ASCII string up to 128 chars, pattern
  `^[A-Za-z0-9._:-]+$`
- `deployment_type`: exactly `local`
- `api_version`: exactly `v1`
- `features`: object with boolean values; known keys are
  `private_writer_flow`, `protected_retrieval`, `public_publication`,
  `mcp_streamable_http`
- `policy_versions`: object with string values; unknown keys allowed
- `auth`: object with `profile`, `protected_resource_metadata_url`, and
  `capability_resource_origin`
- invalid type, missing key, or mismatched value returns
  `status=capabilities_invalid`, `exit_code=4`

Probe HTTP policy:

- local loopback only
- no redirects
- no proxy use
- no credentials forwarded
- timeout: 2 seconds
- maximum response body: 64 KiB
- `/capabilities` must return JSON object content
- any non-loopback DNS/IP target is rejected before network I/O
- for `localhost`, resolve all A/AAAA answers, reject the probe if any answer
  is non-loopback, and connect to a validated loopback address instead of
  allowing a second resolver pass
- accepted IP literals are parsed with `ipaddress.ip_address` and must be
  loopback
- use `http.client.HTTPConnection` directly, not `urllib.request`, so proxy
  environment variables are not consulted
- tests set `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` and prove
  probes still connect directly to loopback

## CLI Surface

Add or update `knudgctl` commands:

```text
knudgctl config show
knudgctl config set-server --profile local --server-url <url> [--auth-profile local]
knudgctl config use-profile local
knudgctl server status [--server-url <loopback-url>]
knudgctl server capabilities [--server-url <loopback-url>] [--pin] [--allow-insecure-loopback]
```

CS1-CS3 CLI grammar:

- `config show [--profile <profile>] [--config <path>]`
- `config set-server --profile <local|cloud|enterprise> --server-url <url> [--auth-profile <profile>] [--config <path>]`
- `config use-profile local [--config <path>]`
- `server status [--profile <local|cloud|enterprise>] [--server-url <loopback-url>] [--config <path>]`
- `server capabilities [--profile <local|cloud|enterprise>] [--server-url <loopback-url>] [--pin] [--allow-insecure-loopback] [--config <path>]`

Cloud and enterprise profile values are parsed, then rejected as
`not_configured` with exit code `2`. They are not argparse usage errors. This
keeps the future command shape stable while preventing accidental enablement.

`--tenant` is rejected in CS1-CS3. Local tenant binding is deferred until a
trusted local auth design exists.

`server_url` CLI overrides are accepted only when the effective profile is
`local` and the URL is loopback. Environment server URL overrides are ignored
for `mcp-once` and other agent-wrapper contexts unless a later reviewed design
adds an explicit wrapper flag.

Caller-context override matrix:

| Caller context | Honors `KNUDG_CONFIG` | Honors `KNUDG_SERVER_URL` | Honors `KNUDG_AUTH_PROFILE` | Honors `KNUDG_TENANT_ID` |
|---|---|---|---|---|
| `cli` | yes | yes, local loopback only | yes, local only | no |
| `mcp_once` | no | no | no | no |
| `agent_wrapper` | no | no | no | no |

Output stays JSON. Sensitive values are never echoed except normalized server
URL and profile names in local CLI output. MCP tool content and public
abstention responses must not echo server URLs, internal hostnames, tenant
slugs, or probe errors.

Command contract:

| Command | Success | Not configured | Usage error | Unavailable | Notes |
|---|---:|---:|---:|---:|---|
| `config show` | `0 ok` | n/a | `3 usage_error` | n/a | no network |
| `config set-server` | `0 ok` | `2 not_configured` | `3 usage_error` | n/a | atomic write for local only |
| `config use-profile` | `0 ok` | n/a | `3 usage_error` | n/a | no network |
| `server status` | `0 ok` | `2 not_configured` | `3 usage_error` | `4 unavailable` | probes `/health/startup` then `/health/ready` |
| `server capabilities` | `0 ok` | `2 not_configured` | `3 usage_error` | `4 unavailable` | validates live capabilities |
| `server capabilities --pin` | `0 ok` | `2 not_configured` | `3 usage_error` | `4 unavailable` | requires `--allow-insecure-loopback` |

Reachable but unpinned local server:

- command `status`: `ok`
- exit code: `0`
- `pin_state`: `unpinned`

Reachable local server with env/CLI override:

- command `status`: `ok`
- exit code: `0`
- `pin_state`: `override_unpinned`

Pin mismatch:

- command `server capabilities`: `server_pin_mismatch`
- exit code: `4`
- `pin_state`: `mismatch`

`server status` does not fetch `/capabilities`; it can report URL/server
identity mismatch only when visible in `/health/ready`. Capability digest
mismatch is detected by `server capabilities`.

Non-pinning `server capabilities` may probe HTTP loopback without
`--allow-insecure-loopback`. The flag is required only when writing a local
dev-only pin with `--pin`.

Every output includes:

- `command`
- `status`
- `ok`
- `exit_code`
- `profile`
- `server_url`
- `pin_state`
- `request_id`
- `correlation_id`

`request_id` is a per-command invocation ID. `correlation_id` is a local
diagnostic grouping ID. This local slice does not write server-side audit
events and is not a production runbook transcript; `trace_id` and `span_id`
remain future operator telemetry fields.

Expected local behavior before a real server exists:

- `config show` returns the active profile and normalized server URL
- `server status` tries `/health/startup` and `/health/ready` and returns
  `unavailable` if no server is running
- `server capabilities` tries `/capabilities` and returns `unavailable` if no
  server is running

## Retrieval And MCP Skeleton Integration

The retrieval skeleton remains abstention-only and is not the protected HTTP
MCP route.

Changes:

- do not import `knudg_client_config.py` in CS1-CS3
- do not read `KNUDG_SERVER_URL` in `mcp-once`
- do not add server metadata to public search output
- private `search-similar` may accept `--local-config-metadata` later, but this
  is deferred until after the `knudgctl` config/probe surface lands
- do not call protected retrieval endpoints
- do not enable protected-data serving based on config alone

MCP skeleton:

- `tools/list` can remain static
- `tools/call search_similar` still returns `no_suggestion`
- `mcp-once tools/call search_similar` continues to return the existing
  abstention payload with no server-derived fields in tool content
- `mcp-once` must not respond to JSON-RPC notifications without `id`
- `mcp-once tools/list` must advertise an input schema consistent with runtime
  validation, not `additionalProperties: true`
- protected HTTP MCP, transport-level `401`, OAuth protected resource metadata,
  and `WWW-Authenticate` behavior are out of scope for CS1-CS3 and remain M5+

## Failure Modes

- Invalid URL: usage error.
- Server unavailable: unavailable, no fallback to another custom server.
- Enterprise/cloud custom server write or probe: not_configured.
- Unpinned custom server: status reports `unpinned`; protected operations are
  disabled.
- Override changes effective server/auth/tenant: status reports
  `override_unpinned`; protected operations are disabled and capability cache is
  ignored.
- Pin mismatch: unavailable with `server_pin_mismatch`.
- Unsupported API version: unavailable with `unsupported_api_version`.
- Missing capabilities: unavailable with `capabilities_invalid`.
- Feature disabled: command returns `not_configured` or abstains, depending on
  the command family.

## Acceptance Criteria

AC-CS-001: `knudgctl config set-server` validates and atomically writes a local
config for loopback `http` URLs.

AC-CS-002: `knudgctl config show` reports active profile, server URL, auth
profile, tenant setting presence, pin state, and whether a capabilities cache
exists without printing credentials.

AC-CS-003: invalid server URLs are rejected with `usage_error`.

AC-CS-004: `knudgctl server status` calls `/health/startup` and
`/health/ready`, handles unavailable servers, and returns JSON with stable exit
codes.

AC-CS-005: `knudgctl server capabilities` validates the capabilities document
and can pin a local server identity/digest.

AC-CS-006: pinned custom servers fail closed on server URL, `server_id`,
deployment type, API version, resource, or capability digest mismatch.

AC-CS-007: retrieval/MCP skeleton output remains abstention-only and does not
enable protected-data retrieval merely because a server URL is configured.

AC-CS-008: config tests prove no token/private key/card body fields are written.

AC-CS-009: env/CLI URL overrides report `override_unpinned`, do not mutate the
stored profile, do not use cached capabilities, and cannot enable protected
operations.

AC-CS-010: public search and MCP tool content do not leak server URL, profile,
tenant, internal hostname, or probe error details.

AC-CS-011: enterprise/cloud custom server writes and probes return
`not_configured` in CS1-CS3.

AC-CS-012: probe tests cover no redirects, response byte caps, timeout handling,
JSON content requirement for capabilities, and rejection before network I/O for
non-loopback targets.

AC-CS-013: `mcp-once` ignores `KNUDG_SERVER_URL`, emits no response for JSON-RPC
notifications, and advertises a tool schema consistent with runtime profile
validation.

## Implementation Slice Plan

Slice CS1:

- add `scripts/knudg_client_config.py`
- add `knudgctl config ...` commands
- add config unit tests

Module API:

- `load_config(path: Path | None, env: Mapping[str, str]) -> ClientConfig`
- `save_config(config: ClientConfig, path: Path) -> None`
- `normalize_server_url(url: str, profile: str) -> str`
- `effective_profile(config: ClientConfig, env: Mapping[str, str], overrides: Mapping[str, str], caller_context: Literal["cli", "mcp_once", "agent_wrapper"] = "cli") -> EffectiveProfile`
- `validate_no_secret_fields(config: Mapping[str, object]) -> None`
- `canonical_capabilities_digest(capabilities: Mapping[str, object]) -> str`
- `probe_json(origin: str, path: Literal["/health/live", "/health/startup", "/health/ready", "/capabilities"], *, timeout_seconds: float = 2.0, max_bytes: int = 65536) -> Mapping[str, object]`

Implementation primitives:

- URL parsing uses `urllib.parse.urlsplit`.
- JSON canonicalization uses `json.dumps(value, sort_keys=True,
  separators=(',', ':'), ensure_ascii=False)`.
- Atomic writes use `os.replace`.
- Network probes use `http.client.HTTPConnection` with explicit host/port,
  no redirect handling, no proxy lookup, a 2 second timeout, and a 64 KiB body
  cap.
- `probe_json` rejects paths outside the literal allowlist, absolute-form URLs,
  authority-form paths, CR/LF, and values not starting with `/`.

Parser and handler mapping:

| CLI branch | Handler |
|---|---|
| `config show` | `config_show(args)` |
| `config set-server` | `config_set_server(args)` |
| `config use-profile` | `config_use_profile(args)` |
| `server status` | `server_status(args)` |
| `server capabilities` | `server_capabilities(args)` |

These handlers live in `scripts/knudgctl.py` and delegate config parsing,
normalization, effective profile resolution, digesting, and probing to
`scripts/knudg_client_config.py`.

URL test vectors:

- accepted local: `http://localhost:8787`,
  `http://127.0.0.1:8787`, `http://[::1]:8787`
- rejected local: `https://localhost:8787`,
  `http://localhost:8787/path`, `http://localhost.evil.com:8787`,
  `http://0177.0.0.1:8787`, `http://127.0.0.1.:8787`,
  `http://user@localhost:8787`, `http://localhost:8787/#fragment`
- rejected cloud/enterprise writes in CS1-CS3:
  any custom URL

Forbidden persisted key names are checked recursively using lowercase substring
matching for: `token`, `refresh`, `secret`, `private_key`, `card_body`,
`payload_json`, `approval_artifact`, `raw_log`, and `credential`.

Slice CS2:

- add `/health/ready` and `/capabilities` probe commands to `knudgctl`
- add local HTTP test server fixtures
- add pinning and mismatch tests

Slice CS3:

- keep retrieval skeleton behavior unchanged
- add tests proving `mcp-once` ignores `KNUDG_SERVER_URL`
- add tests proving public search and MCP tool content do not include server
  URL/profile/tenant/probe metadata
- fix JSON-RPC notification handling and MCP tool schema/runtime mismatch while
  preserving abstention-only behavior

## Use-Ready Definition

After CS1-CS3, a developer can point Knudg tooling at a local server URL, verify
server health/capabilities, pin the local server, and see retrieval/MCP remain
fail-closed until actual serving gates are implemented.

This is local dogfood ready, not production ready.
