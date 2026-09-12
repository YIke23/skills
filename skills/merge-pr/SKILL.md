---
name: merge-pr
description: >-
  レビューの済んだ Pull Request をマージし、リモートとローカルの作業ブランチ、
  紐づく worktree を後始末する。ユーザーが「PRマージして」「マージして」
  「この PR 取り込んで」「マージしてブランチも消して」と言ったときに使う。
  PR の状態確認・マージ方法の確定・承認・`gh pr merge --delete-branch` の実行・
  ローカルの後始末までを行う。**コミットと PR 作成は担当しない。**
  `main` → `release` の本番リリース PR も対象外で、あれは人がマージする。
---

# merge-pr

レビューと CI の済んだ PR を、**承認を得てから** マージし、残骸を残さず片付ける。

## 担当範囲

開発の流れのうち、**5番目だけ**を担当する。

1. 作業ブランチを切る → `create-branch`
2. 開発作業をする
3. 時折コミットする → `git-commit`
4. 作業ブランチの内容を PR にまとめる → `create-pr`
5. **PR をマージして後始末する** ← ここ

このスキルはコミットを作らない。PR も作らない。4 までが済んで、**レビューと CI が
通った状態**を入力として受け取る。

**`main` → `release` のような本番リリース PR は対象外。** `release-pr` が
「本番へ出す判断は人がする」として意図的にマージを持ち場から外している。このスキルも
同じ線を引く（手順3で止まる）。

## 絶対原則

- **提示して承認を得るまでマージしない。** 提示（手順5）と実行（手順6）は必ず別ターン。
  手順5を出したらターンを終了して返信を待つ。マージは `main` を書き換え、デプロイを
  走らせることがあり、取り消しても履歴に痕跡が残る。「マージして」は通常のトリガーで
  あって確認スキップ指示ではない。
- **base が本番ブランチの PR はマージしない。** 手順3で止めてユーザーに返す。
- **リモートが `MERGED` を返すまで、後始末を1つも始めない。** `gh pr merge` は成功して
  終了しても、実際にはマージされていないことがある（下の「落とし穴」）。先に掃除すると、
  マージされていないブランチを消すことになる。
- **後始末の失敗を、マージの成功と混ぜて報告しない。** マージは済んでいるのに掃除だけ
  失敗した、という状態は普通に起きる。「マージしました」で終わらせると残骸が見えなくなる。
  マージの結果と掃除の結果は分けて報告する。
- **`--admin` を使わない。** 保護ルールを迂回するフラグで、レビューや必須チェックを
  飛ばしてマージできてしまう。必要に見えたら、それはマージしてよい状態ではない。
- 掃除を自前で書かない。取りこぼしは **`/clean_gone`（公式・導入済み）に委譲する**（手順8）。

## 手順

### 1. 対象の PR を特定する

```bash
git remote get-url origin                # ホスト判定と owner/repo
git rev-parse --abbrev-ref HEAD          # カレントブランチ
gh pr status -R <owner/repo>             # 番号の指定が無いとき
```

番号を言われていなければ、カレントブランチに紐づく PR を採る。`gh pr merge` は引数を
省くとカレントブランチの PR を選ぶが、**取り違えが起きたときに気づけない**ので、番号を
確定させてから以降のコマンドに明示する。

`owner/repo` は remote URL から取り出し、`gh` には **必ず `-R owner/repo` を渡す**。

**GitHub 以外（Bitbucket など）は `gh` が使えない。** マージ方法をユーザーに伝えて終わる。

### 2. マージしてよい状態か確認する

```bash
gh pr view <番号> -R <owner/repo> --json \
  number,title,state,isDraft,baseRefName,headRefName,mergeStateStatus,mergeable,reviewDecision,url
gh pr checks <番号> -R <owner/repo>
```

**次のどれかに当たったら、マージせず手順5で状況を伝える。**

| 見るもの | 止まる値 | 意味 |
|---|---|---|
| `state` | `MERGED` / `CLOSED` | 既に終わっている。**二重にマージしない**。`MERGED` なら手順7の後始末だけ行う |
| `isDraft` | `true` | draft のまま。ready にするのは人の判断 |
| `mergeable` | `CONFLICTING` | コンフリクト。解消はこのスキルの担当外 |
| `mergeStateStatus` | `BLOCKED` | 必須レビュー・必須チェックが未達 |
| `mergeStateStatus` | `BEHIND` | base に追いついていない。更新が要る |
| `mergeStateStatus` | `DIRTY` | コンフリクト |
| `gh pr checks` | 赤 / 実行中 | **緑になるまで待つ。** 実行中のままマージすると下の「落とし穴」を踏む |

`mergeStateStatus` が `CLEAN` で、`gh pr checks` が全部緑のときだけ先へ進む。
`UNSTABLE`（必須ではないチェックが落ちている）は、何が落ちているかを手順5で伝えて
ユーザーに判断してもらう。

### 3. 本番リリース PR なら止まる

`baseRefName` が本番ブランチ（`release` など）なら、**マージせずに終わる。**

```bash
gh repo view <owner/repo> --json defaultBranchRef --jq .defaultBranchRef.name
```

既定ブランチ以外へ向いていて、かつ head が `main` のような開発の本流そのものなら、
それは `release-pr` が作ったリリース PR。マージした瞬間に本番へ出るため、
判断は人がする。PR の URL を返し、そう伝えて終わる。

### 4. マージ方法を決める

**リポジトリが許可している方法しか使えない。**

```bash
gh repo view <owner/repo> --json \
  mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed,deleteBranchOnMerge
```

許可が1つなら、それを使う。複数許可されているときは、次の順で決める。

