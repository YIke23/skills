# skills

Claude のスキルを 1 箇所で管理し、2 台の Mac と 2 つの claude.ai アカウントへ配るリポジトリ。
構成は [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)
に合わせ、プラグインごとに `plugins/<name>/` で束ねている。

## 概要

### 置き場所

```
.claude-plugin/marketplace.json          プラグインの一覧。name と source だけを書く
plugins/<plugin>/.claude-plugin/         そのプラグインの plugin.json
plugins/<plugin>/skills/<name>/SKILL.md  スキル本体。1 フォルダ 1 スキル
template/SKILL.md                        新しいスキルを作るときの雛形
scripts/                                 push 前の点検と、作業場への出し入れ
docs/                                    運用ガイドと設計判断の記録
```

**スキルの所属はフォルダ構造で決まる。** `plugins/<plugin>/skills/` に置いたものが、
そのプラグインとして配られる。`marketplace.json` に `skills` 配列は書かない。

書かないのは、**配列を読む実装と読まない実装があるから**。CLI は配列で絞り込むが、
claude.ai とデスクトップアプリは配列を無視してプラグインルート直下の `skills/` を
総なめする。かつて `source: "./"` に配列を添えて束ねていたときは、CLI では 7 本、
デスクトップでは 15 本という食い違いが起きていた（→ studio に git 系が混ざる件）。
`source` をプラグインごとに切れば、どの実装でも同じ結果になる。

束ね方を変えるときはフォルダを動かす。`template/` `scripts/` `docs/` はどの `source` にも
入らないので、配布物には含まれない。

| プラグイン | 中身 | 配布先 |
|---|---|---|
| `studio` | web-image-builder, icon-builder, sns-icon-builder, eli15, meeting-deck, paas-onboarding, doc-brief | Mac + claude.ai アカウント |
| `skill-kit` | skill-prior-art, skill-inventory | Mac + claude.ai アカウント |
| `git-flow` | create-branch, git-commit, create-pr, merge-pr, release-pr, create-issue | Mac のみ（手元の git を触るため） |

呼び出しは `/studio:eli15` のように `プラグイン名:スキル名` になる。

リポジトリ名は `skills`、marketplace 名は `yike-skills` で、意図的に別にしてある。
プラグイン ID が `studio@yike-skills` の形になるのはこのため。
anthropics/skills も同じく `anthropic-agent-skills` という別名を持つ。

### どこで何をするか

| | 持ち場 |
|---|---|
| **Claude Cowork** | 着手前の調査、SKILL.md の下書き、外部サービスからの材料集め |
| **Claude Code**（`~/dev/skills` で起動） | ファイルの編集、`make` 系、git と PR、`claude plugin` 操作 |
| **手作業** | claude.ai 管理画面での「更新」、PR のマージ |

**Cowork はこのリポジトリのファイルを直接編集しない。** `~/.claude` 配下は保護領域として
接続を拒否されるため、そもそも届かない。`~/dev/skills` には届くが、git 操作もコマンド実行も
Claude Code のほうが素直に回る。Cowork の持ち場は、書く前に決めることと、外から材料を
持ってくること。

## セットアップ（各マシンで 1 回）

```bash
claude plugin marketplace add git@github.com:YIke23/skills.git
claude plugin install studio@yike-skills
claude plugin install skill-kit@yike-skills
claude plugin install git-flow@yike-skills
```

**SSH リモートを使うこと。** HTTPS だと最初の登録は通るのに、バックグラウンドの
自動更新だけが無言で失敗する。HTTPS を使うなら先に `gh auth setup-git` を実行しておく。

取得に失敗したとき既存の複製を捨てないよう、`~/.claude/settings.json` に足しておく。

```json
{ "env": { "CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE": "1" } }
```

`marketplace.json` のプラグイン項目に `version` を書かないこと。
書くとリリースごとに上げない限り更新が止まる。省略していればコミットを追って自動更新される。

## 場面別の手順

### 1. スキルを新規作成する

| 工程 | どこで |
|---|---|
| 既存スキルの調査、下書き | Cowork |
| 実装・試用・PR | Claude Code |

