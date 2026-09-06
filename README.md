# skills

Claude のスキルを 1 箇所で管理し、2 台の Mac と 2 つの claude.ai アカウントへ配るリポジトリ。
構成は [anthropics/skills](https://github.com/anthropics/skills) に合わせてある。

## 概要

### 置き場所

```
.claude-plugin/marketplace.json   どのスキルをどのプラグインに束ねるかの定義
skills/<skill-name>/SKILL.md      スキル本体。1 フォルダ 1 スキル、フラットに並べる
template/SKILL.md                 新しいスキルを作るときの雛形
scripts/                          アカウント配布用のビルドと、push 前の点検
```

スキルの所属はフォルダ構造ではなく `marketplace.json` の `skills` 配列で決まる。
束ね方を変えたいときは JSON を直すだけでよく、ファイルは動かさない。
ただし marketplace 経由で Mac に入れた場合、この絞り込みが現状効いていない（→ 未解決）。

| プラグイン | 中身 | 配布先 |
|---|---|---|
| `studio` | web-image-builder, icon-builder, eli15, paas-onboarding | Mac + claude.ai アカウント |
| `git-flow` | create-branch, git-commit, be-pr-create, fe-pr-create, create-issue | Mac のみ（手元の git を触るため） |

呼び出しは `/studio:eli15` のように `プラグイン名:スキル名` になる。

リポジトリ名は `skills`、marketplace 名は `yike-skills` で、意図的に別にしてある。
プラグイン ID が `studio@yike-skills` の形になるのはこのため。
anthropics/skills も同じく `anthropic-agent-skills` という別名を持つ。

### どこで何をするか

| | 持ち場 |
|---|---|
| **Claude Cowork** | 着手前の調査、SKILL.md の下書き、外部サービスからの材料集め |
| **Claude Code**（`~/dev/skills` で起動） | ファイルの編集、`make` 系、git と PR、`claude plugin` 操作 |
| **手作業** | claude.ai 管理画面へのアップロード、PR のマージ |

**Cowork はこのリポジトリのファイルを直接編集しない。** `~/.claude` 配下は保護領域として
接続を拒否されるため、そもそも届かない。`~/dev/skills` には届くが、git 操作もコマンド実行も
Claude Code のほうが素直に回る。Cowork の持ち場は、書く前に決めることと、外から材料を
持ってくること。

## セットアップ（各マシンで 1 回）

```bash
claude plugin marketplace add git@github.com:YIke23/skills.git
claude plugin install studio@yike-skills
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

形が固まったら、このリポジトリの `skills/` へ**移す**。コピーではなく移動。両方に残すと
裸の `/git-commit` と `/git-flow:git-commit` が併存して紛らわしい。

```bash
cd ~/dev/skills
git switch -c skill/<name>
mv ~/.claude/skills/<name> skills/<name>
# marketplace.json の skills 配列に ./skills/<name> を足す
make check
git add -A && git commit -m "add: <name> スキルを追加"
git push -u origin skill/<name>
gh pr create
```

`marketplace.json` への追記を忘れると、**そのスキルは他のマシンへ永久に届かない。**
新規のときだけ必要な手順で、更新では触らない。

check が緑になったら GitHub でマージする。マージ後の反映は 3 と 4 へ。

### 2. スキルを更新する

新規と違う点は 2 つ。`marketplace.json` は触らない。そして**リポジトリ側で直してから試す。**

Cowork は文面の相談に使ってもよいが、必須ではない。実作業は Claude Code に閉じる。

```bash
cd ~/dev/skills
git switch -c fix/<name>
# skills/<name>/SKILL.md を直す
make check
cp -r skills/<name> ~/.claude/skills/   # 試用のため。Claude Code を再起動して実際に呼ぶ
git add -A && git commit -m "fix: <name> の〇〇を直す"
git push -u origin fix/<name>
gh pr create
```

マージしたら `rm -rf ~/.claude/skills/<name>` で作業場を空に戻す。残すとプラグイン版と
二重に並び、どちらを呼んでいるか分からなくなる。

更新は「今までどおり呼べるが挙動だけ変わった」という壊れ方をする。`make check` は形式しか
見ないので、変えた部分を実際に踏むところまでやる。

> 試用の `cp` と後片付けの `rm -rf` は、`make install name=<x>` /
> `make uninstall name=<x>` にする予定。**未実装。**

### 3. スキルを別の PC に配る

受け取る側のマシンの Claude Code で実行する。Cowork は関与しない。

```bash
claude plugin marketplace update yike-skills
claude plugin update studio@yike-skills
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
claude plugin install git-flow@yike-skills
```

### 4. スキルを claude.ai アカウントに配る

ビルドは Claude Code、アップロードは手作業。アカウント側は GitHub を見に行かないので、
ここだけ自動化できない。

```bash
make build          # dist/ に .plugin と skills/*.zip ができる
```

`dist/studio.plugin` を **Customize > Plugins** に上げる。会社と個人で 1 回ずつ、計 2 回。
4 スキルが 1 ファイルに入っているので、これだけで済む。

素の `/eli15` で呼びたい場合だけ `dist/skills/eli15.zip` を **Customize > Skills** に上げる。
スキル 1 本 = zip 1 つなので、増やすほど手作業が増える。

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

`make check` は SKILL.md の `name` とフォルダ名の一致、`description` の有無と長さ、
どのプラグインにも属していないスキルを見る。description が 1536 字を超えると
切り捨てられて意図した場面で呼ばれなくなるため、ここで止める。

## 未解決: marketplace 経由だと担当が分かれない

`marketplace.json` は `studio` に 4 本、`git-flow` に 5 本を割り当てている。
ところが Mac に入った `studio` には 9 本すべてが入っていて、
`studio:git-commit` と `git-flow:git-commit` が同時に並ぶ。

**アカウント配布は影響を受けない。** `make build` は `skills` 配列に書いたフォルダだけを
staging へ写すので、`dist/studio.plugin` は 4 本のまま。崩れるのは marketplace 経由の Mac 側だけ。

原因は両プラグインの `source` がどちらも `"./"` で、リポジトリ全体がコピーされる点にあると
見ている（推定・未検証）。コピーのあとに `skills/` 配下が全部読まれるため、`skills` 配列の
絞り込みが効かない。**入れ直しても直らない。**

### 方針: どちらの案も今は採らない

| 案 | やること | 難点 |
|---|---|---|
| 1 プラグインに統合 | `marketplace.json` を 1 本にまとめる | 制作系と git 系を別々に入れ外しできなくなる |
| ディレクトリを分ける | `plugins/studio/skills/…` と `plugins/git-flow/skills/…` に分け、`source` を個別に向ける | anthropics/skills の構成から外れる |

ディレクトリ分割は「構成は anthropics/skills に合わせる」というこのリポジトリの前提と
正面から衝突する。この前提は一度フラット化を試して戻した経緯があり、軽く動かすものではない。
よって**検討段階に留める。**

統合案は担当分けを捨てることになる。制作系と git 系を別々に入れ外しする使い道が
本当に無いと確認できてから決める。

それまでは、git 系スキルの正式な呼び名を `git-flow:` とする。`studio:git-commit` も
引けてしまうが、指しているファイルは同じなので挙動は変わらない。紛らわしいだけで実害は無い。

## 入れていないもの

`docx` / `pptx` / `xlsx` / `pdf` / `skill-creator` は Anthropic の Proprietary ライセンス。
リポジトリには置かない。claude.ai アカウント側で有効にしたまま使う。
