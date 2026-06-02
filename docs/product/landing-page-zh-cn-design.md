# Simplified Chinese Landing Page Design

Status: Proposed static localization, synchronized May 12, 2026

This document defines the Simplified Chinese landing page implemented in
`site/zh-cn/index.html` with Chinese-specific content rules in `site/styles.css`.
It is a localization, not a line-by-line translation of the English or Japanese
pages.

Document authority:

- classification: internal project design, not public landing-page copy
- owns: Simplified Chinese public message boundary, reading order, visible
  content intent, and parity with the English and Japanese pages
- does not own: deployment steps, rollback procedure, mechanical release checks,
  or production incident handling

## Localization Goal

The Chinese page should feel like a serious engineering infrastructure preview
for teams using coding agents. It should not feel like:

- a direct machine translation from English or Japanese
- a consumer knowledge app
- a public beta funnel
- an AI hype page
- a China-market sales deck with exaggerated claims

Use Simplified Chinese for mainland/global Chinese readers. Prefer `智能体` for
agent and `编程智能体` for coding agent. Avoid `代理` because it can read as a
network proxy. Keep English technical tokens only where Chinese developer
readers naturally expect them, such as `CI`.

## Public Disclosure Boundary

The Chinese page must explain only what the reader needs:

- what effect Knudg aims to create
- why repeated agent work is costly
- why remembered experience is safer as a clue than as an instruction
- why the current page does not provide public access
- what evidence must be proven before opening access

The page must not expose:

- internal retrieval mechanics or system diagrams
- schema fields, internal state names, identifiers, or policy tables
- implementation channel detail
- storage, ranking, indexing, or publication workflow detail
- active-looking product actions
- enough process detail for a reader to reconstruct the product

Rule of thumb:

> If a detail helps someone copy the product more than it helps a reader trust
> the product, do not put it on the landing page.

## Implemented Positioning

Hero headline:

```text
别让智能体一遍遍从头排查。
```

Supporting copy:

```text
Knudg 是面向编程智能体的经验共享基础设施。
它把过去任务中的判断和教训保留下来，作为下一次工作可验证的线索。
```

Audience bridge:

```text
适合正在让编程智能体反复处理构建、CI、迁移和开发工具问题的工程团队。
```

Wedge copy:

```text
开发工具问题是首个切入点，因为这类问题最容易反复出现。
Knudg 不是 CI 知识库；它保留的是可在下一次工作中重新验证和判断的经验。
```

State strip:

```text
当前仅为信息预览，暂未开放产品使用。
```

Hero status:

```text
信息预览
仅供了解
暂未开放使用
```

Current public state:

- information only
- no public product access or integration entry point from the preview
- no public search results
- no active intake, account creation, download, command, or access route
- no live product data in the mock surface

The page intentionally avoids funnel language. It must not invite self-serve
account creation, setup, contact, trial, application, waitlist, or product
access.

## Audience

Primary readers:

- engineering managers, tech leads, and senior engineers using coding agents in
  repeated build, release, migration, and developer-tooling work

Secondary readers:

- agent platform builders
- developer tooling teams
- technical founders
- security and privacy reviewers

The first viewport should communicate the pain and expected effect before the
reader sees any system detail. It should also make the audience clear in one
sentence so the page does not read as an individual memory tool or generic
agent plugin.

## Localization Parity

English, Japanese, and Simplified Chinese pages must carry the same product
commitments:

| Commitment | Chinese page |
| --- | --- |
| Audience | teams operating coding agents |
| Product frame | shared agent experience infrastructure |
| First wedge | repeated developer-tooling failures |
| Safety | clue to verify, not instruction |
| Access state | no public product access or integration entry point |
| Publication | human-reviewed and scoped before sharing |

The Chinese page can change cadence, term choices, and label density, but not
these commitments.

## Reading Rhythm

The page is scan-first. It should use:

- short headline and short supporting copy
- concise status labels
- fewer machine-like labels than the English page
- compact but readable cards
- line lengths around 15 to 40 Chinese characters for important prose
- line-height around `1.65` to `1.8` for CJK body copy

