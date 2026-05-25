# Local Writer Draft

Status: local synthetic helper, no product-table writes

`scripts/knudg_writer.py` creates a canonical `card-payload-v1` draft from a
bounded synthetic input shape. It is a local dogfood helper for the future
knowledge-writer path.

It does not:

- read raw transcripts or workspace files
- store private candidate metadata
- insert into Postgres
- create approval challenges or consent records
- enable public publication

For a complete local synthetic path from draft creation to retrieval-panel
output, see [Local Synthetic Dogfood Runbook](local-synthetic-dogfood-runbook.md).

## Command

```powershell
npm run writer:draft -- draft-card --input path\to\writer-draft.json
```

Print only the canonical payload:

```powershell
npm run writer:draft -- draft-card --input path\to\writer-draft.json --canonical
```

Print only the digest:

```powershell
npm run writer:draft -- draft-card --input path\to\writer-draft.json --digest
```

Inspect the local synthetic writer queue state:

```powershell
npm run knudgctl -- writer status --tenant <tenant_id>
```

Preview the next local writer actions without mutating queue or card state:

```powershell
npm run knudgctl -- writer reconcile --tenant <tenant_id> --dry-run
```

Plan or enqueue the next local writer worker jobs:

```powershell
npm run knudgctl -- writer enqueue-next --tenant <tenant_id> --dry-run
npm run knudgctl -- writer enqueue-next --tenant <tenant_id> --apply
```

Claim and run one queued local writer worker job:

```powershell
npm run knudgctl -- writer run-next --tenant <tenant_id> --dry-run
npm run knudgctl -- writer run-next --tenant <tenant_id> --apply
```

Sweep stuck local writer queue state:

```powershell
npm run knudgctl -- writer sweep --tenant <tenant_id> --dry-run
npm run knudgctl -- writer sweep --tenant <tenant_id> --apply
```

Create or inspect a human approval handoff placeholder after a card reaches
`awaiting_user_approval`:

```powershell
npm run knudgctl -- writer approval-handoff create --tenant <tenant_id> --card <card_id> --dry-run
npm run knudgctl -- writer approval-handoff create --tenant <tenant_id> --card <card_id> --apply
npm run knudgctl -- writer approval-handoff inspect --tenant <tenant_id> --handoff <handoff_id>
```

`writer status` and `writer reconcile --dry-run` expose only opaque IDs,
statuses, current-version digests, timestamps, and recommended next actions.
`writer enqueue-next` stores only an opaque worker-job payload containing IDs,
current-version identifiers, source status, operation name, worker role, and
disabled protected-data/publication flags. `writer run-next` claims exactly one
eligible job, dispatches only the local writer operations named in the queued
metadata, and completes or safely fails the job. `writer sweep` detects missing
next jobs, stale leases, duplicate active jobs, and expired private approval
challenges. Apply mode only enqueues missing metadata-only jobs and releases
expired leases back to `ready`. These commands do not print card bodies, raw
payload JSON, transcripts, command output, or private source material.
`approval-handoff` binds the handoff to the active private approval challenge,
card version digest, namespace, scope, and expiry. It cannot complete consent;
trusted human UI is still required for approval completion. `writer reconcile
--apply` remains disabled in this local slice.

## Input Shape

```json
{
  "schema_version": "writer-draft-v0",
  "request_id": "draft_req_000001",
  "source_class": "synthetic",
  "outcome_type": "solved",
  "goal": "capture a repeated local setup fix",
  "symptom": "local dev server was not configured",
  "environment": {
    "agent_tool": "Codex",
    "coarse_os": "windows"
  },
  "context_fingerprint": {
    "repo_shape": "python-node-local-plugin"
  },
  "successful_path": [
    "set the local profile server URL",
    "pin server capabilities"
  ],
  "failed_paths": [],
  "known_unknowns": [],
  "scope_limits": [
    "synthetic local dogfood only"
  ],
  "risk_flags": []
}
```

Allowed `outcome_type` values:

- `solved`
- `failed_only`
- `inconclusive`
- `unknown_clarified`

Allowed `risk_flags` values:

- `executable_advice`
- `mentions_urls`
- `mentions_packages`
- `mentions_repositories`
- `credential_risk`
- `billing_risk`
- `deletion_risk`
- `network_call_risk`

## Safety Boundary

The helper accepts only `source_class: "synthetic"`. Raw logs, stack traces,
absolute paths, usernames, hostnames, private repository names, customer names,
secrets, tokens, file contents, command output, transcripts, URLs, and private
repo URLs are rejected before card generation.