**Cowork でやること。** `skill-prior-art` を回して、同じ仕事をするスキルが既に公開されて
いないか調べる。採用で済むならここで終わる。自作すると決めたら、SKILL.md の下書きまで作る。

**Claude Code でやること。** まず `~/.claude/skills/<name>/` で書き始める。そこに置いた
スキルは保存した瞬間に効くので、試行錯誤が速い。プラグイン経由だと commit → PR → マージ →
`plugin update` → 再起動を回さないと反映されない。

形が固まったら、束ねたいプラグインの下へ**移す**。コピーではなく移動。両方に残すと
裸の `/git-commit` と `/git-flow:git-commit` が併存して紛らわしい。

```bash
cd ~/dev/skills
git switch -c skill/<name>
mv ~/.claude/skills/<name> plugins/<plugin>/skills/<name>
make check
git add -A && git commit -m "add: <name> スキルを追加"
git push -u origin skill/<name>
gh pr create
```

`marketplace.json` を触るのは**プラグインを新設するときだけ**。既存プラグインへ
スキルを足すなら、フォルダを置けば届く。`make check` が `plugins/` と
`marketplace.json` の食い違いを見るので、置き忘れと書き忘れはそこで止まる。

check が緑になったら GitHub でマージする。マージ後の反映は 3 と 4 へ。

### 2. スキルを更新する

新規と違う点は 2 つ。`marketplace.json` は触らない。そして**リポジトリ側で直してから試す。**

Cowork は文面の相談に使ってもよいが、必須ではない。実作業は Claude Code に閉じる。

```bash
cd ~/dev/skills
git switch -c fix/<name>
# plugins/<plugin>/skills/<name>/SKILL.md を直す
make check
make install name=<name>   # 試用のため。Claude Code を再起動して実際に呼ぶ
git add -A && git commit -m "fix: <name> の〇〇を直す"
git push -u origin fix/<name>
gh pr create
```

マージしたら `make uninstall name=<name>` で作業場を空に戻す。残すとプラグイン版と
二重に並び、どちらを呼んでいるか分からなくなる。

更新は「今までどおり呼べるが挙動だけ変わった」という壊れ方をする。`make check` は形式しか
見ないので、変えた部分を実際に踏むところまでやる。

### 3. スキルを別の PC に配る

受け取る側のマシンの Claude Code で実行する。Cowork は関与しない。

```bash
claude plugin marketplace update yike-skills
claude plugin update studio@yike-skills
claude plugin update skill-kit@yike-skills
claude plugin update git-flow@yike-skills
```

**Mac は放っておいても追いつかない。** `marketplace update` は marketplace の複製を新しく
するだけで、入っているプラグインの版は切り替わらない。各プラグインを明示的に更新して、
セッションを再起動する。

反映できたかは `plugin list` の SHA ではなく、**再起動後の新規セッションで
`/studio:<skill>` が候補に出るか**で確かめる。`plugin validate` も `plugin details` も
名前空間の問題は素通りするので、この 2 つを根拠にしない。

**marketplace 名やプラグイン名を変えたときだけは `plugin update` で追従しない。**
登録キーが古い名前のままなので、一度消して入れ直す。

```bash
claude plugin marketplace remove <古い marketplace 名>
claude plugin marketplace add git@github.com:YIke23/skills.git
claude plugin install studio@yike-skills
claude plugin install skill-kit@yike-skills
claude plugin install git-flow@yike-skills
```

### 4. スキルを claude.ai アカウントに配る

アカウント側は GitHub リポジトリを marketplace として見ている。**ビルドもアップロードも
要らない。** Customize > Skills でプラグインを開き、**「更新」を押す**だけ。
会社と個人で 1 回ずつ、計 2 回。

反映できたかは、そのプラグインの「スキル」タブの本数で確かめる。`studio` なら 7 本。
数が合わないときは配布単位の切り方を疑う（→ studio に git 系が混ざる件）。

`.plugin` を作って手で上げる経路（`make build` と `scripts/build.py`）は 2026-09-15 に
廃止した。GitHub 連携で同じことができるうえ、上げ忘れると**アカウントだけ古い**という
気づきにくい壊れ方をするため。

