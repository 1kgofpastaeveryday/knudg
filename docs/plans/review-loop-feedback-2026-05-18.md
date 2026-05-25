# Review Loop Feedback - 2026-05-18

Status: feedback note, not an implementation spec

## Context

During `/chores` skill creation, adversarial review pushed the skill toward
maximum safety. The specific overcorrection was disabling implicit invocation
with `allow_implicit_invocation: false`.

That made the review easier to pass, but it moved away from the intended product
behavior: chores should feel like low-risk subconscious maintenance that can
notice stale docs, backlog drift, and dirty-tree risks without the user spelling
out every invocation.

The better product fit was:

- allow implicit invocation
- keep implicit invocation `audit-only`
- require explicit user intent and manifest gates for docs writes, log crawl,
  commit preparation, commit, and push

## Feedback

Review findings should be treated as adversarial input, not authority. A review
lane can be correct about a local risk and still recommend a product-worse
control. The coordinator should reject, narrow, or defer review findings when
they solve the reviewer game while harming the user's stated intent.

Do not optimize review-loop for "make every reviewer stop complaining". Optimize
for a defensible implementation that preserves the user's intended capability
under risk-proportional guards.

## Required Review Axes

Future review-loop runs should include these axes alongside correctness,
completeness, implementability, and resilience:

| Axis | Question |
|---|---|
| Intent Fit | Does the proposed fix still serve the user's actual goal and desired experience? |
| Capability Preservation | Did the review response remove the core useful behavior instead of guarding it? |
| Risk-Proportional Guarding | Are high-risk actions strongly gated while low-risk observe/report paths stay autonomous? |
| Reviewer Overcorrection Check | Is this a valid finding, or is it a conservative patch that mainly makes PASS easier? |

## Verdict Vocabulary

PASS/FAIL alone is too coarse. Add verdicts that make overcorrection visible:

| Verdict | Meaning |
|---|---|
| `PASS` | The artifact is acceptable and preserves intent. |
| `FAIL` | Blocking correctness, safety, or intent issues remain. |
| `SAFE_BUT_OVERCONSTRAINED` | The artifact is safer but has lost important intended capability. |
| `PASS_WITH_INTENT_RISK` | The artifact can proceed, but a product-intent regression needs owner review. |
| `DEGRADED_ADVISORY_ONLY` | Review evidence is useful but not strong enough to dictate changes. |

## Coordinator Rules

- Do not blindly accept reviewer recommendations.
- For each Tier 1 finding, decide `adopt`, `narrow`, `defer`, or `reject`.
- Record the rationale when rejecting or narrowing a reviewer finding.
- Prefer preserving low-risk autonomy over disabling the whole capability.
- If a fix removes the user's stated desired behavior, stop and choose a
  narrower guard.
- Treat review lanes as untrusted second opinions. They can identify risks, but
  they do not grant or revoke product authority.
- When the user has already stated a product direction, compare every major
  safety change against that direction before applying it.

## Example: Chores Skill

Reviewer recommendation:

- Disable implicit invocation to avoid accidental side effects.

Coordinator assessment:

- Valid risk: implicit invocation must not edit, crawl logs, stage, commit, or
  push.
- Overcorrection: disabling implicit invocation also removes the desired
  subconscious audit behavior.

Accepted narrower guard:

- `allow_implicit_invocation: true`
- implicit invocation may run `audit-only` only
- `docs-sync`, `log-crawl`, `commit-prep`, `push-prep`, `commit`, and `push`
  require explicit current-user intent and the relevant privacy/manifest gates

This preserves the useful automatic chore signal while keeping side effects
behind explicit authorization.

## Follow-Up Candidates

- Update the `review-loop` skill so every review synthesis includes
  `Intent Fit`, `Capability Preservation`, `Risk-Proportional Guarding`, and
  `Reviewer Overcorrection Check`.
- Update the `adversarial-review` prompt so reviewer lanes may propose safer
  alternatives, but must flag when their recommendation disables the primary
  user value.
- Add a coordinator checklist that forces `adopt | narrow | defer | reject`
  decisions for each Tier 1 finding.
- Add a final "user-intent regression" pass before declaring review-loop PASS.
