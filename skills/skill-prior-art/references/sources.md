# 層ごとの調べ先（T0〜T5）

`SKILL.md` の Step 1 の表に1対1で対応する。各層について「どこを見るか」「実際に打つ
コマンドかURL」「その層の注意点」を書く。末尾に、外部スキルを採用・派生するときの
**監査観点**（Step 2 の「監査結果」が参照している項目）を置く。

## このファイルの数値の扱い

**このファイルに書かれた星数・件数・最終更新日は、すべて 2026-09-08 に取得した値。**
エコシステムは週単位で動くので、レポートに数値を書くときは**この表を写さず、
その日に取り直す**こと。ここに載せているのは「どう取るか」の見本であって、
出典として再利用してよい値ではない。

確認できなかったものは「未確認」と明記してある。**未確認のものを、確認済みとして
レポートに書かない。**

## T0 — 手元

**最も多い重複はここ。** 自分が半年前に作ったものを忘れている。

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/search_local.sh <検索語> [検索語...]
```

英語3〜5個と日本語1〜2個を一度に渡す（OR で当たる）。終了コードは
0=候補なし / 1=候補あり。

**探すのはスキルだけではない。** スラッシュコマンド（`commands/*.md`）も同じ検索語で
走査する。照合するのはどちらもフロントマターまでで、本文は見ない。

| 種別 | 照合するもの |
|---|---|
| スキル | `SKILL.md` のフロントマターの `name` と `description` |
| スラッシュコマンド | `commands/<名前>.md` のフロントマターの `description` と、**ファイル名** |

コマンドのフロントマターには `name` が無い（ファイル名が名前を担う）。`description`
すら書かれていないものもある。だからファイル名自体を照合対象に入れている。
`clean_gone` のような名前は、それだけで何をするコマンドかの手掛かりになる。

スクリプトが探す場所は4つ。それぞれ `skills/` と `commands/` の両方を見る。
無い場所は黙って飛ばす。

| 場所 | 中身 |
|---|---|
| カレントリポジトリの `skills/` / `commands/`（`.claude/` 配下も） | 自作の実体 |
| `~/.claude/skills` / `~/.claude/commands` | 作業場。定常状態では空 |
| `~/.claude/plugins/cache/<marketplace>/<plugin>/<sha>/{skills,commands}` | プラグインの実体。**同じプラグインの古い sha が並ぶ** |
| Claude Desktop のプラグイン配下 | `local-agent-mode-sessions/` 以下。`skills-plugin/` 直下と `rpm/plugin_*/` の2通りの置き方が混在する |

注意点。

- **同名のスキルが複数の場所にあるのが普通。** プラグイン版と作業場版、古い sha の
  残骸が並ぶ。スクリプトは中身が同じものを1件にまとめ、「他N箇所」と表示する
- **スキルを持たず `commands/` だけのプラグインがある。** 公式の `commit-commands` が
  それで、`clean_gone` はここにいる。SKILL.md だけを数えていると、このプラグインは
  丸ごと視界に入らない
- 集計行は `探した場所 N / SKILL.md M 本 / コマンド C 本 / 候補 K 件`。候補の行には
  `（スキル）` / `（スラッシュコマンド）` が付く
- **コマンドは description が1文しかないことが多い。** スキル以上に、本文まで読まないと
  何をするか分からない
- **T0 に候補が無いことは、他の層に無いことを意味しない。** 終了コード 0 でも T1〜T5 は続ける
- 手元に無いが**過去に見た記憶がある**ものは、記憶ではなく T3・T4 で引き直す

## T1 — Anthropic 公式

公式は本体の挙動に追随して更新される。自作は追随しない。ここに同等品があるなら、
自作の理由はよほど強くないと立たない。

| 見るもの | URL | 2026-09-08 に見えたもの |
|---|---|---|
| スキル本体のリポジトリ | https://github.com/anthropics/skills | 175,042★ / 最終 push 2026-09-03。`skills/`（カテゴリ別）、`spec/`（Agent Skills 仕様）、`template/`、`.claude-plugin/` |
| 公式プラグインの marketplace | https://github.com/anthropics/claude-plugins-official | 36,019★ / 最終 push 2026-09-07。`plugins/`（Anthropic 内製）と `external_plugins/`（第三者）に分かれる |
| 内蔵スキル | このセッションで生えているもの | `/plugin` の一覧、および `ListSkills` 相当の一覧で確認する |

```bash
# 名前で当たりを付ける
gh search code --repo anthropics/skills --filename SKILL.md <検索語>
# リポジトリの現況（星数・最終 push はここで取る。記憶で書かない）
gh api repos/anthropics/skills --jq '"\(.stargazers_count)★ pushed=\(.pushed_at)"'
```

注意点。

- **ライセンスが一様ではない。** 大半は Apache 2.0 だが、`docx` / `pdf` / `pptx` /
  `xlsx` の文書系は source-available（オープンソースではない）と明記されている。
  派生・取り込みの前に必ず個別に確認する
- `claude-plugins-official` の `external_plugins/` は Anthropic 内製ではない。
  「公式リポジトリに入っている」ことと「Anthropic が書いた」ことは別
- 内蔵スキルは環境によって生えているものが違う。**自分のセッションで見えている一覧が正**

## T2 — 作業対象サービスのベンダー公式

**最も見落とされ、最も効く層。** 既存サービス上の作業をスキル化しようとしているなら、
そのサービス自身が公式スキルを出していないかを必ず確認する。

### 探し方（ここが本体。一覧を覚えない）

**リポジトリ名が揃っていない。** `skills` のこともあれば `agent-skills` のこともあり、
別のリポジトリに同梱されていることもある。名前を決め打ちで叩くと取りこぼす。

```bash
# 1. そのベンダーの GitHub Organization を横断で見る（最初にこれ）
gh search repos --owner <vendor> skill --limit 10 \
  --json fullName,description,stargazersCount