`git-flow` はアカウントに上げない。手元の git を触るスキルなので使い道がない。

## main は保護されている

**`main` へは直接 push できない。** ブランチを切って PR を出し、GitHub でマージする。
PR では CI が `make check` を走らせるので、壊れた SKILL.md が main に入らない。

直接 push しようとすると GitHub 側で弾かれる。ルールセットによる強制で、
管理者バイパスは付けていないので自分自身も例外ではない。

```
remote: - Changes must be made through a pull request.
remote: - Required status check "check" is expected.
 ! [remote rejected] main -> main
```

main に入るには次の 4 つが揃っている必要がある。

| ルール | 意味 |
|---|---|
| `pull_request` | PR 経由でしか変更できない（承認者数は 0 なので一人で回せる） |
| `required_status_checks` | CI の `check` が緑であること。ブランチが最新の main に追いついていること |
| `non_fast_forward` | force push で履歴を壊せない |
| `deletion` | main を消せない |

事故対応などでどうしても直接 push が要るときは、GitHub の
**Settings > Rules > Rulesets** から該当ルールセットを開き、Enforcement status を
Disabled にする。作業が終わったら Active に戻す。**戻し忘れないこと。**

`make check` が見るのは 2 つ。**スキル単体の形式**として、SKILL.md の `name` とフォルダ名の
一致、`description` の有無と長さ。1536 字を超えると切り捨てられ、意図した場面で呼ばれなく
なるため、ここで止める。**配布の構成**として、`marketplace.json` と `plugins/` の対応、
`plugin.json` との description の一致、そしてリポジトリ直下の `skills/` や `skills` 配列が
復活していないこと。

## studio に git 系が混ざるのは、配布単位がリポジトリ全体だったから

`studio:git-commit` と `git-flow:git-commit` が並んで見える状態が長く続いた。
**2026-09-15 に原因を特定して解消した。** 同じ症状が再発したときのために残す。

### 原因は配列が読まれないこと

かつては全プラグインが `source: "./"` で、どれを生やすかを `marketplace.json` の
`skills` 配列で指定していた。**この配列を読むのは CLI だけ。** claude.ai と
デスクトップアプリは配列を無視し、プラグインルート直下の `skills/` を総なめする。

`source: "./"` はリポジトリ全体を配るので、アカウント側の `studio` には 15 本ぶんの
フォルダが入っていた。結果、宣言は 7 本なのに 15 本生え、git 系まで `studio:` で引けた。

| 見るもの | 当時の中身 |
|---|---|
| `plugin.json` の `skills` 配列 | 7 本 |
| 同じツリーの `skills/` | 15 フォルダ |
| CLI で実際に生えた数 | 7 本 |
| claude.ai / デスクトップで生えた数 | **15 本** |

`git-flow` に同じ症状が出なかったのは、アカウントに上げていなかったから。
つまり「配列は効いている」という当時の診断は、CLI しか見ていなかったせいで半分だけ正しかった。

### 直し方

**配布単位をフォルダで区切る。** `plugins/<plugin>/skills/` に置き、`source` をそこへ
向ければ、配列を読む実装も読まない実装も同じ結果になる。いまのレイアウトがこれ。

再発を疑うときは、アカウントのプラグイン画面で「スキル」タブの本数を見る。
`studio` が 7 本以外なら、`source` がプラグインのサブディレクトリを指しているか確認する。

### 補足: `create-branch` が一覧に出ないのは正常

`plugins/git-flow/skills/create-branch/SKILL.md` には `disable-model-invocation: true` が付いている。
モデルが自動で選ぶ一覧には出ず、`/git-flow:create-branch` と明示的に叩いたときだけ動く。
`studio:` にも `git-flow:` にも見えないのはこのためで、配布の失敗ではない。

## 入れていないもの

`docx` / `pptx` / `xlsx` / `pdf` / `skill-creator` は Anthropic の Proprietary ライセンス。
リポジトリには置かない。claude.ai アカウント側で有効にしたまま使う。
