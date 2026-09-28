# 先行事例調査レポート: 引き継ぎ・新規参加者向け README を書くスキル

## 調査日

2026-09-28

## 何を探したか

リポジトリの README を新規作成・更新・点検するスキル。読者は人間（担当を引き継ぐ人と、
初めてそのリポジトリを触る他のエンジニア）で、「README を書いて」「引き継ぎできるように
README を整えて」と言われたときに発動する。触るのはリポジトリの中身（package.json・
Makefile・環境変数・CI・デプロイ設定）で、表示先は GitHub / Bitbucket。

### 検索語

- 英語: readme, readme generator, write readme, crafting readme, readme best practices, project documentation, handoff, onboarding docs
- 日本語: README, 引き継ぎ

## 調査を省略した理由

なし

## 調査した層

### T0 — 手元

実行したクエリ:

```bash
bash ~/.claude/plugins/cache/yike-skills/skill-kit/ce7910a48cbb/skills/skill-prior-art/scripts/search_local.sh readme README handoff onboarding 引き継ぎ
```

結果: 探した場所 44 / SKILL.md 300 本 / コマンド 6 本 / 候補 6 件（exit 1）。
README を明示的に引き受けているのは自作の `studio:doc-brief` だけ。description に
「READMEを書いて」「引き継ぎ資料を作って」を含む。残りの5件（academy-guide・
paas-onboarding・accessibility-review・design-handoff・ux-copy）は語が当たっただけで無関係。
`softaworks/agent-toolkit` は導入済みだが、入っているのは `c4-architecture` と
`mermaid-diagrams` の2本で、同じリポジトリの `crafting-effective-readmes` は入っていない。

### T1 — Anthropic公式

実行したクエリ:

```bash
gh search code --repo anthropics/skills --filename SKILL.md readme
gh search code --repo anthropics/claude-plugins-official readme --filename SKILL.md
gh api "repos/anthropics/skills/git/trees/main?recursive=1" --jq '.tree[].path' | grep SKILL.md | grep -iE 'doc|writ|readme'
gh api "repos/anthropics/knowledge-work-plugins/git/trees/main?recursive=1" --jq '.tree[].path' | grep documentation
```

結果: `anthropics/skills` と `claude-plugins-official` に README 専用のスキルは無い
（ヒットは「README を読め」「プラグインの README に書け」という言及だけ）。文書系は
`doc-coauthoring`（共同執筆の進め方。README 固有の内容は無い）と `docx`。
`anthropics/knowledge-work-plugins` の `engineering/skills/documentation` が README を
文書タイプの一つとして扱う（候補 3）。

### T2 — ベンダー公式

<!-- README の表示先は GitHub。GitHub 自身が出しているものを見た。 -->

実行したクエリ:

```bash
npx skills find "readme generator"
gh api repos/github/awesome-copilot --jq '"\(.owner.login)/\(.owner.type) pushed=\(.pushed_at)"'
gh api "repos/github/awesome-copilot/git/trees/main?recursive=1" --jq '.tree[].path' | grep readme-blueprint
```

結果: `github/awesome-copilot` の `readme-blueprint-generator`（候補 4）。GitHub の
Organization 所有。`.github/copilot/` 配下の資料を前提にした Copilot 向けのプロンプトで、
Claude Code の運用には合わない。Bitbucket（Atlassian）の公式スキルは今回探していない。

### T3 — マーケットプレイス

実行したクエリ:

```bash
gh api "repos/anthropics/claude-plugins-official/git/trees/main?recursive=1" --jq '.tree[].path' | grep -iE 'readme|doc'
```

結果: 該当なし。ヒットは `playground` のテンプレートと `plugin-dev` の参照ファイルだけで、
README を書くプラグインは無い。claude.com/plugins の画面は今回見ていない。

### T4 — skills.sh

実行したクエリ:

```bash
npx skills find readme
npx skills find "readme generator"
npx skills find "write readme"
npx skills find "crafting readme"
npx skills find "readme best practices"
npx skills find "project documentation"
npx skills find handoff
npx skills find "onboarding docs"
```