# 2. 名前の候補を直接叩く（存在確認だけなら速い）
for r in <vendor>/skills <vendor>/agent-skills; do
  gh api "repos/$r" --jq .full_name 2>/dev/null || echo "404 $r"
done

# 3. 公式ドキュメント側から辿る
#    <docs ドメイン> の検索窓で "skill" / "agent skill" / "Claude"
```

さらに2つ、リポジトリ以外の配り方がある。

- **MCP サーバーがスキルを配っている場合がある。** ベンダーの MCP サーバーを接続すると、
  その中からスキルが生える形。このセッションでも Figma の MCP サーバーが
  `figma-use` などのスキルを、Notion の MCP サーバーがスキル検索のツールを出している
  （2026-09-08 に、このセッションのツール一覧で確認）
- **CLI やSDKのリポジトリに同梱**されている場合がある。例: `googleworkspace/cli`
  （30,772★）は説明文に "Includes AI agent skills" とある（2026-09-08 確認。
  中身のスキル名までは未確認）

### 確認できた例（2026-09-08 時点。網羅ではない）

`gh api repos/<name>` で存在と最終 push を確かめたもの。

| ベンダー | リポジトリ | ★ | 最終 push |
|---|---|---|---|
| Supabase | `supabase/agent-skills` | 2,584 | 2026-08-12 |
| Vercel | `vercel-labs/agent-skills` | 30,942 | 2026-08-28 |
| Cloudflare | `cloudflare/skills` | 2,797 | 2026-09-06 |
| Sentry | `getsentry/skills` | 985 | 2026-09-07 |
| Expo | `expo/skills` | 2,507 | 2026-09-07 |
| Hugging Face | `huggingface/skills` | 11,023 | 2026-09-03 |
| Trail of Bits | `trailofbits/skills` | 7,011 | 2026-09-02 |
| OpenAI | `openai/skills` | 26,047 | 2026-07-14 |
| Microsoft | `microsoft/skills` | 2,999 | 2026-09-07 |
| Angular | `angular/skills` | 636 | 2026-09-04 |
| Neon | `neondatabase/agent-skills` | 86 | — |
| HashiCorp | `hashicorp/agent-skills` | 865 | — |

Supabase を例に取ると、README は3通りの入れ方を書いていた（2026-09-08 確認）。

```bash
npx skills add supabase/agent-skills                      # 全部
npx skills add supabase/agent-skills --skill supabase     # 1本だけ
claude plugin install supabase@supabase-agent-skills      # プラグインとして
```

### 二次情報の一覧は、当たりを付ける用途にしか使えない

`VoltAgent/awesome-agent-skills` のような「公式スキル一覧」は出発点として便利だが、
**そこに書かれたパスをそのまま信じてはいけない。** 2026-09-08 に照合したところ、

- Supabase は `supabase/skills` と書かれていたが、実物は `supabase/agent-skills`
- Neon は `neondatabase/skills` と書かれていたが、実物は `neondatabase/agent-skills`
- HashiCorp は `hashicorp/skills` と書かれていたが、実物は `hashicorp/agent-skills`
- Stripe は `stripe/skills`、Netlify は `netlify/skills` と書かれていたが、**どちらも 404。**
  `gh search repos --owner stripe` / `--owner netlify` でも公式スキルのリポジトリは
  見つけられなかった（**確認できなかった**。無いとは言い切れない）

一覧で当たりを付け、**必ず `gh api` で実在を確かめてからレポートに書く。**

## T3 — Claude マーケットプレイス

審査があり、`/plugin update` で更新が届く。

| 見るもの | 入口 |
|---|---|
| Claude Code から | `/plugin` → Discover |
| ブラウザから | https://claude.com/plugins |
| 公式 marketplace の中身を直接 | https://github.com/anthropics/claude-plugins-official |

```bash
/plugin install <plugin-name>@claude-plugins-official
```

2026-09-08 に https://claude.com/plugins で見えたもの。

- インストール数つきの一覧、検索、対応先（Claude Code / Cowork）での絞り込み
- **「Anthropic verified」バッジ**がある。バッジの有無が審査の有無に対応する
- FAQ が「信頼できる開発者のものだけ入れること」「コミュニティ製は未検証の第三者
  ソフトウェアを入れることがある」と明記している

注意点。

- **バッジの無いものは審査済みではない。** T4 と同じ扱いで中身を読む
- 第三者プラグインの掲載は申請制で、提出フォームが
  https://clau.de/plugin-directory-submission にある（2026-09-08 確認）
- ブラウザの一覧と `/plugin` → Discover が同一の索引かどうかは**未確認**

## T4 — skills.sh レジストリ

網羅性は最大。**ただし中身を読むまで信用しない。**

| 見るもの | URL |
|---|---|
| 索引 | https://skills.sh |
| 監査結果 | https://skills.sh/audits |

```bash
npx skills find <キーワード>          # 検索
npx skills add <owner/repo>          # 入れる（--skill <name> で1本だけ）
npx skills list                      # 手元に入っているものを見る
```

`npx skills` の実体は `vercel-labs/skills`（30,623★ / 最終 push 2026-09-06、
2026-09-08 確認）。`add` / `use` / `list`(`ls`) / `find` / `update` / `remove`(`rm`) /
`init` のサブコマンドがある。

2026-09-08 に見えたもの。

- トップの Skills Leaderboard に **1,376,738**（"All Time"）と表示されていた。
  これが「登録スキル数」なのか集計上の別の指標なのかは**未確認**。桁として
  「手作業では見切れない量」とだけ理解して使う
- `/audits` に **Gen Agent Trust Hub / Socket / Snyk** の3社の結果を並べた表がある。
  Safe / Low Risk / Medium Risk / Critical で分類されている
- **その表のカバレッジは部分的。** 表示されていた50件のうち、相当数が3社とも
  "Pending" のままだった。**監査結果が無い＝安全、ではない**

注意点。

- **掲載自体に事前審査があるかどうかは確認できなかった。** ただし監査が
  「後から付く / まだ付いていない」形で運用されているのは上のとおりなので、
  掲載されていることを品質の根拠にしない
- 検索で当たった時点では候補でしかない。SKILL.md 本文と `scripts/` を読むまで
  レポートに「使える」と書かない

## T5 — 著名企業・著名個人の公開スキル

保守が続く見込みが立つ、というだけの層。**公式ではない。**

```bash
gh search repos "agent-skills" --limit 20 --json fullName,stargazersCount,description
gh search code --filename SKILL.md <検索語> --limit 20
```

星数の多い個人・コミュニティのコレクションが多数ある（2026-09-08 の
`gh search repos "agent-skills"` で確認）。星数は人気であって審査ではない。

見るのは星数より次の3つ。

- **最終 push**（`gh api repos/<name> --jq .pushed_at`）
- **issue が生きているか**（放置されたリポジトリは仕様変更に追随しない）
- **ライセンス**（派生するなら必須。`gh api repos/<name> --jq .license.spdx_id`）

## 外部スキルを採用・派生するときの監査観点

`SKILL.md` Step 2 の「**監査結果** — 外部スキルを採用・派生する場合は必須」が参照する
のはこの節。**レポートに、次の項目を1つずつ書く。**

### 1. 誰が出しているか

- Organization がそのベンダー本体か、似た名前の第三者か。
  `gh api repos/<name> --jq '.owner.login, .owner.type'` で確認する
- ベンダー公式を騙る取り違えが最も危ない。**ドキュメント側からリンクを辿って
  一致するかを見る**（リポジトリ側の自称だけで判断しない）

### 2. 何を実行するか

```bash
# 同梱スクリプトを全部数え、中身を読む
find <skill-dir> -type f \( -name '*.py' -o -name '*.sh' -o -name '*.js' \) | xargs wc -l
```

- **`scripts/` が無いスキルは読む量が少ない。** 逆に大量にあるなら全部読むまで採用しない
- ネットワークに出るか（`curl` / `requests` / `fetch` / `urllib`）
- 資格情報に触るか（`~/.aws`、`~/.ssh`、`.env`、`gh auth token`、キーチェーン）
- 消す操作があるか（`rm -rf`、`git reset --hard`、`--force`）
- フロントマターの `allowed-tools` が何を許しているか

### 3. 保守されているか

- `gh api repos/<name> --jq '"\(.pushed_at) open_issues=\(.open_issues_count) archived=\(.archived)"'`
- 半年以上 push が無いなら、仕様変更に追随していないものとして扱う

### 4. ライセンスが用途に合うか

- `gh api repos/<name> --jq .license.spdx_id`
- **T1 の Anthropic 公式ですら一様ではない**（文書系は source-available）。
  「公式だから自由に取り込める」と決めつけない

### 5. 第三者の監査結果があるか

- https://skills.sh/audits に載っているか。**載っていない場合は「未監査」であって
  「安全」ではない**
- 載っていても Pending なら結果は出ていない

### 採用の線引き

**外部スキルを勝手にインストールしない。** レポートに上の5項目を書いて並べ、
入れるかどうかはユーザーが選ぶ。ユーザーが `vendor`（取り込んで差分を当てる）を
選んだ場合の手順は `SKILL.md` の Step 3 を見る。
