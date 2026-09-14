# 先行事例調査レポート: 会議で意思決定を仰ぐための単一HTML資料スキル（2種）

## 調査日

2026-09-14

## 何を探したか

**作成済みの .md を入力として受け取り**、その章立てを保ったまま会議用の単一HTMLに組み直すスキル。(1) 画面共有して喋る・図が主役のデッキ型、(2) 事前配布して黙読させる Amazon式6-pager 型。補足素材としてスプレッドシート・コードベースを参照することはあるが、**主入力はあくまで .md**。構成はスキル側で固定せず、.md の章立てに従う。聞き手は社内の経営/営業とエンジニア。

（初回調査時は「素材から資料を起こす」前提だったが、ユーザーの指摘により「作成済み .md を組み直す」前提に修正。T4 に md→HTML 変換系と図の自動生成系を追加調査した。）

### 検索語

- 英語: presentation, deck, slides, six-pager, narrative memo, decision, meeting notes, markdown to html, diagram, infographic
- 日本語: 会議資料, 提案資料

## 調査を省略した理由

なし

## 調査した層

### T0 — 手元

実行したクエリ:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/search_local.sh presentation deck slides six-pager narrative memo decision meeting 会議資料 提案資料
```

結果: 探した場所 45 / SKILL.md 381 本 / コマンド 6 本 / 候補 9 件（exit 0 だが候補あり）。内訳は `pptx`・`theme-factory`・`doc-coauthoring`・`docx`・`claude-api`・`consolidate-memory`・`import-memory`。**単一HTMLの会議資料を作るスキルは手元に無い。** ただし検索語に当たらなかったが隣接する自作スキルとして `studio:eli15`（単一HTML解説記事、Neobrutalism、`assets/base.css` + `scripts/check_contrast.py`）、`studio:paas-onboarding`（単一HTML導入ガイド）、`studio:doc-brief`（日本語 .md、5000字以内）がある。このセッションの組み込みスキルには `design`（デザインキャンバスをArtifactとして公開）、`artifact-design`、`dataviz`、`example-skills:web-artifacts-builder`、`example-skills:canvas-design` もある。

### T1 — Anthropic公式

実行したクエリ:

```bash
gh search code --repo anthropics/skills --filename SKILL.md "presentation"
gh search code --repo anthropics/skills --filename SKILL.md "slide deck"
gh api repos/anthropics/skills --jq '.stargazers_count, .pushed_at'
gh api repos/anthropics/claude-plugins-official --jq '.stargazers_count, .pushed_at'
```

結果: `anthropics/skills` は 176,169★ / pushed 2026-09-10（https://github.com/anthropics/skills）。両クエリとも `skills/pptx/SKILL.md` と `skills/theme-factory/SKILL.md` の2本しか返らない。`pptx` は .pptx ファイルの生成・編集が対象で、HTMLは出さない。しかも source-available（オープンソースではない）と明記されており派生不可。`theme-factory` は配色テーマを作るスキルで、資料の構成は扱わない。**Anthropic公式に、単一HTMLの会議資料スキルは無い。**

### T2 — ベンダー公式

実行したクエリ:

```bash
gh api repos/googleworkspace/cli --jq '.stargazers_count, .pushed_at'
gh api "repos/microsoft/skills/git/trees/main?recursive=1" --jq '.tree[].path' | grep -iE 'present|slide|deck|ppt|meeting'
gh api repos/getsentry/skills --jq '.stargazers_count, .pushed_at'
npx skills find "presentation"
```

結果: この要件は特定のSaaS上の作業ではないので、T2 は「資料形式を持つベンダー」を当たった。**Google Workspace**: `googleworkspace/cli` 30,983★ / pushed 2026-09-05（https://github.com/googleworkspace/cli）に `recipe-create-presentation` が同梱、29.8K installs（https://skills.sh/googleworkspace/cli/recipe-create-presentation）。出力は Google Slides で、単一HTMLではない。**Microsoft**: `microsoft/skills` の tree に present/slide/deck/ppt/meeting を含む SKILL.md は0件（https://github.com/microsoft/skills）。**Sentry**: `getsentry/skills` 991★ / pushed 2026-09-07（https://github.com/getsentry/skills）に `presentation-creator` あり。**単一HTMLを出すベンダー公式は Sentry のみで、それは Sentry ブランド専用。**

### T3 — マーケットプレイス

実行したクエリ:

```bash
gh api "repos/anthropics/claude-plugins-official/git/trees/main?recursive=1" --jq '.tree[].path' | grep -iE 'present|slide|deck|meeting|memo|ppt'
```

結果: `anthropics/claude-plugins-official` は 36,239★ / pushed 2026-09-13（https://github.com/anthropics/claude-plugins-official）。ヒットは `plugins/math-olympiad/skills/math-olympiad/references/presentation_prompts.md` の1件のみで、数学の解答提示に関するもの。**該当なし。**

### T4 — skills.sh

実行したクエリ:

```bash
npx skills find "presentation"
npx skills find "slide deck"
npx skills find "six pager"
npx skills find "meeting notes"
curl -sL https://raw.githubusercontent.com/JimLiu/baoyu-skills/main/skills/baoyu-markdown-to-html/SKILL.md
curl -sL https://raw.githubusercontent.com/JimLiu/baoyu-skills/main/skills/baoyu-diagram/SKILL.md
curl -sL https://raw.githubusercontent.com/JimLiu/baoyu-skills/main/skills/baoyu-infographic/SKILL.md
```

結果: 上位に多数ヒット。読むに値するものを4本抽出した（下の「候補」）。最大は `jimliu/baoyu-skills@baoyu-slide-deck` 30.1K installs（https://skills.sh/jimliu/baoyu-skills/baoyu-slide-deck）。6-pager は `ngmeyer/skills@six-pager` 283 installs（https://skills.sh/ngmeyer/skills/six-pager）が唯一の直球。**日本語の会議資料を単一HTMLで出すスキルは、検索上位には出てこない。** 前提修正後の再調査で、同リポジトリに `baoyu-markdown-to-html` と `baoyu-diagram` があることを確認した（下の「候補」）。

### T5 — 著名企業・個人

実行したクエリ:

```bash
gh api repos/JimLiu/baoyu-skills --jq '.stargazers_count, .pushed_at, .license.spdx_id'
gh api repos/Owl-Listener/designer-skills --jq '.stargazers_count, .pushed_at, .license.spdx_id'
gh api repos/code-on-sunday/slide-deck-generator --jq '.stargazers_count, .pushed_at'
```

結果: `JimLiu/baoyu-skills` 25,875★ / pushed 2026-09-10 / MIT（https://github.com/JimLiu/baoyu-skills）。`Owl-Listener/designer-skills` 2,649★ / pushed 2026-09-05 / MIT（https://github.com/Owl-Listener/designer-skills）。`code-on-sunday/slide-deck-generator` 146★ / pushed 2026-03-18（https://github.com/code-on-sunday/slide-deck-generator）は半年近く push が無く、追随していないものとして扱う。

## 候補

### baoyu-slide-deck

- 層: T4 / T5
- 提供元: JimLiu（個人）
- 取得元URL: https://skills.sh/jimliu/baoyu-skills/baoyu-slide-deck / https://github.com/JimLiu/baoyu-skills
- できること: 17種のスタイルプリセット、聞き手の指定（executives 等）、アウトライン→プロンプト→画像生成の段階分け、PPTX/PDF へのマージ。30.1K installs（https://skills.sh/jimliu/baoyu-skills/baoyu-slide-deck）と、この領域では最も使われている。
- 足りないこと: **出力がラスター画像**で、HTMLではない。SKILL.md 本文に「⛔ Never substitute SVG, HTML, canvas, or other code-based rendering for raster image generation」と明記されており、HTML出力は設計上の非対象。加えて (a) 画像生成バックエンド（Codex imagegen / GenerateImage 等）と `bun`/`npx` が前提、(b) 「reading and sharing 用で live presentation 用ではない」と自ら宣言しており、画面共有して喋る用途は対象外、(c) 意思決定を仰ぐ構成（今日決めること・選択肢・推奨・リスク）が無い、(d) 日本語の会議作法に関する記述が無い。
- 保守状況: 25,875★ / pushed 2026-09-10 / MIT / archived=false（https://github.com/JimLiu/baoyu-skills）。活発。
- 監査結果: 採用・派生しないため未実施。

### six-pager (ngmeyer)

- 層: T4
- 提供元: ngmeyer（個人）
- 取得元URL: https://skills.sh/ngmeyer/skills/six-pager / https://github.com/ngmeyer/skills
- できること: Amazon の6章構成（Introduction / Goals / Tenets / State of the Business / Lessons Learned / Strategic Priorities + Appendix）、PRFAQ モード、Strunk の散文規則による監査、premortem の必須化、`--silent-read` による黙読シミュレーション、語数からの概算ページ数チェック。**6-pager の構成論としては、調べた中で最も練られている。**
- 足りないこと: (a) 出力が `.md` ファイルで、HTMLを出さない（191行目で `--silent-read` の注記が HTML コメントに言及するのみ）。したがって投影・画面共有・図表・グラフのすべてが範囲外、(b) Strunk 準拠の**英語散文**が品質基準の本体で、日本語には直接効かない（450 words/page でのページ換算も日本語では成立しない）、(c) CSV やコードベースからの素材取り込みが無い、(d) 4★ のリポジトリで pushed 2026-07-29（https://github.com/ngmeyer/skills）と1か月半更新が無い。
- 保守状況: 4★ / pushed 2026-07-29 / MIT / archived=false（https://github.com/ngmeyer/skills）。実質的に個人の設定リポジトリで、保守の継続は期待しにくい。
- 監査結果: 採用・取り込みはしないが、**6章構成と premortem の必須化という骨格は borrow する価値がある**。MIT なので構成を参考にすること自体に制約は無い。owner は `ngmeyer`（User）で、ベンダーを騙る要素は無い。`scripts/` は無く SKILL.md 単体。skills.sh の監査表（https://skills.sh/audits）には未掲載＝未監査。

### presentation-creator (Sentry)

- 層: T2 / T5
- 提供元: Sentry（getsentry、ベンダー公式）
- 取得元URL: https://github.com/getsentry/skills/blob/main/skills/presentation-creator/SKILL.md
- できること: React + Vite + Recharts でスライドアプリを組み、**単一HTMLにバンドルして配布**する。「実データが無いならチャートを作るな（捏造禁止）」を明文化しているのは良い。
- 足りないこと: (a) **Sentry のブランドとデザインシステム専用**、(b) `npm install` とビルド工程が要る。単一HTMLファイル1枚を渡すだけの eli15 系の作法と噛み合わず、オフラインで即開ける成果物にならない、(c) 意思決定を仰ぐ構成が無い（narrative arc の例示のみ）、(d) 英語前提。
- 保守状況: 991★ / pushed 2026-09-07 / Apache-2.0 / archived=false（https://github.com/getsentry/skills）。活発。
- 監査結果: 採用・派生しないため未実施。

### presentation-deck (Owl-Listener)

- 層: T4 / T5
- 提供元: Owl-Listener（コミュニティのデザイナー向けコレクション）
- 取得元URL: https://skills.sh/owl-listener/designer-skills/presentation-deck / https://github.com/Owl-Listener/designer-skills
- できること: 発表の型（Stakeholder Update / Design Review / Final Showcase / Portfolio）と普遍構造（Hook→Context→Journey→Solution→Evidence→Ask）、聞き手別の調整（Executives / Engineers / Designers / Mixed）。2.5K installs（https://skills.sh/owl-listener/designer-skills/presentation-deck）。
- 足りないこと: **SKILL.md が41行の構成アドバイスのみで、成果物を1つも作らない。** HTML も画像もファイルも出さない。「Design for the back of the room (large text, high contrast)」のような原則は書いてあるが、それを実装する手段が無い。
- 保守状況: 2,649★ / pushed 2026-09-05 / MIT / archived=false（https://github.com/Owl-Listener/designer-skills）。活発。
- 監査結果: 採用・派生しないため未実施。

### eli15（自作・手元）

実行したクエリ:

```bash
cat /Users/yike/.claude/plugins/marketplaces/yike-skills/skills/eli15/SKILL.md
find /Users/yike/.claude/plugins/marketplaces/yike-skills/skills/eli15 -type f
```

- 層: T0
- 提供元: 自作（YIke23/skills、studio プラグイン）
- 取得元URL: /Users/yike/.claude/plugins/marketplaces/yike-skills/skills/eli15/SKILL.md
- できること: 単一HTML1枚、インラインSVG、Neobrutalism 固定（`assets/base.css`）、`scripts/check_contrast.py` によるコントラスト機械検証（SVG内の文字と下地の図形を座標から割り出す）、日本語の分量予算（1文60字・1段落3文・節3つまで）。**新スキル2本が流用すべき土台はここにある。**
- 足りないこと: (a) 読み手が**その場にいない**前提（一人で読み切る解説記事）。会議で行き来されることを想定した目次・節番号・戻り導線が無い、(b) 目的が「分かってもらう」で、**「決めてもらう」構成（今日決めること・決めないこと・選択肢・推奨・リスク・前提）が無い**、(c) 本文1,600字までの予算は6-pagerには小さすぎ、デッキ型には逆に大きすぎる、(d) 投影・画面共有を前提とした文字サイズや1画面あたりの情報量の規定が無い、(e) CSV からの表・グラフの作法が無い。
- 保守状況: 自作。随時更新可能。
- 監査結果: 自作のため不要（層 T0）。

### baoyu-markdown-to-html

- 層: T4 / T5
- 提供元: JimLiu（個人）
- 取得元URL: https://github.com/JimLiu/baoyu-skills/blob/main/skills/baoyu-markdown-to-html/SKILL.md
- できること: **md ファイルを入力にスタイル付きHTMLを出す**、という入出力が新前提と一致する唯一の候補。インラインCSS、コードハイライト、数式、Mermaid（headless Chrome で PNG 化）、PlantUML、脚注、外部リンクの末尾引用化。EXTEND.md によるテーマの永続設定を持つ。
- 足りないこと: (a) **WeChat 公式アカウント向けの整形が主目的**で、会議・投影・意思決定という文脈が一切無い、(b) **本文を書き換えない純粋なスタイラー**。md に Mermaid が書いてあれば図にするが、**散文から図を起こすことはしない**。「図が主役」は成立しない、(c) 1画面1論点のような画面分割の概念が無く、md を上から順に流すだけ、(d) `bun` / `npx` と headless Chrome が前提で、単一HTML1枚をオフラインで渡す作法と噛み合わない、(e) 中国語圏向けの前処理（Step 0 が中国語検出から始まる）。
- 保守状況: 25,875★ / pushed 2026-09-10 / MIT / archived=false（https://github.com/JimLiu/baoyu-skills）。活発。
- 監査結果: 採用・派生しないため未実施。

### baoyu-diagram

- 層: T4 / T5
- 提供元: JimLiu（個人）
- 取得元URL: https://github.com/JimLiu/baoyu-skills/blob/main/skills/baoyu-diagram/SKILL.md
- できること: **本文から図を起こす**。7種（Architecture / Flowchart / Sequence / Structural / Mind Map / Timeline / State Machine）それぞれに「いつ使うか」と型別のレイアウト指針を持ち、配色・タイポグラフィ・余白規則・SVGのレイヤ構造まで規定している。出力は自己完結の単一 `.svg`。**「内容の形に合わせて図の型を選ぶ」という発想は、作ろうとしているスキルAの中核と同じ。**
- 足りないこと: (a) **ダークテーマ固定**。投影・印刷・ライトモードを想定していない、(b) 出力が `.svg` 単体で、**1回の呼び出しで1枚**。md の章立てを追って各章に図を配り、HTMLページに組み込む導線が無い、(c) 資料としての文章・見出し・分量・可読性を一切扱わない（図だけを作る部品）、(d) コントラストの機械検証が無い。
- 保守状況: 25,875★ / pushed 2026-09-10 / MIT / archived=false（https://github.com/JimLiu/baoyu-skills）。活発。
- 監査結果: **図の型の選び方は borrow する価値がある**（MIT）。ただし eli15 が既に同種の対応表（順序→ステップ図、構造→入れ子ボックス、比較→2カラム、量→バー、分岐→樹形図、変化→before/after）をライト/ダーク両対応で持っているため、借用は「型の追加」程度に留まる見込み。owner は `JimLiu`（User）でベンダー詐称の要素は無い。`scripts/` に SVG→PNG 変換の TypeScript があり、`bun` 実行。今回は取り込まない。

## 結論

derive

- 採用元: eli15（自作・手元）

### 既存で満たせない点

- **「作成済み .md の章立てを保ったまま、会議用の単一HTMLに組み直す」スキルは、T0〜T5 のどこにも無かった。** 入出力が一致するのは `baoyu-markdown-to-html` だけで、それは WeChat 向けのスタイラーであり、散文から図を起こさない。図を起こす `baoyu-diagram` は単体 `.svg` を1枚出す部品で、md を追ってページに組む導線を持たない。**この2本の間が空いている。**
- **単一HTMLで「意思決定を仰ぐ」会議資料を出すスキルは、T0〜T5 のどこにも無かった。** 最も近い3本は、出力形式（baoyu=ラスター画像 / six-pager=Markdown）かブランド（Sentry専用）かで外れる。
- 調べた全候補に、**「今日決めること／決めないこと／選択肢／推奨／リスク／前提」という意思決定の骨格**が無い。six-pager の Goals・Tenets・Strategic Priorities が最も近いが、Markdown 出力で図表を持てない。
- 日本語の会議作法（分量の数え方、文の長さ、投影時の可読性）を扱うものが1本も無い。six-pager の品質基準は Strunk の英語散文で、450 words/page というページ換算も日本語では成立しない。
- **投影・画面共有で読める**ことを実装レベルで保証する仕組み（文字サイズ、コントラストの機械検証）を持つのは、手元の eli15 だけ。ただし eli15 自身は「一人で読み切る解説記事」用で、会議での行き来も意思決定も想定していない。
- CSV・コードベース・議事録という3種の素材から入る導線を持つものが無い。

### 借用の方針

- **baoyu-diagram から（MIT、図の型の選び方のみ）**: State Machine・Mind Map など eli15 の対応表に無い型を必要に応じて足す。実装は借りない（ダークテーマ固定・SVG単体出力のため）。
- **eli15 から**: 単一HTML1枚の作法、`assets/base.css`（Neobrutalism）、`scripts/check_contrast.py`、インラインSVGで図を描く方針、日本語の分量予算の考え方。
- **ngmeyer/six-pager から（MIT、構成のみ）**: 6章のナラティブ構成と、premortem を必須にする発想。借用元として SKILL.md に明記する。