結果: README に直接関係するのは次の5件（候補 1・2・5・6・7）。
`mattpocock/skills@handoff` は会話の引き継ぎ（エージェント間）で、README とは別物。

### T5 — 著名企業・個人

実行したクエリ:

```bash
gh search code --filename SKILL.md "readme" --limit 40
gh search repos "readme skill claude" --limit 15
```

結果: 該当なし。どちらも README 専用スキルを返さなかった。T4 の候補の提供元
（GitHub・Anthropic・softaworks）がこの層を兼ねる。

## 候補

### crafting-effective-readmes

- 層: T4
- 提供元: softaworks（Organization）
- 取得元URL: https://skills.sh/softaworks/agent-toolkit/crafting-effective-readmes （npx skills find で 4.1K installs と表示）
- できること: 作業を「新規・追記・更新・点検」の4つに分けて質問を変える。プロジェクト種別（OSS・個人・社内・設定）で読者と必須節を切り替え、節の要否を表にしている。社内向けテンプレートが最も近く、環境変数を「変数・説明・どこで入手するか」の表で書かせ、上流・下流の依存、Runbook、症状・原因・対処の3段で書くトラブルシュートを持つ。最後に「他に載せるべきことは」と必ず聞く
- 足りないこと: README の記述がコードと合っているかを確かめる手順が無い（点検モードでも「package.json と照合」の1行だけ）。引き継ぎで最も抜ける情報（外部サービスのアカウント、秘密情報の置き場所、費用、持ち主）がテンプレートの枠にしか無く、リポジトリから拾う手順が無い。長さの上限が無い。日本語が無い。スクリプトが無い
- 保守状況: リポジトリ全体の最終 push が 2026-03-05（約7か月前）。open issue 18
- 監査結果: 提供元は Organization 本体。同梱スクリプトなし（読むのは .md だけ）。ネットワーク・資格情報・削除操作なし。ライセンス MIT。半年以上 push が無いので、仕様追随は期待しない。skills.sh の監査表は未確認。**骨格と節の選び方を借り、文章は借りない**

### docs-guard

- 層: T4
- 提供元: amElnagdy（個人）
- 取得元URL: https://skills.sh/amelnagdy/guard-skills/docs-guard （npx skills find で 3.5K installs と表示）
- できること: 「文書はコードベースについての主張の集合で、主張はすべて検証できる」という立場で、README に出てくる関数・CLI フラグ・設定キー・環境変数・パスを抜き出し、それぞれをコード側の定義と照合させる。照合表（主張の種類ごとの一次情報と確かめ方）、検証できない主張は削るか弱める、コードを変えたら文書の全箇所を grep する、TODO や「近日公開」の節を残さない、という規則
- 足りないこと: 照合は指示だけで、スクリプトが無い。何を書くか（構成・読者）は明示的に対象外。引き継ぎの観点が無い。日本語が無い
- 保守状況: 最終 push 2026-07-04。open issue 4
- 監査結果: 提供元は個人アカウント。同梱スクリプトなし。ネットワーク・資格情報・削除操作なし。ライセンス MIT。skills.sh の監査表は未確認。**照合の考え方だけを借り、機械検査は自前で書く**

### documentation（knowledge-work-plugins）

- 層: T1
- 提供元: Anthropic（`anthropics/knowledge-work-plugins`）
- 取得元URL: https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/documentation/SKILL.md
- できること: README・API・Runbook・設計・オンボーディングの5種の骨格を並べる。README は「何でなぜあるか・5分で初回成功・設定と使い方・貢献」。オンボーディングに「誰に何を聞くか」がある。原則は「読者のために書く」「最も役立つ情報を先に」「古い文書は無いより悪い」「複製せずリンクする」
- 足りないこと: 骨格の一覧だけで（取得した SKILL.md は 1507 バイト。https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/documentation/SKILL.md ）、手順も検査も無い
- 保守状況: 最終 push 2026-09-26
- 監査結果: Anthropic 公式。スクリプトなし。ライセンス Apache-2.0

