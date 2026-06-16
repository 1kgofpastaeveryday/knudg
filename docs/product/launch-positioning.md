# Public Launch Positioning

Status: public-safe launch memo for release and outreach planning. This is not
evidence of adoption, usage, or production readiness.

## Positioning Thesis

Knudg should not launch as a generic AI memory API. That category is already
crowded and better-funded. The credible wedge is narrower:

> Knudg is a self-hostable worklog for coding agents and OSS maintainers. It
> records what an attempt actually proved: which fix worked, which paths
> failed, and which environment traps wasted the run.

The launch problem is not "agents need memory" in the abstract. The launch
problem is more concrete: coding agents repeatedly re-debug the same package,
CI, migration, build, test, and release failures. Knudg's first claim should be
that these repeated failures deserve a structured, redacted worklog that agents
can retrieve before starting from zero.

Retrieved cards remain untrusted evidence. They are hints the acting agent
must verify in the current environment, not instructions to execute.

## Competitive Snapshot

Snapshot date: 2026-06-16. This table uses public vendor/project docs and
landing pages. It should be refreshed before any major launch or funding
application.

| Project or category | Public positioning | Knudg relationship |
| --- | --- | --- |
| [Mem0](https://docs.mem0.ai/introduction) | "Universal, self-improving memory layer for LLM applications." Offers managed and open-source paths. | Strong generic memory competitor. Avoid matching its breadth. Emphasize task-outcome evidence for coding agents, not persistent user/app memory. |
| [OpenMemory](https://mem0.ai/openmemory) | Persistent MCP memory layer for coding agents that auto-captures preferences, patterns, and setup, then injects relevant memories. | Closest coding-agent memory adjacent. Differentiate on solved/failed path cards, an approval-first private posture, and evidence-not-instruction retrieval. |
| [Letta](https://docs.letta.com/guides/core-concepts/stateful-agents/) | Stateful agent foundation where memories, messages, reasoning, and tool calls persist in a database and agents can modify memory through tools. | Agent runtime and state platform, not the same layer. Position Knudg as a worklog-card tool that can sit beside many runtimes. |
| [LangGraph / LangChain long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory) | Agent memory stores persist JSON documents organized by namespace and key, with tool read/write access. | Framework primitive. Knudg should not compete as a store API; its wedge is worklog card shape, trust lifecycle, and coding-task retrieval semantics. |
| [Supermemory](https://supermemory.ai/docs/intro) | Long-term and short-term memory/context infrastructure with memory, extraction, connectors, and managed RAG. | Broad context infrastructure competitor. Avoid "complete context stack" claims. Keep the wedge to coding-agent experience reuse. |
| [Pieces](https://pieces.app/) | OS-level developer memory that automatically forms memories from code, docs, chats, and workflow context. | Personal developer workflow memory. Knudg should avoid always-on capture language and emphasize explicit redacted cards and self-hostable review. |
| [Claude Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) | Reusable filesystem-based instructions/resources that load when relevant. | Adjacent reusable capability format. Skills describe how to work; Knudg cards record what happened and whether it worked. |
| [AGENTS.md](https://agents.md/) and [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | Repository guidance for coding agents, kept separate from human README content. | Complementary. AGENTS.md tells agents local rules before work starts; Knudg retrieves prior task evidence during work. |

## What To Say

Use this frame consistently:

- **Category:** self-hostable worklog for coding agents.
- **Wedge:** package, CI, migration, build, test, and release failures.
- **Unit:** redacted experience card: solved path, failed path, environment
  trap, deprecated approach, or clarified unknown.
- **Safety posture:** private by default, redaction and revocation are
  first-class design constraints, and retrieved cards are evidence, not
  instructions.
- **Stage:** early-stage Apache-2.0 project.

Avoid these claims:

- "market-leading," "production-ready," "widely adopted," or "state of the
  art"
- broad "AI memory for everything" positioning
- claims that public hosted retrieval or public publication are ready
- claims that retrieved cards should be followed without local verification

## Short Explanation

Knudg is a self-hostable worklog for coding agents and the people maintaining
their projects. When an agent fixes a flaky CI job, untangles a migration, or
works around a build trap, that outcome usually disappears. Knudg keeps the
receipt: which path worked, which dead ends wasted time, and which local trap
changed the answer. The next agent on a similar task can look this up before
re-exploring from scratch. Everything is private by default, with redaction and
revocation treated as design constraints, and retrieved cards are evidence to
weigh, not instructions to follow.

## Launch Sequence

1. **Repository hygiene first.** Keep GitHub metadata, topics, license
   detection, release notes, CI, secret scanning, and live-site smoke green.
2. **Tell one narrow story.** Lead with coding agents repeatedly hitting the
   same CI/build/migration failures. Do not lead with broad memory.
3. **Show evidence.** Link the clean-machine quickstart transcript, v0.1.1
   release, Apache-2.0 license, and public gates.
4. **Ask for validation, not adoption theater.** The call to action should be:
   try the quickstart, open a self-hosting issue, or tell us which repeated
   coding-agent failure should become the first replay demo.
5. **Follow with proof.** The next meaningful public artifact should be a short
   walkthrough or replay showing one retrieval-panel suggestion changing an
   agent's route on a repeated developer-tooling failure.

## Launch Copy Drafts

### Option A: Category

Coding agents keep re-solving the same CI, migration, and build failures from
zero.

Knudg is a self-hostable worklog that keeps the receipt: which fix worked,
which paths failed, and which environment trap changed the answer.

Private by default. Retrieved cards are evidence, not instructions. Apache-2.0,
early days.

### Option B: Contrast

Memory layers store what an agent should remember.

Knudg stores what already happened: the fix that worked, the path that failed,
and the trap in the environment.

Built for coding agents and OSS maintainers. Self-hostable, private by
default, Apache-2.0.

### Option C: Problem

The expensive part of agent work is not just finding an answer. It is
rediscovering the same package, test, and release failures over and over.

Knudg is a shared worklog of solved and failed paths for coding agents.
Self-hostable, private by default, and designed around redaction, revocation,
and local verification.

## Next PR Themes

1. **Replay demo package.** Add a small public WEDGE-001 replay comparison
   that compares no-Knudg vs. retrieval-panel-assisted agent work on synthetic
   package/CI/build failures.
2. **Walkthrough asset.** Record or script a concise Codex plugin walkthrough
   showing one useful retrieval-panel suggestion on a repeated developer
   tooling task.
3. **Card capture polish.** Make solved/failed-path capture easier for the
   first wedge, without broadening into raw transcript storage or personal
   memory.
4. **Launch copy surfaces.** Keep README and the landing page focused on
   "a self-hostable worklog for coding agents," and keep broader memory
   comparisons in docs rather than in first-viewport copy.
