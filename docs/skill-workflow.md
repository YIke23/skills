# スキル運用ガイド（2026-09-13 / 2026-09-28 更新）

会社Mac でスキルを書き、個人Mac まで届けるまでの手順。読者は YIke 本人と、このプロジェクトを引き継ぐ Claude。

**0章と1章は初回に通読する。2〜6章は必要になったときに引く。** 経緯や設計の背景は `skill-distribution-pipeline.md` にある。

## 0. 作業は会社Mac の Claude Code で通す

スキル作りは調査から PR まで、**会社Mac の Claude Code で一気通貫**で行う。工程を Cowork と分担しない。判断の根拠は `skill-distribution-pipeline.md` の「2026-09-06 の判断: 分担をやめる」にある。

Cowork を使うのは次の3つに限る。

- 会社Mac が手元にない（個人Mac・外出先）
- リポジトリに入らない資料や記録
- 放置して回す長い調査

いずれも「工程の途中で切る」使い方ではない。線引きは **リポジトリに入るものは全部 Claude Code**。

## 1. 実体は ~/dev/skills にあり、残りは全部その下流

スキルの本体は会社Mac の `~/dev/skills` にある。GitHub のローカルリポジトリで、ブランチを切るのもコミットするのもここ。このガイド自身も `~/dev/skills/docs/` にあり、スキル本体と同じ履歴で追える。

そこから二方向に流れる。

```
                  ┌── make install name=<x> ──→ ~/.claude/skills   （作業中の1本だけ）
~/dev/skills ─────┤
  （実体・git）    └── push / PR ──→ GitHub main ──→ plugin update ──→ 両方の Mac
```

**完成したスキルはプラグイン経由で受け取る。** `studio`・`skill-kit`・`git-flow` の3つを配っている。呼び名は `/studio:eli15` の形になる。

**会社Mac には `studio` と `git-flow` の両方が入っている**（2026-09-06 確認。`installed_plugins.json` に `studio@yike-skills` と `git-flow@yike-skills` が `scope: user` で並ぶ）。個人Mac の導入状態は会社Mac からは見えないため未確認。

`skill-kit` は 2026-09-07 に追加したプラグインで、**まだどの Mac にも入っていない**。受け取るには各 Mac で `plugin update` が要る。

`~/.claude/skills` は完成品の置き場ではない。**書いている途中の1本だけを一時的に置く作業場**で、マージしたら消す。全部を入れるとプラグイン側と二重に並ぶ。

ただし**空にはならない**。下の例外が1件ある。

### 例外: notion-weekly-progress は作業場に常駐する

`notion-weekly-progress` は、**GitHub に上げない唯一のスキル**。このリポジトリにも
`marketplace.json` にも載せず、`~/.claude/skills` に置いたまま使う。

そのため作業場には常に次の2つが残る。

| 残るもの | 中身 |
|---|---|
| `notion-weekly-progress/` | スキル本体（`SKILL.md` / `assets` / `references` / `scripts`） |
| `notion-weekly-progress-docs/` | `prior-art-notion-weekly-progress.md` 1枚。`SKILL.md` を持たないのでスキルとしては読み込まれない。他のスキルなら `docs/` に置く先行事例調査の記録だが、本体がリポジトリに無いので行き場がなくここに同居している |

覚えておくことは2つ。

- **`make uninstall` の「作業場に残っている」警告は、この2つの名前についてだけは正常。**
  それ以外の名前が混じっていたら、それが片付け忘れ
- 2章・3章の流れ（ブランチ → PR → `plugin update`）はこのスキルには適用されない。
  GitHub を経由しないため、**個人Mac には届かない**

`main` は保護してあり、直接 push できない。GitHub へ届けるには必ずブランチと PR を経由する。

### 深掘りノート: make install の仕様

`make install name=<x>` / `make uninstall name=<x>` は実装済み（2026-09-06）。中身は
`scripts/install.py` で、Makefile からはこれを呼ぶだけ。

- `make install name=<x>` — `plugins/*/skills/<x>/` を `~/.claude/skills/<x>/` へ写す。既にあれば
  入れ替える。**引数なしの全件コピーは作らない**
- `make uninstall name=<x>` — `~/.claude/skills/<x>/` を消す。マージ後の後片付け用。
  無ければ黙って skip するので、二重に叩いても壊れない
- 写す前に、同名のプラグイン版が有効かどうかは見ない。二重に並ぶのは作業中だけなので許容する

`name` は `skills/` 直下のフォルダ名 1 つだけを受ける。空・`/` を含む・`.` で始まるものは
弾く。`uninstall` は宛先が `~/.claude/skills` の直下であることを確かめてから消すので、
`name` を書き間違えて作業場ごと消す事故は起きない。

`uninstall` のあとに他のスキルが残っていれば警告する。ただし作業場が完全に空になることは
無く、`notion-weekly-progress` と `notion-weekly-progress-docs` は常に警告に出る（上の例外）。