Reference findings used:

- Simplified Chinese typography guidance recommends Simplified Chinese for the
  mainland/global Chinese market and shorter Chinese line lengths, roughly
  15-40 characters per line.
  <https://www.morisawa-usa.com/post/simplified-chinese-typography-basics>
- CJK typesetting guidance notes that CJK text benefits from generous leading,
  around `1.7`, because of higher information density per character.
  <https://www.typotheque.com/articles/typesetting-cjk-text>
- Developer AI adoption and trust concerns support the page's focus on
  repeated debugging value and verification, not automatic obedience.
  <https://survey.stackoverflow.co/2025/ai>

## Implemented Page Outline

### Header

Navigation:

- 问题
- 效果
- 示例
- 安全
- 状态
- 验证

Status labels:

- `信息预览`
- `仅供了解`

Mobile behavior:

- at `767px` CSS width and below, hide header navigation and status labels and
  keep only brand plus language switch in the sticky header
- at `768px` CSS width and above, show navigation and status labels
- do not add a hamburger, disclosure button, or scripted menu
- the same closed-access state remains visible in the hero status strip

### Hero

The hero explains:

- the repeated-work problem
- the target wedge of developer-tooling failures
- the target reader: teams operating coding agents across build, CI, migration,
  and developer-tooling failures
- that the page is only an information preview

The hero mock should put the Knudg action image first:

- use a console-style log block
- show that similar prior work was found
- show that repeated trial and error was skipped
- show cumulative saved time, token count, and estimated token cost
- avoid extra explanatory panels that weaken the cost-reduction image

### 问题

Purpose: create recognition before product explanation.

Cards:

- 反复重读文档
- 失败方案被再次尝试
- 环境陷阱留在会话里

### 效果

Purpose: make outcomes feel like Knudg product behavior, not abstract
mechanics.

Each card should include a short console-style log that sounds like an agent
starting work with a reusable clue. Use concrete but public-safe examples such
as Windows PowerShell local validation failures, failed dependency reinstall
attempts, deploy version checks, or a reminder to verify before use.

Layout: stack the outcome log blocks vertically. Do not force these examples
into the generic card grid; they should read top-to-bottom like a sequence of
Knudg nudges.

Cards:

- 找到相似工作
- 避开死路
- 传给下一次工作
- 不要变成命令

### 私有验证回放

Purpose: show that Knudg starts a task by suggesting what to suspect first.

The replay should read like a public-safe task log, not a terminal transcript
or internal system trace. Use direct examples such as Playwright blank
screenshots, Windows sandbox command failures, OS update environment drift, and
deploy smoke/version checks.

The replay must not include commands, routes, identifiers, schema/state names,
exact card contents, private paths, raw prompt text, or transcripts.

### 示例

Purpose: show public-safe examples of what kind of lesson is preserved.

The first example should feel like something an agent could actually use while
remaining public-safe. It may name familiar developer-tooling context, but must
not expose internal schema names, retrieval fields, product APIs, workspace
identifiers, exact stack/runtime versions, named remediation commands, or
detailed proprietary process.

Featured example:

- visible label: CI 环境线索
- title: 包构建在本地通过，却只在 CI 中失败
- agent-facing sample: CI 可能选择了与本地不同的工具链或配置。再次尝试以前有效的修复前，先比较 CI 与本地环境差异。前提不匹配时，不使用这条线索。
- safety note: 只作为候选依据，需要在当前工作环境中验证。

The visible layout should read as a public example card, not as an internal
data model. Labels are presentation aids, not product fields. Use at most three
visible public-safe labels in the card, and on mobile keep the title outside the
row budget. If it starts to look like a schema table, merge rows into
plain-language sentences.

Cards use narrative, non-taxonomic labels:

- CI 环境线索
- 有过效果的处理
- 已经走过的弯路
- 还不能下结论
- 调查到这里为止
- 需要重新确认

Each example uses:

- short label
- title
- one-sentence summary
- plain-language value sentence

Do not add metadata tables to these public cards.

