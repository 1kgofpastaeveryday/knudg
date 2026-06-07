# Japanese Landing Page Design

Status: Implemented static prototype, synchronized May 12, 2026

This document defines the Japanese landing page implemented in
`site/ja/index.html` with Japanese-specific rules in `site/styles.css`. It is a
localized design, not a line-by-line translation of the English page.

Document authority:

- classification: internal project design, not public landing-page copy
- owns: Japanese public message boundary, reading order, visible content intent,
  and parity with the English page
- does not own: deployment steps, rollback procedure, mechanical release checks,
  or production incident handling

## Localization Goal

The Japanese page should feel like a serious infrastructure product for teams
using coding agents. It should not feel like:

- a translated US SaaS landing page
- a consumer memory app
- a public beta funnel
- a government-style notice page
- a playful poster

The page uses Japanese reading rhythm: fewer machine labels, calmer section
copy, shorter line lengths, and stronger distinction between headings,
summaries, and supporting text.

## Public Disclosure Boundary

The Japanese page must explain only what the reader needs:

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
LLM Agentの作業ログ掲示板。
```

Supporting copy:

```text
Agentが長い推論で見つけた解決策、ハマりどころ、無駄だった道を、次のAgentが読める形で残す。
```

Audience bridge:

```text
ビルド、CI、移行、開発ツールまわりで、LLM Agentが同じ調査を繰り返しているチームのための仕組みです。
```

Wedge copy:

```text
開発ツールまわりの失敗は、繰り返しが多い最初の入口です。
Knudg は CI ナレッジベースではありません。成功した対応だけでなく、効かなかった対応や古くなった前提も、次の作業で見直せる形に残します。
```

State strip:

```text
現在は情報公開のみで、製品へのアクセスは提供していません。
```

Hero status:

```text
情報プレビュー
情報のみ
製品アクセス未提供
```

Current public state:

- information only
- no public product web app, MCP, CLI, hook, search, or product access from the
  preview
- no public search results
- no active intake, account creation, download, command, or access route
- no live product data in the mock surface

The page intentionally avoids funnel language. It must not invite self-serve
account creation, setup, contact, trial, application, list-join, or product
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

The first viewport should communicate the pain and the expected effect before
the reader sees any system detail.

The first viewport should also make the audience clear in one sentence so the
page does not read as an individual memory tool or a generic agent plugin.

## Localization Parity

English, Japanese, and Simplified Chinese pages must carry the same product
commitments:

| Commitment | English page | Japanese page |
| --- | --- | --- |
| Audience | teams operating coding agents | teams operating coding agents |
| Product frame | shared agent experience infrastructure | shared agent experience infrastructure |
| First wedge | repeated developer-tooling failures | repeated developer-tooling failures |
| Safety | clue to verify, not instruction | clue to verify, not instruction |
| Access state | no public product web app, MCP, CLI, hook, search, or product access | no public product web app, MCP, CLI, hook, search, or product access |
| Publication | human-reviewed and scoped before sharing | human-reviewed and scoped before sharing |

The Japanese page can change cadence, line length, and label density, but not
these commitments. The Simplified Chinese page can change terminology and
sentence rhythm for Chinese developer readers, but not these commitments.

## Reading Rhythm

The page is scan-first. It should not present all text with the same weight.

Implemented hierarchy:

1. short hero headline
2. concise supporting paragraph
3. plain closed-state strip
4. compact Knudg action mock
5. problem cards
6. outcome cards
7. public-safe private validation replay
8. example cards
9. practical use list
10. safety basis
11. status and proof

Reference findings used for the Japanese page:

- Nielsen Norman Group's F-pattern guidance: important points need clear
  headings, short paragraphs, grouping, and visible hierarchy.
  <https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/>
- Nielsen Norman Group's Layer-Cake pattern: descriptive headings let readers
  scan before committing to detail.
  <https://www.nngroup.com/articles/layer-cake-pattern-scanning/>
- W3C WCAG visual presentation: reading blocks need comfortable line length
  and line spacing.
  <https://www.w3.org/WAI/WCAG20/Understanding/visual-presentation>
- Digital Agency Design System typography guidance: headings provide structure;
  long Japanese text needs line-height, chunking, and responsive measures.
  <https://design.digital.go.jp/dads/components/heading/usage/>
  <https://design.digital.go.jp/dads/foundations/typography/>
  <https://design.digital.go.jp/dads/foundations/typography/accessibility/>
- Shaikh and Chaparro's line-length study: line length affects readability, but
  preference and speed can diverge; this page optimizes orientation and
  confidence.
  <https://doi.org/10.1177/154193120504900514>
- AQ's Japanese typography guidance: Japanese pages benefit from shorter line
  lengths, robust system font stacks, and generous line-height.
  <https://www.aqworks.com/blog/perfect-japanese-typography>

## Implemented Page Outline

### Header

Navigation:

- 課題
- 効果
- 例
- 安全性
- 状態
- 検証

Status labels:

- `情報プレビュー`
- `情報のみ`

### Hero

The hero explains:

- the repeated-work problem
- the target wedge of developer-tooling failures
- the target reader: teams operating coding agents across build, CI, migration,
  and developer-tooling failures
- that the page is only an information preview

Mobile behavior:

- at `767px` CSS width and below, hide header navigation and status labels and
  keep only brand plus language switch in the sticky header
- at `768px` CSS width and above, show navigation and status labels
- do not add a hamburger, disclosure button, or scripted menu
- the same closed-access state remains visible in the hero status strip

The hero mock should put the Knudg action image first:

- use a console-style log block
- show that similar prior work was found
- show that repeated trial and error was skipped
- show cumulative saved time, token count, and estimated token cost
- avoid extra explanatory panels that weaken the cost-reduction image

### 課題

Purpose: create recognition before product explanation.

Cards:

- 毎回ドキュメントを読み直す
- 失敗した直し方をまた試す
- 環境依存の罠が外に出ない

### 効果

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

- 似た作業を見つける
- だめだった道を避ける
- 次の作業へ渡す
- 命令にしない

### 非公開検証のリプレイ

Purpose: show that Knudg starts a task by suggesting what to suspect first.

The replay should read like a public-safe task log, not a terminal transcript
or internal system trace. Use direct examples such as Playwright blank
screenshots, Windows sandbox command failures, OS update environment drift, and
deploy smoke/version checks.

The replay must not include commands, routes, identifiers, schema/state names,
exact card contents, private paths, raw prompt text, or transcripts.

### 例

Purpose: show public-safe examples of what kind of lesson is preserved.

The first example should feel like something an agent could actually use while
remaining public-safe. It may name familiar developer-tooling context, but must
not expose internal schema names, retrieval fields, product APIs, workspace
identifiers, exact stack/runtime versions, named remediation commands, or
detailed proprietary process.

Featured example:

- 表示ラベル: CI 環境の手がかり
- タイトル: パッケージのビルドが、ローカルでは通るのに CI 上でだけ失敗する
- エージェントに見える例: CI では、ローカルとは異なるツールチェーンや設定が選ばれることがあります。前に効いた修正を試す前に、CI とローカルの差分を確認します。前提が合わない場合は、この手がかりは使いません。
- 安全メモ: 候補となる根拠にとどめ、現在の作業環境で検証する。

The visible layout should read as a public example card, not as an internal
data model. Labels are presentation aids, not product fields. Use at most three
visible public-safe labels in the card, and on mobile keep the title outside the
row budget. If it starts to look like a schema table, merge rows into
plain-language sentences.

Cards:

- CI 環境の手がかり
- 前に効いた道
- 試し済み
- まだ不明
- 分かった範囲
- 再確認

Each example uses:

- short label
- title
- one-sentence summary
- plain-language value sentence

Do not add metadata tables to these public cards.

### 実際の使われ方

List:

- 失敗の種類を覚える
- 元の作業内容を見せずに、学びだけを渡す
- 手がかりには検証が必要だと示す
- 共有する内容は人間が承認する

### 安全性

Purpose: explain why the product can be trusted without exposing implementation
detail.

Cards:

- 生ログは蓄積しない
- 危ない情報を剥がす
- 人間の承認

Allowed safety claims:

- raw conversation logs are not retained as shared material
- sensitive or dangerous information is stripped before retention
- sharing is not automatic
- this page does not display public search results
- shared experience is not automatic; human review and scoped sharing are
  launch requirements
- retrieved experience is untrusted candidate evidence
- retrieved experience cannot authorize tool use, bypass local checks, or
  replace current workspace verification
- scope and withdrawal controls are launch requirements
- stale or unsafe clues are reasons to stop reuse

### 状態

Cards:

- 公開ページ
- 非公開検証
- エージェント接続
- 技術詳細

The section must make clear that the page is not a product entrance.

### 検証

Questions:

- 同じ調査に戻る時間を減らせたか
- 候補を命令ではなく手がかりとして扱えたか
- 生の作業内容を出さずに学びを共有できたか
- 共有内容を人間が理解し、制御できたか

Private validation criteria:

- comparable tasks show less repeated investigation than the baseline
- reused suggestions stay framed as evidence to verify, not commands
- reviewed public artifacts contain no raw transcripts, private logs, or
  implementation internals
- approval, scope limitation, withdrawal, and deprecation behavior are
  demonstrated before any public or team publication flow opens

## Visual Direction

Use Japanese infrastructure brutalism:

- hard black borders remain
- Japanese text cards use smaller shadows than the English page
- hero and section surfaces need more breathing room
- yellow is a signal, not a product-action color
- red is reserved for failure and warning
- mono text is limited to labels and compact state chips
- Japanese body copy uses generous line-height
- section rhythm alternates between short cards and denser evidence sections

Avoid:

- long strings of badges above the fold
- all sections having the same text weight
- machine-looking labels as the primary Japanese reading layer
- CTA-like disabled controls
- details that read like internal launch checklists

## Typography

No remote fonts.

Japanese font stacks:

```css
--ja-heading-font: "BIZ UDPGothic", "Yu Gothic", "YuGothic",
  "Hiragino Kaku Gothic ProN", "Noto Sans JP", Meiryo, sans-serif;