## 2. 新しくスキルを作る → ブランチを切って、束ねたいプラグインの下に置く

どのプラグインに属するかはフォルダで決まる。`marketplace.json` は触らない
（触るのはプラグインそのものを新設するときだけ）。

1. **先に既存を調べる。** `skill-prior-art` を回して、同じ仕事をするスキルが公開されていないか確認する。採用で済むならここで終わる
2. `cd ~/dev/skills && git switch -c add-<name>` — main では作業しない
3. `cp -r template plugins/<plugin>/skills/<name>` して SKILL.md を書く。`<plugin>` は `studio` / `skill-kit` / `git-flow` のいずれか
4. `make check` — frontmatter の形式やフォルダ名の一致を機械が見る
5. `make install name=<name>` して Claude Code を再起動し、**実際に呼んで発火するか確かめる**。description を書き間違えても静かに呼ばれなくなるだけなので、ここを飛ばすと気づけない
6. `git push -u origin add-<name>` → `gh pr create` → PR をマージ
7. `make uninstall name=<name>` で作業場を空に戻す。以降はプラグイン版が担当する

## 3. スキルを更新する → 同じ道を通る

道筋は2章と同じ。フォルダを作らず既存の SKILL.md を直すだけなので、違いは一つ。

**手元での確認をより厚くする。** 新規なら「呼べない」とすぐ分かるが、更新は「今までどおり呼べるが挙動だけ変わった」という壊れ方をする。`make check` を通したあと `make install name=<name>` して、変えた部分を実際に踏むところまでやる。

更新中は `~/.claude/skills/<name>` とプラグイン版が同名で並ぶ。**このとき呼んでいるのはどちらか分からない**ので、確認したいときは SKILL.md に一時的な目印を入れて見分ける。終わったら `make uninstall name=<name>`。

ブランチ名は `add-` ではなく `fix-<name>` や `update-<name>` を使う。PR を見返したときに、新規追加と更新が名前で分かれる。

## 4. 完成したスキルを届ける → Mac は plugin update、アカウントは「更新」

### 両方の Mac

マージしたあと、各 Mac の Claude Code で受け取る。

```bash
claude plugin marketplace update yike-skills
claude plugin update studio@yike-skills
claude plugin update skill-kit@yike-skills
claude plugin update git-flow@yike-skills
```

続けて **Claude Code を再起動する。**

`marketplace update` だけでは反映されない。marketplace の複製が新しくなるだけで、
入っているプラグインの版は切り替わらない。各プラグインの `update` と再起動まで通して初めて新しいスキルが使える。

反映できたかは `plugin list` の SHA ではなく、**再起動後の新規セッションで `/studio:<skill>` が
候補に出るか**で確かめる。`plugin validate` も `plugin details` も名前空間の問題は素通りするので、
この2つを根拠にしない。

個人Mac ではこれだけ。個人Mac の `~/.claude/skills` は常に空で、何も書かない。

**marketplace 名やプラグイン名を変えたときだけは `plugin update` で追従しない。**
登録キーが古い名前のままなので、一度消して入れ直す。

```bash
claude plugin marketplace remove <古い marketplace 名>
claude plugin marketplace add git@github.com:YIke23/skills.git
claude plugin install studio@yike-skills
claude plugin install skill-kit@yike-skills
claude plugin install git-flow@yike-skills
```

### claude.ai アカウント（会社・個人の2つ）

アカウント側は GitHub リポジトリを marketplace として見ている。**ビルドもアップロードも要らない。**
Customize > Skills でプラグインを開き、**「更新」を押す**だけ。会社と個人で1回ずつ、計2回。
配るのは `studio` と `skill-kit` で、`git-flow` は上げない（手元の git を触るので使い道がない）。

反映できたかは、そのプラグインの「スキル」タブの本数が `plugins/<plugin>/skills/` の
フォルダ数と一致するかで確かめる。合わないときは配布単位の切り方を疑う（→ 末尾の「studio に git 系が混ざっていた件」）。

`.plugin` を作って手で上げる経路（`make build` と `scripts/build.py`）は 2026-09-15 に廃止した。
GitHub 連携で同じことができるうえ、上げ忘れると**アカウントだけ古い**という気づきにくい壊れ方をするため。

## 5. 新しい Mac に入れる → marketplace を SSH で登録する

各マシンで1回だけ。

```bash
claude plugin marketplace add git@github.com:YIke23/skills.git
claude plugin install studio@yike-skills
claude plugin install skill-kit@yike-skills
claude plugin install git-flow@yike-skills
```

**SSH リモートを使うこと。** HTTPS だと最初の登録は通るのに、バックグラウンドの
自動更新だけが無言で失敗する。HTTPS を使うなら先に `gh auth setup-git` を実行しておく。

