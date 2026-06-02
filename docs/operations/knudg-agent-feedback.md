# Knudg Agent Feedback

Status: resolved into startup gate, role verdict, and skill guardrails

This document captures operator feedback from real Codex use. It is not a
product promise or implementation contract by itself; use it to guide future
Knudg agent-orchestration policy.

Resolution:

- `plugins/knudg/hooks/knudg_startup_gate.py` now skips small, reversible text
  edits in the Knudg workspace unless the prompt also indicates higher
  retrieval value.
- `plugins/knudg/skills/knudg/SKILL.md` now scopes startup retrieval to
  nontrivial technical work and calls out direct local editing for small text
  changes.
- `knudg_role_verdict.v0` now distinguishes `no_actionable_signal` from
  `suggestion_available`, and startup hook copy says references are not task
  progress unless validated and used.

## 2026-06-02: Avoid Knudg For Small Text Edits

Feedback:

- The agent used Knudg live nudge and native sub-agent startup for small landing
  page text and Markdown adjustments.
- The work was local, low-risk, and line-level: copy changes, information
  architecture wording, and documentation alignment.
- In that context, spawning Knudg sub-agents added overhead without materially
  improving the result.

Observed cost:

- extra token use
- extra latency
- noisy progress updates
- thread-slot pressure
- user confusion about why a retrieval tool was involved

Preferred behavior:

- Do not require Knudg live nudge for ordinary copy edits, Markdown cleanup,
  spelling/style tweaks, or single-document wording changes.
- Use direct local editing for small, reversible text changes.
- Reserve Knudg startup retrieval for tasks where prior work can plausibly
  change the approach: architecture decisions, deployment traps, test failures,
  cross-document policy alignment, nontrivial implementation, or recurring
  environment issues.

Decision implication:

- The "use Knudg at task start" rule should include a practical threshold.
- The threshold should consider risk and expected retrieval value, not only
  whether the workspace is the Knudg repository.

## 2026-06-02: Compact Verdict Is Not A Useful Artifact By Itself

Feedback:

- Native Knudg sub-agents successfully spawned and returned compact verdicts.
- The returned payload was only metadata such as `suggestion_available`,
  `offer_retrieval_panel`, confidence, risk, panel reference, and reference
  count.
- That payload did not include an actionable synthesis, implementation advice,
  or document-ready feedback.

Observed issue:

- From the user's point of view, a spawned sub-agent appeared to run, but it did
  not produce a useful work product.
- The result was technically successful but operationally weak for the task.
- Repeating this pattern makes Knudg feel like token spend without output.

Preferred behavior:

- If a native Knudg sub-agent is required, it should return one of two clear
  outcomes:
  - a genuinely actionable compact synthesis that can change the current task
  - an explicit `no_actionable_signal` result that says no useful retrieval was
    found
- `suggestion_available` alone should not be treated as task progress.
- The parent agent should not present a compact verdict as a meaningful
  contribution unless it actually affected the next step.

Decision implication:

- The live nudge protocol should distinguish "references exist" from "the
  references changed the recommended action."
- Agent UX should account for token efficiency and observable usefulness, not
  just backend retrieval success.

## Proposed Guardrail

For future agent behavior, use this default:

- Skip Knudg for small text edits unless the user explicitly asks for prior-work
  retrieval.
- Run Knudg for nontrivial implementation, debugging, deployment, security,
  policy, or cross-document consistency work.
- When Knudg runs, record whether its output changed the task plan. If it did
  not, say so briefly and avoid treating it as evidence.
