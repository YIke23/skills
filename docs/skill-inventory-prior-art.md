# 先行事例調査レポート: セッションのスキル一覧表 + ローカル/GitHub 更新差分

## 調査日

2026-09-10

## 何を探したか

現在の Claude Code セッションで使えるスキル（harness 組み込み・`~/.claude/skills` のユーザースキル・
CLI プラグイン・デスクトップアプリのプラグイン／`anthropic-skills` 合成プラグインの全系統）を
出自つきの表にまとめ、同時に mac 上の実体と GitHub 上の正（marketplace のリモート）との
更新差分を示す。触る対象は Claude Code のプラグイン機構そのもの（`claude plugin` CLI と git）。

### 検索語

- 英語: claude code skill inventory, list installed skills table, skill audit staleness, plugin version drift, skills sync local remote
- 日本語: スキル一覧 表, スキル 更新差分

## 調査を省略した理由

なし

## 調査した層

### T0 — 手元

実行したクエリ:

```bash
bash ~/.claude/plugins/marketplaces/yike-skills/skills/skill-prior-art/scripts/search_local.sh \
  inventory list audit sync drift 一覧 差分
```

結果: 探した場所 25 / SKILL.md 159 本 / 候補 3 件。中身は `git-commit`（「差分」がコミット
差分の意味で誤ヒット）、`accessibility-review` と `design-system`（"audit" が WCAG 監査・
デザインシステム監査の意味で誤ヒット）。**スキル台帳・スキル一覧・更新差分を扱うものは手元に無い。**

副産物として、今回の対象そのものである事故が手元で1件見つかった。
`~/.claude/skills/skill-prior-art/` は `SKILL.md` だけで、GitHub 側（`YIke23/skills`）にある
`references/sources.md` / `scripts/check_report.py` / `scripts/search_local.sh` / `assets/report.md`
が欠けている。ローカルとリモートの構成差が、本人にも気づかれずに残っていた。

### T1 — Anthropic公式

実行したクエリ:

```bash
gh api repos/anthropics/skills --jq '"\(.stargazers_count)★ pushed=\(.pushed_at)"'
gh api repos/anthropics/skills/contents/skills --jq '.[].name'
gh api repos/anthropics/claude-plugins-official/contents/plugins --jq '.[].name'
gh search code --repo anthropics/skills --filename SKILL.md "skills" --limit 10
```

結果: `anthropics/skills` は https://github.com/anthropics/skills で ★175,440 / pushed 2026-09-03。
同梱スキルは academy-guide, algorithmic-art, brand-guidelines, canvas-design, claude-api,
discernment-nudge, doc-coauthoring, docx, frontend-design, internal-comms, mcp-builder, pdf,
pptx, skill-creator, slack-gif-creator, theme-factory, web-artifacts-builder, webapp-testing, xlsx
の19本。**スキル台帳・一覧・更新差分を扱うものは無い。**

`anthropics/claude-plugins-official`（https://github.com/anthropics/claude-plugins-official 、
★36,087 / pushed 2026-09-09）の `plugins/` にはプラグイン40個。うちスキル機構に近いのは
`plugin-dev` だが、中身は agent-development / command-development / hook-development /
mcp-integration / plugin-settings / plugin-structure / skill-development の7本で、
すべて**プラグインを「作る」側**の解説。既に入っているものを棚卸しする機能は無い。
`claude-code-setup` も導入ガイドで、一覧化は担当していない。

ライセンスは `gh api repos/anthropics/skills --jq .license.spdx_id` が `null`（SPDX 判定なし）。
派生するなら個別確認が必要。

### T2 — ベンダー公式

対象サービスは Claude Code 自身なので、ベンダー = Anthropic。リポジトリではなく
**本体 CLI と組み込みコマンドが一次情報**になるため、そちらを直接叩いた。

実行したクエリ:

```bash
"$CLAUDE_CODE_EXECPATH" plugin --help
"$CLAUDE_CODE_EXECPATH" plugin list --json
"$CLAUDE_CODE_EXECPATH" plugin list --available --json
"$CLAUDE_CODE_EXECPATH" plugin marketplace list --json
"$CLAUDE_CODE_EXECPATH" plugin details --help
strings "$CLAUDE_CODE_EXECPATH" | grep -o skill-doctor
```

結果: 要件の**部品はすべて公式にある**。ただし要件そのものを満たすものは無い。

| 公式の手段 | 何を返すか | 要件との差 |
|---|---|---|
| `plugin list --json` | 導入済みプラグインの id / version(SHA) / installPath / lastUpdated | プラグイン単位。**スキル単位の一覧にならない** |
| `plugin list --available --json` | `{installed, available}` の2配列 | marketplace 側との差の材料になるが、SHA の新旧比較は自前 |
| `plugin details <name>` | 1プラグインのコンポーネント内訳と想定トークン量 | **1個ずつ**。横断の表にならない |
| `plugin marketplace list --json` | marketplace 名 / source / url / installLocation | GitHub の URL は取れるが、差分は取らない |
| `plugin marketplace update` | リモートから marketplace を更新 | 更新はするが**差分を見せない** |
| `/skill-doctor`（組み込み。バイナリ内に文字列を確認） | スキルの診断レポート | 単体スキルの健全性寄り。3系統横断の台帳ではない |

