# Task Profile Builder

Status: local synthetic/searcher-side helper

`scripts/knudg_task_profile.py` builds a sanitized `task_profile.v0` from
explicit current-work metadata. It is a local helper for searcher-role dogfood;
it does not inspect arbitrary workspace files, raw transcripts, logs, private
notes, or source contents.

## Command

Build a profile:

```powershell
npm run task-profile -- build --input path\to\task-profile-input.json
```

Build a profile and include bounded query-view debug terms:

```powershell
npm run task-profile -- build --input path\to\task-profile-input.json --with-query-views
```

The default output is directly usable as `task_profile.v0` input for:

```powershell
npm run roles -- searcher-profile-nudge-synthetic --input path\to\task-profile.json --corpus path\to\corpus.json
```

## Input Shape

```json
{
  "schema_version": "task-profile-builder-input-v0",
  "intent": "debug",
  "explicit_query": "capture local server setup failure",
  "repo_shape_category": "python-node-local-plugin",
  "subsystems": ["local-dev-server"],
  "safe_file_refs": ["docs/operations/local-dev-server.md"],
  "symbols": ["knudgctl"],
  "error_fingerprints": ["server-url-missing"],
  "public_packages": ["pypi:jsonschema"],
  "public_frameworks_tools": ["Codex"],
  "language_runtime": "python-3.12",
  "coarse_os": "windows",
  "dependency_major_versions": ["pytest:9"],
  "risk_tags": ["correctness"],
  "recent_event_kinds": ["task_start"]
}
```

The builder validates the final output against
`schemas/task-profile-v0.schema.json`. It deduplicates explicit arrays and
omits empty optional fields.

## Safety Boundary

The builder rejects raw or private-looking input and returns only a generic
`input_rejected` result on failure. It must not echo absolute paths, URLs,
hostnames, usernames, secrets, tokens, command output, stack traces, or raw
source material in error output.
