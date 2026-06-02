# Summoned Role MVP

Status: product design only; active implementation uses live backend
orchestration.

Knudg's first agent-native MVP should use summoned sub-agents, not a fully
automatic local sidecar or hook. The main agent begins the user's task normally
and may start bounded Knudg roles in parallel. Those roles return compact,
structured signals only. They do not write canonical state, execute tools for
the main task, or inject retrieved experience directly into the acting prompt.

This design protects the main agent's working context. Knudg should improve
agent judgment by isolating experience retrieval and candidate drafting, not by
filling the main prompt with historical material.

## Role Split

```text
user prompt
  -> main agent starts the task
  -> Knudg roles may be summoned in parallel
       searcher: build/search a sanitized profile and abstain by default
       writer: watch for a future reusable candidate and draft only after work
       nudger: decide whether a low-noise suggestion is worth surfacing
       reviewer: optionally evaluate retrieved evidence fit/risk
  -> main agent receives compact role verdicts
  -> main agent decides whether to open a retrieval panel or approval handoff
```

The main agent keeps:

- user intent interpretation
- task planning and execution
- file edits, tool use, and final response authority
- the decision to use, ignore, or inspect a Knudg suggestion

Knudg roles keep:

- current-work query profiling
- retrieval and abstention
- candidate-draft shaping
- nudge timing
- optional evidence fit/risk evaluation

## MVP Contract

Role outputs are suggestions, not instructions. They must be short, structured,
and bounded:

```json
{
  "schema_version": "knudg_role_verdict.v0",
  "role": "searcher",
  "status": "suggestion_available",
  "confidence": "medium",
  "risk": "low",
  "reason_summary": "Similar public package and error category.",
  "recommended_action": "offer_retrieval_panel",
  "card_refs": ["opaque-card-ref"]
}
```

Allowed `status` values:

- `abstain`
- `no_actionable_signal`
- `suggestion_available`
- `draft_candidate_possible`
- `approval_handoff_possible`
- `degraded`

Allowed `recommended_action` values:

- `do_nothing`
- `offer_retrieval_panel`
- `offer_writer_draft`
- `offer_approval_handoff`
- `ask_user_before_continuing`

The verdict must not contain raw card bodies, command text, package install
lines, private paths, full stack traces, secrets, tokens, raw transcripts,
private repo names, or arbitrary quoted prompt text. If useful detail would
violate that rule, the role returns an opaque reference and the main agent may
open a gated retrieval panel or trusted approval handoff.

## Searcher

The searcher consumes a sanitized `SearchProfile` or `task_profile.v0`
and returns one of:

- `abstain` when confidence, authorization, freshness, or safety is uncertain
- `no_actionable_signal` when search completed but found no useful signal for
  the current task
- compact candidate refs suitable for a retrieval panel
- `degraded` when the search backend, auth, or revocation fence is unavailable

The searcher must not deliver inline instructions to the main prompt. It may
recommend opening a retrieval panel. Full body expansion remains governed by
Agent Access and Retrieval Model policies.

## Writer

The writer observes only the bounded task summary and final outcome signals
provided to it. It may propose a structured draft candidate after a solved,
failed-only, inconclusive, or unknown-clarified case.

The writer cannot store non-synthetic bodies, approve retention, publish,
complete consent, or bypass intake gates. Its MVP output is at most:

- an opaque pending candidate reference
- an approval handoff suggestion for the main agent to present

Exact artifact preview and human approval are still required before private
retention, team sharing, or public publication.

## Nudger

The nudger is deliberately weak. It should optimize for low interruption cost
and may only suggest that the main agent offer a panel or draft. It must not
tell the main agent what technical action to take.

The nudger should return `abstain` when safety, authorization, or confidence is
uncertain, and `no_actionable_signal` when it searched but found nothing useful.
It should return `suggestion_available` only when all of these are true:

- the suggestion is relevant to the active task
- the confidence is high enough for the current rollout stage
- the suggestion can be expressed without raw/private content
- the user or main agent can ignore it without losing task progress

## Reviewer

A reviewer role may be summoned when a retrieved card has nontrivial fit or
safety risk. It consumes card metadata and the sanitized current-work profile,
then returns a verdict such as `fit_likely`, `fit_unclear`,
`safety_withheld`, or `stale`. It does not grant authority to execute a card's
contents.

## Relationship To Agent Subconscious

`agent-subconscious` is optional future plumbing, not a dependency for the MVP.
It may later become a local observer/event feed that emits the same role
contracts. The Knudg role APIs should not depend on its storage model, active
notes projection, hooks, or local memory lifecycle.

Rollout order:

1. manual summon by user or main agent
2. automatic per-task summon by the main agent
3. policy-based summon by workspace, task class, and measured usefulness
4. optional sidecar/subconscious adapter that emits the same verdicts
5. full hook/sidecar automation only after noise, privacy, and safety gates pass

If a later subconscious adapter is added, it remains a candidate source and
observer. Knudg keeps canonical schema, consent, approval, revocation, shared
storage, retrieval contracts, and publication gates.

## Guardrails

- Default to `abstain`.
- Keep role outputs outside the main prompt unless they are compact verdicts.
- Never treat retrieved cards as instruction hierarchy.
- Never auto-save, auto-publish, or auto-complete consent.
- Never require subconscious to ship writer/searcher/nudger.
- Preserve a no-Knudg baseline path: role failures must not block the main task.
- Measure usefulness against no-Knudg and against main-agent-only operation.

## Backend Handoff

Summoned roles are a product design for the agent-facing front door. They do
not replace the backend product core. The active implementation has skipped the
old local synthetic role loop and moved to live closed-launch orchestration.
Implementation should move in this order:

1. keep live profile/search/nudge/write-candidate commands bounded to the
   pinned closed-launch backend
2. keep retrieved evidence advisory and outside the acting prompt unless the
   main agent opens an allowed panel
3. wire M1 writer queue orchestration only after product intake and consent
   gates are accepted
4. implement M3 authorized exact/FTS retrieval and retrieval-panel response
   generation for product paths
5. build trusted human approval and revocation surfaces
6. open product-path non-synthetic protected-data flows only after auth, durability, intake,
   no-log ingress, consent, and launch-gate manifests pass

This keeps the current value loop usable while preserving the boundary between
thin agent orchestration and canonical Knudg storage/search/consent behavior.