取得に失敗したとき既存の複製を捨てないよう、`~/.claude/settings.json` の `env` に
`CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE` を足しておく（有効にする）。

## 6. リポジトリの決まりごと

### marketplace.json には name と source だけを書く

**スキルの所属はフォルダ構造で決まる。** `plugins/<plugin>/skills/` に置いたものが、
そのプラグインとして配られる。`marketplace.json` に `skills` 配列は書かない。
CLI は配列で絞り込むが、claude.ai とデスクトップアプリは配列を無視してプラグインルート直下の
`skills/` を総なめするので、配列を書くと実装ごとに生える本数が食い違う。
`template/` `scripts/` `docs/` はどの `source` にも入らないので、配布物には含まれない。

プラグイン項目に `version` も書かない。書くとリリースごとに上げない限り更新が止まる。
省略していればコミットを追って自動更新される。

リポジトリ名は `skills`、marketplace 名は `yike-skills` で、意図的に別にしてある。
プラグイン ID が `studio@yike-skills` の形になるのはこのため。
anthropics/skills も同じく `anthropic-agent-skills` という別名を持つ。

### main は保護されている

`main` へは直接 push できない。ルールセット「main: PR と CI 通過を必須にする」による強制で、
管理者バイパスは付けていないので自分自身も例外ではない。

| ルール | 意味 |
|---|---|
| `pull_request` | PR 経由でしか変更できない（承認者数は 0 なので一人で回せる） |
| `required_status_checks` | CI の `check` が緑であること。ブランチが最新の main に追いついていること |
| `non_fast_forward` | force push で履歴を壊せない |
| `deletion` | main を消せない |

直接 push すると次のように弾かれる。

```
remote: - Changes must be made through a pull request.
remote: - Required status check "check" is expected.
 ! [remote rejected] main -> main
```

事故対応などでどうしても直接 push が要るときは、GitHub の **Settings > Rules > Rulesets** から
該当ルールセットを開き、Enforcement status を Disabled にする。作業が終わったら Active に戻す。
**戻し忘れないこと。**

CI の `check` は `make check` を走らせる。見るのは2つ。**スキル単体の形式**として、SKILL.md の
`name` とフォルダ名の一致、`description` の有無と長さ（1536 字を超えると切り捨てられ、意図した
場面で呼ばれなくなる）。**配布の構成**として、`marketplace.json` と `plugins/` の対応、
`plugin.json` との description の一致、リポジトリ直下の `skills/` や `skills` 配列が復活していないこと。

### 入れていないもの

`docx` / `pptx` / `xlsx` / `pdf` / `skill-creator` は Anthropic の Proprietary ライセンス。
リポジトリには置かない。claude.ai アカウント側で有効にしたまま使う。

### create-branch が一覧に出ないのは正常

`plugins/git-flow/skills/create-branch/SKILL.md` には `disable-model-invocation: true` が付いている。
モデルが自動で選ぶ一覧には出ず、`/git-flow:create-branch` と明示的に叩いたときだけ動く。
配布の失敗ではない。

## 用語

| 語 | 意味 |
|---|---|
| `~/dev/skills` | 会社Mac にあるスキルの実体。GitHub のローカルリポジトリ |
| `~/dev/skills/docs` | このガイドと設計記録の置き場。スキル本体と同じ履歴で追える |
| `~/.claude/skills` | 書いている途中の1本を置く作業場。`notion-weekly-progress` とその調査記録だけが常駐する |
| GitHub main | 公開先。保護されていて直接 push できない |
| `marketplace.json` | プラグインの一覧。`name` と `source` だけ。プラグイン新設のときだけ更新する |
| `plugins/<plugin>/skills/` | ここに置いたものがそのプラグインとして配られる。所属はフォルダで決まる |
| `studio` / `skill-kit` / `git-flow` | 配布用のプラグイン3つ |
| `plugin update` | 各 Mac が GitHub から取り込む操作 |

## studio に git 系が混ざっていた件は解消済み（2026-09-15）

`studio:git-commit` と `git-flow:git-commit` が並ぶ症状があった。原因は
**claude.ai とデスクトップアプリが `marketplace.json` の `skills` 配列を読まず、
プラグインルート直下の `skills/` を総なめすること。** `source: "./"` だったため
リポジトリ全体が配られ、他プラグインのスキルまで `studio:` に入っていた。

`plugins/<plugin>/skills/` へ分けて `source` をそこへ向けたことで解消した。
経緯と、2 回外した診断の記録は `skill-distribution-pipeline.md` の
「プラグインの二重登録」にある。

再発を疑うときは、アカウントのプラグイン画面で「スキル」タブの本数が
`plugins/<plugin>/skills/` のフォルダ数と合うかを見る。合わなければ、`marketplace.json` の
`source` がプラグインのサブディレクトリを指しているか確認する。
