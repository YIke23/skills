# 先行事例調査レポート: PR のマージとマージ後のブランチ後始末

## 調査日

2026-09-12

## 何を探したか

GitHub の Pull Request をマージし、マージ後にリモートとローカルの作業ブランチ、および
紐づく worktree を後始末する。「PRマージして」で発動し、触る対象は GitHub（`gh`）と git。

### 検索語

- 英語: pr merge, merge pull request, delete branch after merge, git branch cleanup, worktree cleanup
- 日本語: PRマージ, ブランチ削除

## 調査を省略した理由

なし

## 調査した層

### T0 — 手元

実行したクエリ:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/search_local.sh \
  "pr merge" "merge pull request" "delete branch" "branch cleanup" "worktree" "PRマージ" "ブランチ削除"
```

結果: 探した場所 34 / SKILL.md 251 本 / 候補 0 件（exit 0）。

**ただしこの 0 は信用してはいけない。** `search_local.sh` が照合するのは SKILL.md の
frontmatter だけで、**スラッシュコマンド（`commands/*.md`）を1件も見ない**。手で追ったところ、
要件の後半をほぼ満たす `clean_gone` が手元に導入済みだった（下の候補に展開）。

```bash
find ~/.claude/plugins -iname "*clean_gone*"
# → .../claude-plugins-official/commit-commands/*/commands/clean_gone.md
```

> **2026-09-13 追記: この取りこぼしは修正した。** `search_local.sh` は `commands/*.md`
> も走査するようになった（[#24](https://github.com/YIke23/skills/pull/24)）。コマンドの
> frontmatter には `name` が無いため、`description` とファイル名の両方で照合する。
> 集計行に「コマンド N 本」が出て、候補には `（スキル）` / `（スラッシュコマンド）` が付く。
> **上の検索語をそのまま渡すと `/clean_gone` が候補に出る（exit 1）。**
> 根は照合ではなく探す場所の集め方にあった。`skills/` という名前のディレクトリしか
> 拾っていなかったので、`skills/` を持たず `commands/` だけの `commit-commands` は
> 走査の対象に入る前から視界の外にいた。0 件の内訳（`探した場所 34 / SKILL.md 251 本`）は
> 2026-09-12 時点の記録としてそのまま残してある。

自作スキル側（`~/dev/skills/skills/`）には、マージも後始末も担当するものは無い。
`create-pr` と `release-pr` は本文中で「このスキルはマージしない」と明示的に持ち場から外している。

### T1 — Anthropic公式

実行したクエリ:

```bash
gh api repos/anthropics/skills --jq '"\(.stargazers_count)★ pushed=\(.pushed_at) license=\(.license.spdx_id)"'
gh api repos/anthropics/claude-plugins-official/contents/plugins --jq '.[].name'
gh search code --repo anthropics/claude-plugins-official "gh pr merge" --limit 15
```

結果: `anthropics/skills` は 175,917★ / pushed 2026-09-10 / license 判定 null
（https://github.com/anthropics/skills ）。`claude-plugins-official` は 36,162★ /
pushed 2026-09-12 / Apache-2.0（https://github.com/anthropics/claude-plugins-official ）で、
`plugins/` に 40 個。

`gh search code --repo anthropics/claude-plugins-official "gh pr merge"` は **0 件**。
公式プラグインのどこにも `gh pr merge` を実行するものは無い。PR 系に見える
`feature-dev` / `pr-review-toolkit` / `code-review` はいずれも作成とレビューまでで、
マージは担当していない。`commit-commands@commit-push-pr` も `gh pr create` で終わる。

**後始末側だけは公式にある。** `commit-commands@clean_gone`（下の候補）。

### T2 — ベンダー公式

作業対象サービスは GitHub。

実行したクエリ:

```bash
gh search repos --owner github skill --limit 10 --json fullName,description,stargazersCount
for r in github/skills github/agent-skills github/gh-skills cli/skills; do gh api "repos/$r" --jq .full_name; done
gh search code --repo github/copilot-plugins "pr merge" --limit 10
gh search code --repo github/awesome-copilot "gh pr merge --delete-branch" --limit 10
```

結果: **GitHub は Claude 向けの公式スキルを出していない。** `github/skills`・
`github/agent-skills`・`github/gh-skills`・`cli/skills` はいずれも 404。
Organization 横断で引っかかるのは Copilot 向けの2つ
（`github/copilot-plugins` 359★ / MIT / pushed 2026-08-31、
https://github.com/github/copilot-plugins 、および `github/awesome-copilot` 38,927★、
https://github.com/github/awesome-copilot ）。どちらもコード検索で
`pr merge` / `gh pr merge --delete-branch` に **該当なし**。

なお GitHub 本体としての一次情報は CLI 側にあり、`gh pr merge --delete-branch` が
リモートとローカルの両方を消す挙動はそこで保証されている。スキルではなくフラグとして
提供されている、というのがこの層の結論。

### T3 — マーケットプレイス

実行したクエリ:

```bash
"$CLAUDE_CODE_EXECPATH" plugin list --available --json   # available 297 件を merge/branch clean/worktree で全走査
```

結果: available 297 件のうち該当は3件で、いずれも要件と別物。
`gitlab`（GitLab の merge request。GitHub ではない）、
`mergify`（Mergify のマージキュー製品の CLI。`gh pr merge` ではなく同社サービスの操作）、
`oracle-ai-data-platform-workbench-engineer-agent`（誤ヒット）。
**素の GitHub PR をマージして後始末するプラグインは無い。**

### T4 — skills.sh

実行したクエリ:

```bash
npx --yes skills find "merge pull request"
npx --yes skills find "delete branch after merge"
npx --yes skills find "git branch cleanup worktree"
```

結果: **この層に候補が集中していた。** 上位は
`owainlewis/blueprint@task-to-pr` 310 installs、`adeonir/agent-skills@git-helpers` 185 installs、
`deevus/tea-skills@merge-pull` 93 installs、`toy-crane/skills@merge` 28 installs、
`patinaproject/skills@merge-pr` 24 installs、`chann/skills@git-branch-cleanup` 44 installs、
`ulpi-io/skills@git-merge-expert-worktree` 152 installs、
`timschoch/mattpocock-skills@cleanup-merged-branches` 68 installs
（インストール数はいずれも https://skills.sh の各ページ表示。例:
https://skills.sh/toy-crane/skills/merge 、 https://skills.sh/chann/skills/git-branch-cleanup ）。

本文まで読んだのは下の候補3件。読んだうえで落としたものを記録しておく。

- `deevus/tea-skills@merge-pull` — 本文は `tea pulls merge` / `tea pulls clean` で、
  **Gitea/Forgejo 専用**。GitHub では動かない（https://github.com/deevus/tea-skills 、9★、
  pushed 2026-05-30、MIT）
- `patinaproject/skills@merge-pr` と `timschoch/mattpocock-skills@cleanup-merged-branches` —
  **レジストリの掲載が実体より古い。** 両リポジトリの tree を `recursive=1` で引いたが、
  その名前のスキルは存在しなかった（patinaproject 側にあるのは
  `resolving-merge-conflicts` / `fix-merge-conflicts` / `move-branch-here`）。
  skills.sh の検索結果は存在確認になっていない

### T5 — 著名企業・個人

実行したクエリ:

```bash
gh search repos "claude skill merge pull request cleanup" --limit 8 --json fullName,stargazersCount,description
```

結果: **0 件。** T4 で挙がった候補はいずれも★が1桁〜十数（下の候補に個別に記載）で、
保守の継続性を星数や組織で担保できるものは無かった。

## 候補

### commit-commands@clean_gone（Anthropic 公式スラッシュコマンド）

- 層: T1
- 提供元: Anthropic（`anthropics/claude-plugins-official` の `commit-commands` プラグイン）
- 取得元URL: https://github.com/anthropics/claude-plugins-official/tree/main/plugins/commit-commands
  （リポジトリは 36,162★ / Apache-2.0 / pushed 2026-09-12、https://github.com/anthropics/claude-plugins-official ）
- できること: **要件の後半をほぼ完全に満たす。** `git branch -v` の `[gone]`（リモートが
  消えたブランチ）を拾い、`+` 接頭辞の付いた worktree 付きブランチは
  `git worktree remove --force` を先に走らせてから `git branch -D` する。
  squash マージで `-d` が拒否される問題を `[gone]` 判定 + `-D` で回避できている。
  **会社Mac に導入済み**（`commit-commands@claude-plugins-official` が有効）。
- 足りないこと: (1) **マージしない。** 掃除専門で、`gh pr merge` も `--delete-branch` も無い。
  (2) 起点が `[gone]` なので、**リモートがまだ生きている段階では何もできない**。
  「マージした直後にリモートとローカルを両方消す」という要件の本体は守備範囲外。
  (3) `[gone]` は「マージされた」ではなく「upstream が消えた」なので、マージされていない
  ブランチのリモートを誰かが消していた場合も無言で `-D` する。マージ済みかの照合は無い。
- 保守状況: 公式リポジトリの一部として pushed 2026-09-12。生きている。
- 監査結果: スラッシュコマンド1枚（`commands/clean_gone.md`）で、中身は上記の bash のみ。
  ネットワークに出ない。`git worktree remove --force` と `git branch -D` という**不可逆な
  操作を確認なしで一括実行する**点は把握しておく必要がある。Apache-2.0。

### toy-crane/skills@merge

- 層: T4
- 提供元: toy-crane（個人）
- 取得元URL: https://skills.sh/toy-crane/skills/merge （28 installs）/
  https://github.com/toy-crane/skills （3★ / MIT / pushed 2026-09-10 / open issues 1 / archived でない）
- できること: **要件に最も近い唯一の候補。** コミット → 同期 → push → PR の作成または再利用 →
  検証付きマージ → **リモートが `MERGED` を返してから** worktree とブランチを掃除 →
  ベースのチェックアウトをマージ後の状態に追従、までを一連の流れで通す。
  rebase と squash を「独立した意味のあるコミットか」で選び分ける方針を持つ。
  worktree を消す前に `scripts/stop-worktree-server.sh` で dev サーバーを止める同梱スクリプトがある。
- 足りないこと: (1) **コミットと PR 作成を丸ごと抱え込む。** 本文に "Complete the necessary
  commit, synchronization, publication, and PR work without depending on other skills" とある。
  この形は `git-commit` / `create-pr` を独立した持ち場に切ってある本リポジトリの設計と正面から
  衝突し、導入すると「PR作って」でどちらが発火するか分からなくなる。
  (2) **`--delete-branch` もリモートブランチ削除も本文に無い。** 消すと書いてあるのは
  worktree とローカルブランチだけで、要件の中心が抜けている。
  (3) **SKILL.md が約30行の散文のみで、実行するコマンドが1つも書かれていない。** 手順も
  ハードストップも無く、判断を全面的にモデルに委ねる作り。番号付きの手順と実コマンドで
  書いてある本リポジトリの既存スキルとは書式が別物で、そのまま並べると粒度が揃わない。
  (4) `release-pr` のような「マージしてはいけない PR」の除外概念が無い。
- 保守状況: pushed 2026-09-10（2日前）で動いている。ただし星数は少なく（上の取得元URLの値）、
  作者1人のリポジトリなので継続性の担保は弱い。
- 監査結果: 同梱は `scripts/stop-worktree-server.sh` と evals 一式。SKILL.md 本文は
  ネットワークに出る指示を含まない。ただし**スクリプトはプロセスを kill する**ため、
  採用するなら本文の通読が要る（今回は tree と SKILL.md 全文までを確認）。
  https://skills.sh/audits への掲載は確認できず（**未監査**であって安全の意味ではない）。MIT。

### chann/skills@git-branch-cleanup

- 層: T4
- 提供元: chann（個人）
- 取得元URL: https://skills.sh/chann/skills/git-branch-cleanup （44 installs）/
  https://github.com/chann/skills （0★ / MIT / pushed 2026-09-06 / archived でない）
- できること: 保護ブランチ（`main` `master` `dev` `develop` `development` `stg` `stage`
  `staging` `root`）のいずれかから到達可能なローカルブランチを削除する。保護名とカレント
  ブランチは必ず残す。韓国語と英語の両方でトリガーする description を持つ。
- 足りないこと: (1) **マージしない。** (2) **`git branch -d` しか使わないと明言している**
  （description に "Uses `git branch -d` (safe delete) only — never `-D`"）。
  squash マージ運用では到達可能性が成立しないため、**この repo の PR のように squash で
  入ったブランチはどれも消えない。** 要件に対して致命的。
  (3) worktree を扱わない。(4) リモートブランチを消さない。
- 保守状況: pushed 2026-09-06。星数は上の取得元URLの値で、作者1人のリポジトリ。
- 監査結果: SKILL.md 本文の bash のみで、ネットワークに出ない。`-d` 限定なので破壊性は低い。
  https://skills.sh/audits への掲載は確認できず（未監査）。MIT。

## 結論

build-new

- 採用元: なし

### 既存で満たせない点

- **「マージと同時に両方消す」を担当する既存スキルが、全層を通して1つも無い。** T1 の公式は
  `gh pr merge` を1箇所も実行せず（コード検索 0 件）、T2 の GitHub はスキルを出しておらず、
  T3 の 297 件にも無い。T4 で唯一近い `toy-crane/skills@merge` すら `--delete-branch` にも
  リモートブランチ削除にも触れていない。要件の中心が空白。
- **後始末側は `clean_gone` が既にあるので、作り直してはいけない。** 公式・導入済み・
  `[gone]` + worktree + `-D` まで押さえている。`merge-pr` は掃除を再実装せず、
  取りこぼし分を `/clean_gone` に委譲する形にする。これは「既存で満たせない点」ではなく
  **既存を使うべき点**として、ここに記録しておく。
- **`toy-crane/skills@merge` は採用も派生もできない。** 持ち場の切り方が本リポジトリと逆で、
  コミットと PR 作成を抱え込む。既にある `git-commit`（コミット専任）と
  `create-pr`（384行・リポジトリのテンプレート適用・承認ハードストップ）と トリガー が衝突する。
  借りられるのは「リモートが `MERGED` を返すまで掃除しない」「掃除の失敗をマージ成功と
  混ぜて報告しない」という2つの安全則だけで、これは骨格ではないため `derive` とは呼べない。
- **`chann/skills@git-branch-cleanup` は squash マージ運用で機能しない。** `-d` 限定を
  設計として宣言しているため、squash で入ったブランチが1本も消えない。この repo は
  squash を許可しており（`allow_squash_merge: true`）、実際 squash で入った PR がある。
- **`release-pr` を除外する概念が、どの候補にも無い。** 本リポジトリ群では
  `main` → `release` の PR は「本番へ出す判断は人がする」として明示的にマージ対象外に
  してある。これを知らないスキルを入れると、リリース PR まで掃除対象に含めてしまう。
