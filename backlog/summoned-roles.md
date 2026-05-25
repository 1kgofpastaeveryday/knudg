# Summoned Role Backlog

Summoned roles are the MVP path for writer/searcher/nudger before a fully
automatic hook or `agent-subconscious` adapter exists. The main agent can start
these roles in parallel with active work, but the roles return compact
verdicts only.

## SR-001: Role Verdict Schema

Status: done

Goal:

Define the closed JSON schema for `knudg_role_verdict.v0`.

Acceptance:

- Supports `searcher`, `writer`, `nudger`, and `reviewer`.
- Supports `abstain`, `suggestion_available`, `draft_candidate_possible`,
  `approval_handoff_possible`, and `degraded`.
- Supports only bounded recommended actions:
  `do_nothing`, `offer_retrieval_panel`, `offer_writer_draft`,
  `offer_approval_handoff`, and `ask_user_before_continuing`.
- Allows opaque refs but rejects raw card bodies, command text, package install
  lines, full stack traces, absolute paths, secrets, tokens, raw transcripts,
  and private repo names.
- Adds schema tests with negative fixtures for prompt-injection-like text and
  executable suggestions.

Suggested files:

- `schemas/knudg-role-verdict-v0.schema.json`
- `tests/test_knudg_role_verdict_schema.py`

Evidence:

- `schemas/knudg-role-verdict-v0.schema.json`
- `scripts/knudg_roles.py`
- `tests/test_knudg_role_verdict.py`
- `python -m pytest tests/test_knudg_role_verdict.py`

## SR-002: Local Searcher Role Wrapper

Status: done

Goal:

Wrap the existing synthetic retrieval harness in a summoned searcher role that
returns a compact verdict before any retrieval-panel display.

Acceptance:

- Accepts only a sanitized synthetic/local `SearchProfile` equivalent.
- Calls the synthetic retrieval path or abstains.
- Returns `offer_retrieval_panel` only when the harness returns displayable
  retrieval-panel metadata.
- Returns `abstain` or `degraded` without blocking the main task when retrieval
  is unavailable.
- Does not expose card bodies or executable card content in the verdict.

Evidence:

- `scripts/knudg_roles.py searcher-synthetic`
- `tests/test_knudg_role_verdict.py`

## SR-003: Local Writer Role Wrapper

Status: done

Goal:

Wrap local synthetic writer draft generation as a summoned writer role.

Acceptance:

- Consumes a bounded outcome summary, not a raw transcript.
- Can return `draft_candidate_possible` with an opaque draft ref or local
  synthetic draft metadata.
- Cannot persist non-synthetic body data.
- Cannot complete private retention, publication consent, or revocation.
- Reuses the existing `writer:draft` payload/digest path where possible.

Evidence:

- `scripts/knudg_roles.py writer-local`
- `tests/test_knudg_role_verdict.py`

## SR-004: Nudger Policy

Status: done

Goal:

Define the low-noise policy for when Knudg should interrupt the main agent with
a suggestion.

Acceptance:

- Default decision is `abstain`.
- Nudges can only recommend offering a retrieval panel, writer draft, approval
  handoff, or user question.
- Nudges cannot recommend tool execution, file edits, package installs, or
  technical fixes.
- Adds tests or fixtures proving low-confidence, high-risk, stale, unsafe, or
  raw/private suggestions abstain.

Evidence:

- `scripts/knudg_roles.py nudger-from-verdict`
- `tests/test_knudg_role_verdict.py`

## SR-005: Optional Subconscious Adapter Boundary

Status: deferred

Goal:

Document how a future `agent-subconscious` observer could emit the same role
contracts without becoming Knudg's canonical store.

Acceptance:

- Treats subconscious as an optional candidate/event source only.
- Does not depend on active notes, hooks, or local memory lifecycle.
- Routes all candidate writes through the same intake, consent, approval,
  revocation, and publication gates.
- Preserves the ability to run writer/searcher/nudger without subconscious.

## SR-006: Composed Role Dogfood Commands

Status: done

Goal:

Make the local synthetic role loop usable with one command per main-agent offer.

Acceptance:

- Add `searcher-nudge-synthetic` to run synthetic searcher and nudger in one
  process.
- Add `writer-nudge-local` to run local writer and nudger in one process.
- Return only the final compact nudger verdict.
- Preserve the existing raw/private/executable rejection behavior.
- Add tests proving no card bodies, successful paths, command text, or raw input
  are exposed.

Evidence:

- `scripts/knudg_roles.py searcher-nudge-synthetic`
- `scripts/knudg_roles.py writer-nudge-local`
- `tests/test_knudg_role_verdict.py`

## SR-007: Plugin Entry Points For Roles

Status: done

Goal:

Expose the composed role commands through the local Knudg plugin/skill path for
actual Codex dogfood.

Acceptance:

- Document the allowed `npm run roles -- ...` invocations in the skill.
- Keep unsupported `knudgctl` groups blocked or handed off.
- Do not add hooks, background daemons, or automatic subconscious reads.

Evidence:

- `plugins/knudg/skills/knudg/SKILL.md`
- `tests/test_knudg_plugin_manifest.py`
- `python -m pytest tests/test_knudg_plugin_manifest.py tests/test_knudg_role_verdict.py`