### readme-blueprint-generator

- 層: T2
- 提供元: GitHub（`github/awesome-copilot`）
- 取得元URL: https://skills.sh/github/awesome-copilot/readme-blueprint-generator
- できること: リポジトリに既にある資料（Copilot 用の指示ファイル群）を材料に README を組む。材料を先に集めるという順序は正しい
- 足りないこと: 技術スタック・構成・コーディング規約・テスト・貢献まで11節を全部埋めさせるので、必ず長くなる。読者を問わない。`.github/copilot/` の資料が無いと材料が無い
- 保守状況: 最終 push 2026-09-27
- 監査結果: 提供元は GitHub の Organization。スクリプトなし。ライセンス MIT。**反面教師として扱う（節を網羅させると README は肥大する）**

### beautify-github-readme

- 層: T4
- 提供元: oil-oil（個人）
- 取得元URL: https://skills.sh/oil-oil/beautify-github-readme/beautify-github-readme
- できること: 書く前に「読者・一文での価値・一番の証拠・最初に成功する操作」を書き出させる。実績・ベンチマーク・対応環境を捏造しない。長い説明より例を先に置く。README から参照する画像の欠落と SVG の不適合を `audit_readme.py` で機械検査する
- 足りないこと: 主題は OSS の見た目（ヒーロー画像・SVG・GIF）で、社内の引き継ぎには過剰
- 保守状況: 最終 push 2026-09-10
- 監査結果: 提供元は個人。同梱スクリプトのうち読んだ `audit_readme.py`（https://github.com/oil-oil/beautify-github-readme/blob/main/skills/beautify-github-readme/scripts/audit_readme.py ）はローカルファイルを読むだけでネットワーク・削除なし。ライセンス MIT

### codebase-documenter

- 層: T4
- 提供元: ailabs-393
- 取得元URL: https://skills.sh/ailabs-393/ai-labs-claude-skills/codebase-documenter
- できること: 「なぜを先に」「段階的に開示」「5分で動かす」「前提知識ゼロで書く」の原則と、README・設計・API のテンプレート
- 足りないこと: 「前提知識ゼロ」「すべての概念に例」を徹底すると README は長くなる。検証手順が無い
- 保守状況: 最終 push 2025-11-11（10か月以上前）
- 監査結果: 未実施（借りるものが無いため）

### doc-brief

- 層: T0
- 提供元: 自作（`plugins/studio/skills/doc-brief`）
- 取得元URL: https://github.com/YIke23/skills/tree/main/plugins/studio/skills/doc-brief
- できること: 読者と「読んだ後に何が起きてほしいか」を先に決める。見出しに結論を書く。地の文の字数上限を `count.py` で機械検査する。作成日・最終更新日のヘッダ。落とした情報を畳むか付録へ逃がす
- 足りないこと: 汎用の文書スキルで、README 固有のもの（ローカルで動かす手順が実際に動くか、スクリプト名・環境変数・パスがコードと合っているか、外部サービスと秘密情報の置き場所）を見ない。README をリポジトリの入口として扱わず、1枚の文書として扱う
- 保守状況: 現役
- 監査結果: 自作のため不要

## 結論

derive

- 採用元: crafting-effective-readmes

### 既存で満たせない点

- README に書いたコマンド・スクリプト名・環境変数・パス・リンクが、実際のリポジトリと合っているかを**機械で**確かめるものが無い（docs-guard は指示だけ、他は手順自体が無い）
- 引き継ぎで最も抜ける情報（外部サービスとそのアカウント、秘密情報の置き場所、費用の発生源、持ち主と問い合わせ先）を、**リポジトリの中身から拾い出して**書かせるものが無い
- README を読んだだけの人が作業を始められるかを、書いた本人以外の目で確かめる工程が無い
- README と CLAUDE.md / AGENTS.md の役割分担を扱うものが無い（エージェント向けの規則が README に混ざる、または二重に書かれる）
- 日本語の README を、既存の doc-brief と役割を分けて扱うものが無い