1. **リポジトリの明文化された方針。** `.github/PULL_REQUEST_TEMPLATE.md` の HTML コメントや
   `CLAUDE.md` に「マージは Squash」などと書かれていれば、それに従う（`create-pr` の手順2で
   読んでいるはず）
2. **実際の履歴。** どちらが使われているかを見る

   ```bash
   git log --merges --first-parent origin/<base> --pretty='%s' | head -10
   ```

   `Merge pull request #N from ...` が並んでいれば merge commit 運用。ほとんど出てこなければ
   squash 運用。

3. 判断が付かなければ **squash**。作業ブランチの試行錯誤が base の履歴に流れ込まない。

**`deleteBranchOnMerge` の値をここで控えておく。** `true` ならリモートは GitHub が消すので、
`--delete-branch` が実際に効くのはローカル側だけになる。手順7の期待値が変わる。

### 5. 提示して承認を得る（ハードストップ）

次を提示して、**ターンを終了し承認を待つ**。

- PR の番号・タイトル・URL
- **base ← head** のブランチ名
- 実行するコマンド（マージ方法のフラグまで含めた完全な形）
- CI の状態（`gh pr checks` の結果）
- 消えるもの: リモートブランチ / ローカルブランチ / worktree のパス（あれば）
- 手順2で止まる値に当たっていたなら、**マージせずにその事実だけ**を伝える
- `deleteBranchOnMerge` が `true` なら、リモートは GitHub 側が消す旨

### 6. マージする（承認後の別ターン）

```bash
gh pr merge <番号> -R <owner/repo> --squash --delete-branch
```

- マージ方法のフラグ（`--squash` / `--merge` / `--rebase`）は手順4で決めたものにする
- `--delete-branch` は **リモートとローカルの両方**を消す（`gh pr merge --help` の
  `-d, --delete-branch: Delete the local and remote branch after merge`）

**続けて、本当にマージされたかを確かめる。**

```bash
gh pr view <番号> -R <owner/repo> --json state,mergedAt,mergeCommit \
  --jq '"\(.state) \(.mergedAt) \(.mergeCommit.oid // "-")"'
```

**`MERGED` が返るまで手順7へ進まない。** `gh pr merge` はコマンドとしては成功しても、
実際には auto-merge が予約されただけのことがある（下の「落とし穴」）。その場合は
`state` が `OPEN` のまま返るので、予約された旨をユーザーに伝えて終わる。掃除はしない。

### 7. ローカルを後始末する

`MERGED` を確認できた後にだけ実行する。

```bash
git fetch --prune                        # 消えた origin/<branch> の追跡参照を落とす
git switch <base>                        # マージ済みブランチから降りる
git pull --ff-only                       # base をマージ後の状態に追いつかせる
git branch -vv                           # 残骸が無いか目視
```

`--delete-branch` でローカルが消えていれば、`git branch -vv` に作業ブランチは出てこない。
**出てきたら消せていない。** 原因はほぼ worktree（下の「落とし穴」）なので、手順8へ回す。

### 8. 取りこぼしは `/clean_gone` へ

`[gone]` のまま残っているブランチがあれば、**自前で消さず公式のコマンドに渡す。**

```bash
git branch -vv | grep ': gone]'
```

`/clean_gone`（`commit-commands` プラグイン、Anthropic 公式）が、`[gone]` の検出から
worktree の `git worktree remove --force`、`git branch -D` までを1回で行う。

**Web UI や auto-merge でマージされた分は、このスキルを通らずに `[gone]` になる。**
そちらは定期的に `/clean_gone` を回すのが担当。このスキルが拾えるのは、自分でマージした
ぶんだけだと理解しておく。

## 落とし穴

**CI が走っている間にマージすると、auto-merge の予約に化ける。** `gh pr merge` は
「必須チェックがまだ通っていなければ auto-merge を有効にする」挙動を持つ
（`gh pr merge --help` に明記）。コマンドは成功して終わるのに PR は `OPEN` のままで、
ローカルブランチも消えない。**手順6の `state` 確認だけがこれを見分ける。**
リモートブランチは後で GitHub が消すので、ローカルだけが残って `[gone]` になる。

**worktree に checkout 中のブランチはローカル削除に失敗する。** `--delete-branch` は
リモートを消してローカルの削除だけ失敗し、**マージ自体は成功しているのでコマンドは
エラーで終わらないことがある。** 事前に確認しておく。

```bash
git worktree list | grep "\[<作業ブランチ>\]"
```

該当があれば、手順5でそのパスを「消えるもの」に含めて伝え、後始末は `/clean_gone` に任せる。

**squash マージすると `git branch -d` は効かない。** squash は base に別のコミットとして
入るため、git は元ブランチをマージ済みと認識しない。自前で掃除しようとして `-d` を
使うと1本も消えず、`-D` は不可逆。だから判定は `[gone]`（upstream が消えた）で行い、
その処理は `/clean_gone` に任せる。

**`deleteBranchOnMerge: true` でもローカルは残る。** リポジトリ設定が消すのはリモートだけ。
「設定を入れたから掃除は要らない」は成り立たない。

**カレントブランチをマージすると、その場で足場が消える。** `gh` は base へ切り替えてから
消すが、`git status` で未コミットの変更が残っていると切り替えに失敗することがある。
マージ前に作業ツリーをクリーンにしておく。

## やってはいけないこと

- **承認前にマージする。** 手順5と手順6を同じターンで通さない
- **`--admin` でチェックを迂回する**
- **`state` を確認せずに掃除を始める**
- **`git branch -D` を自前で撃つ。** `/clean_gone` に渡す
- **本番リリース PR をマージする。** 手順3で止まる
- **コミットや PR 作成を肩代わりする。** `git-commit` と `create-pr` の持ち場