**決定的な差が2つある。**

1. `plugin list` は**デスクトップアプリ側のスキル／プラグインを1件も返さない**。
   このセッションには `anthropic-skills:*`（claude.ai 側で有効化したスキルを合成した
   プラグイン）、`design:*`、`natural-japanese:*`、`cowork-plugin-management:*` が生えているが、
   `plugin list --json` が返したのは commit-commands / example-skills / git-flow / studio の4件だけ。
   実体は `~/Library/Application Support/Claude/local-agent-mode-sessions/<session>/<sub>/rpm/plugin_*/`
   に展開される（`~/.claude/projects/-Users-yike/memory/desktop-plugins-live-in-rpm.md` に
   2026-09-05 の実測として記録済み）。公式 CLI だけで一覧を作ると**半分以上が抜ける**。
2. **GitHub との更新差分を出す公式手段が無い。** `marketplace update` は更新してしまうので、
   「今どれだけ遅れているか」は消えてしまう。差分を見るには marketplace の
   git チェックアウト（`~/.claude/plugins/marketplaces/<name>/`）に対して自前で
   `git fetch` + `rev-list --left-right --count` を打つ必要がある。

なお `plugin list --json` の `version` は semver ではなく **git SHA**（例: `studio@yike-skills` が
`583eb49ce025`）。同じ marketplace の HEAD は `917acae` だったので、この環境には
実際に「marketplace は最新だが導入済みキャッシュが古い」状態が存在していた。

### T3 — マーケットプレイス

実行したクエリ:

```bash
"$CLAUDE_CODE_EXECPATH" plugin list --available --json   # {installed, available} を全走査
```

結果: 設定済み marketplace は anthropic-agent-skills / claude-plugins-official / yike-skills の3つ。
`available` 側を skill / audit / invent / doctor / drift / stale で機械的に絞ったが**該当なし**。
Discover 相当の索引にスキル棚卸し系プラグインは載っていなかった。

### T4 — skills.sh

実行したクエリ:

```bash
npx --yes skills find "skill inventory"
npx --yes skills find "list skills"
```

結果: **該当なし。** "skill inventory" は在庫管理（EC・倉庫・Shopify・Amazon）の
スキルに全部吸われ、"list skills" は UI スタイルや CLI 系の無関係なスキルが並んだ。
レジストリの検索語としては「スキルの棚卸し」が在庫管理と衝突して機能しない。
表示された上位はいずれも https://skills.sh 配下だが、要件に関係するものは1件も無かった。

### T5 — 著名企業・個人

実行したクエリ:

```bash
gh search repos "claude code skill audit" --limit 10 --json fullName,stargazersCount,description
gh search code --filename SKILL.md "plugin list --json" --limit 15
gh api repos/<name> --jq '"★\(.stargazers_count) pushed=\(.pushed_at) license=\(.license.spdx_id)"'
```

結果: **ここに近縁が3件あった。** 下の「候補」に展開する。
`gh search code --filename SKILL.md "plugin list --json"` の側は、doctor 系の名前が並んだものの
（`spotify/portal-ai-plugins@doctor`、`beefiker/superloopy@superloopy-doctor` 等）
いずれも各製品の自己診断で、Claude Code のスキル台帳ではなかった。

## 候補

### shimo4228/skill-stocktake

- 層: T5
- 提供元: shimo4228（個人）
- 取得元URL: https://github.com/shimo4228/skill-stocktake （★2 / pushed 2026-09-02 / MIT）
- できること: 導入済みスキルをひとつずつ評価し `Keep / Improve / Update / Retire / Merge / Out of scope`
  の判定を付ける。構造的な事前検査（存在しないパスの検出、symlink で外部所有のスキルの除外）、
  transcript から使用回数を出す `usage_stats.py`、参照URLの死活チェックを持つ。
  判定後は skill-creator に引き渡す設計で、境界が明確。要件のうち「一覧を作る」部分は重なる。
- 足りないこと: (1) 列挙対象が `~/.claude/skills/*/SKILL.md` と `{cwd}/.claude/skills/*/SKILL.md`
  だけで、**プラグイン由来のスキルをまったく見ない**。今回の要件の中心である「プラグイン含む」が丸ごと外。
  デスクトップの `rpm/` 系統も当然対象外。(2) **GitHub との更新差分を扱わない。** `Update` 判定は
  「中身が古びている」という質の判断で、リモートの HEAD との比較ではない。(3) 出力は品質判定の
  レポートで、出自つきの一覧表ではない。(4) 自前の `results.json` 台帳と、同作者の別スキル
  `skill-health` / `uv` プロジェクトへの依存があり、単体では動かない。
- 保守状況: pushed 2026-09-02（8日前）で生きている。open issues 0、archived でない。
  ただし星数は少なく（上の取得元URLの値）、作者1人のリポジトリ。
