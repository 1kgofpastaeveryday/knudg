# Synthetic Retrieval Harness

Status: local synthetic helper, no protected/public corpus search

`scripts/knudg_synthetic_retrieval.py` searches a caller-provided synthetic
corpus using an exact/FTS-style token match. It is a local dogfood bridge
between writer drafts and the future crawler path.

For a complete local synthetic path from writer draft to loopback server
retrieval, see
[Local Synthetic Dogfood Runbook](local-synthetic-dogfood-runbook.md).

It does not:

- query product tables
- read workspace files as corpus data
- search protected, team, or public Knudg data
- use vector search, reranking, or public privacy thresholds
- return executable card bodies

## Command

```powershell
npm run retrieval:synthetic -- search --input path\to\request.json --corpus path\to\corpus.json
```

Build a synthetic corpus from one or more synthetic card payloads:

```powershell
npm run retrieval:synthetic -- build-corpus --payload path\to\card-payload.json
```

`build-corpus` also accepts the default `writer:draft` JSON result shape and
extracts its `payload` field when `status` is `local_draft_only`.

The local dev server exposes the same synthetic-only harness over loopback:

```text
POST /v1/synthetic-retrieval/search
```

Body:

```json
{
  "request": {},
  "corpus": {},
  "min_score": 2
}
```

The endpoint does not read corpus files from disk and does not query product
tables. The caller must provide both the sanitized synthetic request and the
synthetic corpus object in the JSON body.

With a configured local dev server, `knudgctl` can call the endpoint:

```powershell
npm run knudgctl -- server synthetic-search --input path\to\request.json --corpus path\to\corpus.json
```

This is still a synthetic-only dogfood route. The CLI wraps the response and
keeps `protected_data_serving_enabled` and `publication_enabled` false.

## Request Shape

```json
{
  "schema_version": "synthetic-retrieval-v0",
  "request_id": "retrieval_req_000001",
  "auth_context": {
    "tenant_id": "tenant_local",
    "namespace_ids": ["ns_local"],
    "revocation_epoch": 0
  },
  "search_profile": {
    "schema_version": "search-profile-v0",
    "request_id": "profile_req_000001",
    "tenant_scope": "private",
    "namespace_ids": ["ns_local"],
    "delivery_mode_requested": "retrieval_panel",
    "goal_category": "local server setup",
    "sanitized_error_signature": "server url missing",
    "public_packages_claimed": ["knudgctl"],
    "public_frameworks_tools_claimed": ["Codex"],
    "language_runtime": "python-3.12",
    "coarse_os": "windows",
    "dependency_major_versions": [],
    "repo_shape_category": "python-node-local-plugin",
    "risk_flags_claimed": [],
    "latency_budget_ms": 250,
    "privacy_budget_class_claimed": "private_team"
  }
}
```

## Corpus Shape

```json
{
  "schema_version": "synthetic-corpus-v0",
  "cards": [
    {
      "tenant_id": "tenant_local",
      "namespace_id": "ns_local",
      "card_id": "card_001",
      "card_version_id": "version_001",
      "status": "approved_private",
      "source_class": "synthetic",
      "payload": {}
    }
  ],
  "revocation_tombstones": []
}
```

`payload` must be a valid `card-payload-v1` object. The harness authorizes by
tenant and namespace before scoring, excludes non-searchable lifecycle states,
and applies card/card-version/namespace/tenant tombstones before returning
metadata.

Returned cards are retrieval-panel metadata only. They include the goal,
symptom, quality, outcome, safety, freshness, provenance, and matched terms.
They do not include `successful_path`, raw commands, raw logs, full card bodies,
or private source data.

The response must validate against
`schemas/retrieval-panel-v0.schema.json`.

## Corpus Builder Boundary

`build-corpus` accepts only valid `card-payload-v1` payloads whose `privacy` and
`provenance` source classes are both `synthetic`. It assigns deterministic
opaque card IDs such as `card_001` and `version_001`; callers can set the
synthetic tenant and namespace IDs for fixture alignment. It does not preserve
writer request IDs as card IDs and does not enable protected-data storage.