### 实际用法

List:

- 记住失败类型
- 不暴露原始工作内容，只传递可复用的经验
- 明确线索需要验证
- 共享前需要人工确认

### 安全

Purpose: explain why the product can be trusted without exposing implementation
detail.

Allowed safety claims:

- raw work does not appear on the public page
- sharing is not automatic
- this page does not display public search results
- shared experience is not automatic; human review and scoped sharing are
  launch requirements
- retrieved experience is untrusted candidate evidence
- retrieved experience cannot authorize tool use, bypass local checks, or
  replace current workspace verification
- scope and withdrawal controls are launch requirements
- stale or unsafe clues are reasons to stop reuse

### 状态

Status cards:

- 公开页面
- 私下验证
- 接入未开放
- 细节暂不公开

The section must make clear that the page is not a product entrance.

### 验证

Questions:

- 是否减少了回到同一项调查的时间
- 智能体是否把候选经验当作线索而非指令
- 是否能在不暴露原始工作的情况下共享经验
- 人是否能理解并控制哪些内容会被共享

## Visual Direction

Use restrained Chinese infrastructure brutalism:

- hard black borders remain
- Chinese text cards use smaller shadows than the English page
- hero and section surfaces need enough breathing room
- yellow is a signal, not a product-action color
- red is reserved for failure and warning
- mono text is limited to labels and compact state chips
- Chinese body copy uses generous line-height

Avoid:

- China-market AI hype language
- long strings of badges above the fold
- all sections having the same text weight
- machine-looking labels as the primary Chinese reading layer
- CTA-like disabled controls
- details that read like internal launch checklists

## Typography

No remote fonts.

Simplified Chinese font stacks:

```css
--zh-heading-font: "Microsoft YaHei", "PingFang SC", "Noto Sans SC",
  "Source Han Sans SC", "Hiragino Sans GB", Arial, sans-serif;
--zh-body-font: "Microsoft YaHei", "PingFang SC", "Noto Sans SC",
  "Source Han Sans SC", "Hiragino Sans GB", Arial, sans-serif;
--zh-code-font: "SFMono-Regular", Consolas, "Liberation Mono",
  "Microsoft YaHei", monospace;
```

Rules:

- keep Chinese body text at or above `16px`
- use line-height around `1.65` to `1.8` for Chinese paragraphs
- avoid letter spacing
- avoid viewport-scaled type
- use headings and summaries to reduce fatigue

## Message Acceptance

The visible Chinese page should satisfy these message and disclosure checks:

- it identifies teams operating coding agents as the primary reader
- it frames developer-tooling failures as the first wedge, not the whole product
- it does not position Knudg as personal memory, a generic notes tool, or a
  single plugin
- it makes the current no-access state clear without inviting self-serve
  account creation, setup, contact, trial, application, waitlist, or product
  access
- no visible product-action controls
- no internal field names or machine states in visible copy
- no implementation route to deeper technical detail
- first viewport communicates effect and safety before mechanics
- mobile text remains readable and not over-dense
- featured example is no more than three visible labeled rows on mobile

Mechanical release validation, local target enumeration, headers, deployment,
and rollback are owned by the internal operator runbook.

## Implementation Contract

- public route: `/zh-cn/`
- local page: `site/zh-cn/index.html`
- local 404 page: `site/zh-cn/404.html`
- document language: `<html lang="zh-CN">`
- canonical URL: `https://knudg.com/zh-cn/`
- reciprocal alternates on English, Japanese, and Chinese pages:
  - `hreflang="en"` -> `https://knudg.com/`
  - `hreflang="ja"` -> `https://knudg.com/ja/`
  - `hreflang="zh-CN"` -> `https://knudg.com/zh-cn/`
  - `hreflang="x-default"` -> `https://knudg.com/`
- language switch targets:
  - English: `/`
  - Japanese: `/ja/`
  - Simplified Chinese: `/zh-cn/`
- localized missing route: `/zh-cn/missing-smoke` should serve
  `site/zh-cn/404.html` with `404` status and `<html lang="zh-CN">`