- 監査結果: 同梱スクリプトは `scripts/usage_stats.py` と `hooks/log-skill-usage.sh` と
  `scripts/sync-from-local.sh`。SKILL.md 本文が transcript（`~/.claude/projects/**/*.jsonl`）を
  読む前提で、**セッション履歴という機微な入力に触れる**。ネットワークには
  `url_liveness`（参照URLの死活確認）で外に出る。ライセンスは MIT で派生可。
  https://skills.sh/audits に掲載は確認できず（**未監査**であって安全の意味ではない）。
  破壊的操作（`rm -rf` / `git reset --hard`）は tree 上のスクリプト名からは見当たらないが、
  採用するなら `usage_stats.py` 本文を通読する必要がある（今回は tree と SKILL.md 本文までを確認）。

### eliransu/skill-tax

- 層: T5
- 提供元: eliransu（個人）
- 取得元URL: https://github.com/eliransu/skill-tax （★5 / pushed 2026-05-12 / MIT）
- できること: 導入済みスキルの「セッションあたりトークン税」を測り、transcript から実使用を
  掘り起こして、削除候補をランク付けする（`audit` / `usage` / `report` の3コマンド）。
  一覧を機械的に集める発想は要件と重なる。
- 足りないこと: (1) **スキルではない。** リポジトリは `skill_tax.py` 単体で、SKILL.md が無い。
  Claude Code のスキルとして発動しない。(2) 軸がトークンコストと未使用検出で、**出自別の一覧表を作らない**。
  (3) **GitHub との更新差分を扱わない。** (4) プラグイン由来を含むかは README からは読み取れず未確認。
- 保守状況: pushed 2026-05-12。**約4ヶ月更新なし。** Claude Code のプラグイン機構は
  この間に変わっているため、追随していないものとして扱う。open issues 0。
- 監査結果: Python 1ファイル（`skill_tax.py`）のみで読む量は少ない。`tiktoken` を任意依存とし、
  無ければ chars/4 で近似する。README は「何も削除しない、推奨だけ」と明記。
  transcript を読むため機微な入力に触れる。ライセンス MIT。
  https://skills.sh/audits に掲載は確認できず（未監査）。

### agentcrew-academy/cc-audit

- 層: T5
- 提供元: agentcrew-academy
- 取得元URL: https://github.com/agentcrew-academy/cc-audit （★13 / pushed 2026-04-05 / ライセンス表記なし）
- できること: Claude Code 設定全体の健診。既定モデル、hooks、MCP 一覧、CLAUDE.md / rules の行数
  （膨張点の検出）、直近5セッションの JSONL から context 使用率を出す。
- 足りないこと: (1) スキルの扱いが `ls ~/.claude/skills/` **1行だけ**。プラグイン由来も、
  出自の区別も、表もない。(2) **GitHub との更新差分を扱わない。** (3) 対象が設定全体なので、
  スキル台帳としての解像度が要件に足りない。
- 保守状況: pushed 2026-04-05。**約5ヶ月更新なし。** open issues 0。
- 監査結果: **ライセンス表記が無い**（`gh api ... --jq .license.spdx_id` が `none`）。
  取り込み・派生には使えない。同梱は SKILL.md と README のみでスクリプト無し、
  本文の Bash / Python はすべて読み取り専用（`cat` / `wc` / JSONL の集計）。
  ネットワークは `allowed-tools` に WebSearch / WebFetch を許しているが本文では未使用。
  https://skills.sh/audits に掲載は確認できず（未監査）。

## 結論

build-new

- 採用元: なし

### 既存で満たせない点

- **プラグイン由来のスキルを列挙する候補が1つも無い。** 3件すべてが `~/.claude/skills/` を見るだけで、
  CLI プラグイン（`~/.claude/plugins/cache/<marketplace>/<plugin>/<sha>/skills/`）と
  デスクトップアプリのプラグイン（`local-agent-mode-sessions/<session>/<sub>/rpm/plugin_*/skills/`）、
  および `anthropic-skills` 合成プラグインを見ない。今回の要件の中心が丸ごと未対応。
- **ローカルと GitHub の更新差分を扱う候補が1つも無い。** T2 の公式 CLI も含めて、
  「marketplace の git チェックアウトを `git fetch` してリモートとの ahead/behind を出す」
  「導入済みキャッシュの SHA が marketplace の HEAD より古いことを検出する」手段が無い。
  この環境には実際に `studio@yike-skills` が古い SHA のまま残っている状態があった。
- **同一スキルが複数系統に重複してロードされていることを検出する候補が無い。** この環境では
  `skill-prior-art` が素の名前（`~/.claude/skills/`）と `anthropic-skills:skill-prior-art` の
  2系統で同時に生えており、かつローカル側は参照ファイル群が欠けた不完全な状態だった。
  出自の列を持たない既存候補の出力形式では、この状態を表現できない。
- **skill-stocktake は質の判定器で、台帳ではない。** 判定に LLM の per-item 判断を要するため
  実行が重く、「今どれが使えるのか」を一覧したいだけの用途に対して過剰。
  逆に台帳側の要件（出自・名前空間・更新差分）は持っていない。
- 残る2件は保守が4〜5ヶ月止まっており、うち `cc-audit` はライセンス表記が無いため
  取り込み・派生の対象にできない。