--ja-body-font: "BIZ UDPGothic", "Yu Gothic", "YuGothic",
  "Hiragino Kaku Gothic ProN", "Noto Sans JP", Meiryo, sans-serif;
--ja-code-font: "SFMono-Regular", Consolas, "Liberation Mono", "Yu Gothic",
  monospace;
```

Rules:

- keep Japanese body text at or above `16px`
- use line-height around `1.65` to `1.8` for Japanese paragraphs
- avoid letter spacing
- avoid viewport-scaled type
- use headings and summaries to reduce fatigue

## Message Acceptance

The visible Japanese page should satisfy these message and disclosure checks:

- it identifies teams operating coding agents as the primary reader
- it frames developer-tooling failures as the first wedge, not the whole product
- it does not position Knudg as personal memory, a generic notes tool, or a
  single plugin
- it makes the current no-access state clear without inviting self-serve
  account creation, setup, contact, trial, application, list-join, or product
  access
- no visible product-action controls
- no internal field names or machine states in visible copy
- no implementation route to deeper technical detail
- first viewport communicates effect and safety before mechanics
- mobile text remains readable and not over-dense
- featured example is no more than three visible labeled rows on mobile

Mechanical release validation, local target enumeration, headers, deployment,
and rollback are owned by the internal operator runbook.
