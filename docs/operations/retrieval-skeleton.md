# Retrieval/API/MCP Abstention Skeleton

Status: local contract skeleton, retrieval backend disabled

`scripts/knudg_retrieval.py` is a non-ingesting skeleton for the future
retrieval/API/MCP access paths. It validates bounded request shapes and returns
`no_suggestion` until a later milestone configures authenticated serving,
ranking, indexes, and token verification.

The skeleton exists to lock down the contract boundary early:

- private/team `SearchProfile` inputs must be sanitized profiles, not raw logs
  or transcripts
- public search rejects tenant, namespace, object, and fingerprint selectors
- MCP `tools/list` and `tools/call` use JSON-RPC 2.0 envelopes
- no command queries protected product tables or returns card candidates
- default behavior is abstention, not best-effort retrieval

## Commands

Private/team skeleton search:

```powershell
npm run retrieval:skeleton -- search-similar --input path\to\search-profile.json
```

Public skeleton search:

```powershell
npm run retrieval:skeleton -- public-search --input path\to\public-search.json
```

Single MCP JSON-RPC request:

```powershell
npm run retrieval:skeleton -- mcp-once --input path\to\mcp-request.json
```

The MCP shape follows the current MCP base requirement that messages use
JSON-RPC 2.0. The skeleton intentionally implements only `tools/list` and a
stubbed `tools/call` for `search_similar`.

## Disabled Until Later Milestones

This skeleton does not implement:

- delegated-token validation
- tenant membership or namespace authorization
- exact/FTS/vector candidate generation
- ranking, reranking, thresholds, or privacy budgets
- `get_card`, `submit_candidate`, approval, revocation, or harmful-card reports
- public search over any corpus

Those remain blocked by the architecture gates in `agent-access.md` and
`retrieval.md`.
