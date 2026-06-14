# Trust Model

This is the conceptual spine of Knudg. Read it before the detailed retrieval,
data-model, and security docs. Those documents specify *how* each gate works;
this one explains *why the system does not rot*.

## The Invariant

**Knudg never trusts stored knowledge. Every card carries a trust state that
must be earned, can be demoted, and is re-verified at the point of use. When
trust is low, retrieval abstains instead of polluting the acting agent.**

Everything else — schemas, ranking, lifecycle states, injection contracts — is
machinery in service of that one sentence.

## The Problem It Answers

The obvious way to give an agent memory is to dump prior sessions into a store
and feed them back. That store works until it doesn't:

- A fix that was correct last quarter is now wrong (dependency moved, API
  changed). The store keeps serving it.
- Two sessions reached contradictory conclusions. The store flattens one.
- A path that worked in one environment is replayed blindly in another.
- The agent treats retrieved text as instruction, so a stale or hostile note
  becomes an action.

This is why memory and hand-curated markdown handoffs decay: **they trust their
own contents unconditionally.** Accumulated knowledge silently crosses from
asset to liability, and the system has no structural way to notice.

Knudg's answer is not "store more carefully." It is "never trust the store."

## The Three Structural Mechanisms

### 1. Trust is a first-class, reversible property of every card

A card does not enter the corpus as truth. It enters as `unreviewed` and climbs
only by earning evidence:

```text
unreviewed  ->  solved_once  ->  solved_many  ->  verified
```

- `solved_many` requires evidence strength of `multi_session`, `reproduced`, or
  `external_reference`.
- `verified` requires `reproduced`/`external_reference` evidence **and** a
  linked verification record (reviewer, activity, environment, I/O evidence,
  version bounds, remaining risk).

Climbing is not one-way. The same property can fall:

- `disputed` — a contradicting result demotes the card (requires a `contradicts`
  edge or dispute event); the conflict is **kept**, not silently resolved.
- `deprecated` / `superseded` — a newer card explicitly retires an older path.
- `revoked` — removed from serving entirely; never returned.

Contradictory fixes are linked with `contradicts`, never merged. A minority
environment variant is preserved as a `variant_of`, never discarded because the
majority path works elsewhere. The store is allowed to hold disagreement,
because disagreement is information.

Failed and unknown experience are first-class, not second-class:
`outcome_type` of `failed_only`, `inconclusive`, and `unknown_clarified` get
their own embeddings, fingerprints, provenance, and scoring. Knudg preserves
*experience*, not just recipes.

### 2. Retrieval demotes and abstains — it does not "return the top 3"

Trust state is not decoration; it drives serving:

- `deprecated`, `superseded`, and `disputed` cards are demoted in ranking and
  surface only when explicitly requested or as provenance for a replacement.
- `revoked` cards are never returned.
- Low-confidence queries return **no card**. The target is "return up to 3 cards
  only when confidence clears the threshold," not "always return the best
  match." Abstention is a correct, expected result.
- `stale or harmful suggestion rate` is a measured quality gate, not an
  afterthought — the asset/liability boundary is something Knudg is built to
  observe.

### 3. Use re-verifies, and the result feeds back

Retrieved cards are **untrusted evidence, rendered as non-executable data.**
They are hints for the acting agent, never commands, and never sit above
system, user, tool, or safety policy.

This closes the loop that memory leaves open. The agent verifies a candidate
path *in the current environment* before relying on it. That verification is
itself new experience: it can promote a card toward `verified`, demote it to
`disputed`, or supersede it. **The corpus is corrected by use, not just by
moderation.** This is the update mechanism — knowledge stays current because
every retrieval is also a re-test.

## Why This Beats a Memory Dump

| | Memory / MD handoff | Knudg |
|---|---|---|
| Default trust | Unconditional | None; trust is earned |
| Stale knowledge | Served as-is | Demoted / superseded / revoked |
| Contradictions | Flattened | Preserved as `contradicts` |
| Environment fit | Implicit | `context_fingerprint` + variants |
| Low confidence | Still answers | Abstains |
| Retrieved text | Often treated as instruction | Untrusted evidence, verified at use |
| Correction path | Manual edit | Use re-verifies and writes back |

A memory dump optimizes for recall. Knudg optimizes for **not being wrong on
the agent's behalf** — and accepts returning nothing as the price.

## Where the Machinery Lives

This spine is implemented across the detailed docs. When you need the exact
gate, follow the pointer:

- Trust states, outcome semantics, contradiction/variant links, lifecycle:
  [Data Model](data-model.md)
- Ranking, demotion, abstention thresholds, injection contract, quality gates:
  [Retrieval Model](retrieval.md)
- Untrusted-evidence rendering, hostile-card handling, redaction boundaries:
  [Security and Privacy](security-privacy.md)
- How a card is admitted, reviewed, and compacted without becoming new ground
  truth: [Architecture Overview](overview.md)
