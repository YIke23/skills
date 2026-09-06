# スキル配布パイプライン（2026-09-06 / 分担をやめた）

日々の手順は `skill-workflow.md` にある。こちらは経緯と設計判断の記録。

## 現在の決定

**スキル作りは会社Mac の Claude Code で一気通貫。工程を Cowork と分担しない。**（2026-09-06）

**レイアウトは anthropics/skills 準拠を維持する。`skills/<name>/` を変えない。**
リポジトリのルートを `~/.claude/skills` に一致させるための「フラット化」は**中止した**。
このドキュメントの旧版に書かれていたフラット化の手順は、実行してはいけない。

接続方式は **`make install` によるコピー**に決定（2026-09-05）。`~/dev/skills/skills/*` を `~/.claude/skills/` へ写す。symlink 案と worktree 案は下の表のとおり検討したうえで採らなかった。**2026-09-06 に `scripts/install.py` として実装済み**（仕様は `skill-workflow.md` の「深掘りノート: make install の仕様」）。

## 2026-09-06 の判断: 分担をやめる

旧版は「編集・コミットは Claude Code、Cowork は事前調査・下書き・記録」と分担を定めていた。これを**取り消す**。理由は3つ。

**1. 検証工程が構造的にできない。** Cowork は `~/.claude` に触れない（保護領域として拒否される）。`make install` も、Claude Code の再起動も、発火テストも、eval もできない。description の書き間違いは「静かに呼ばれなくなる」という壊れ方をするので、実際に呼んで確かめる工程を飛ばすと気づけない。つまり Cowork が担えるのは工程の前半だけで、後半ははじめから Claude Code の仕事だった。

**2. 分断が原因の事故を既に起こしている。** 下の「何が起きたか」に記録したフラット化の一件は、手順を書いた側が `git log` を読めなかったことが原因。PR #4・#5 がマージされ、#6 で取り消した。能力の問題ではなく、履歴を読める側と手順を書く側が別だったことが原因。

**3. 唯一の強みが差になっていない。** Cowork の優位だと思っていた事前調査は、Claude Code にも同じ道具がある。WebSearch / WebFetch は標準、`skill-prior-art` はアカウント側のスキルなので同期される、MCP コネクタは `.mcp.json` で足せる。違うのは記録の置き場所だけだった。しかもスキル作りで最も効く調査は「自分の9本と重複していないか」で、それはリポジトリの中でやるほうが当たりが良い。

### Cowork を使う場面（限定）

- 会社Mac が手元にない（個人Mac・外出先）。リポジトリの実体が会社Mac にしかない以上、そこでは代替手段がない
- リポジトリに入らない資料や記録
- 放置して回す長い調査。クラウド実行と定期実行は Cowork だけの機能

いずれも「工程の途中で切る」使い方ではない。**線引きは、リポジトリに入るものは全部 Claude Code。**

## 何が起きたか（記録）

旧版の設計メモに「リポジトリをフラット化し、`~/.claude/skills` をワーキングツリーにする」と書かれていた。それを引き継いで Claude Code 用の移行プロンプトを作り、実行された。

`7d737f5 refactor: anthropics/skills と同じレイアウトに移行` という、**意図的にそのレイアウトへ寄せたコミットが git log に残っていた**にもかかわらず、確認せずに戻す指示を出したのが原因。

経過と結果:

- PR #4（フラット化）と PR #5（`make sync` 追加）が main にマージされた
- PR #6 の revert（`bd67a61`）で両方とも取り消し済み
- **現在の main = `9f341e3`。`d3e1891` との差分は `README.md` だけ**（`git diff --stat d3e1891 main` → README.md 1 ファイルのみ）。revert 後に入った #7〜#9 はいずれも README の改稿
- `skills/` 配下の9スキル、`template/`、`marketplace.json` の `./skills/x` パス、Makefile（build / check / clean）はすべて元通り
- 同じ経緯で `~/dev/skills` も一度削除したが、**2026-09-05 に復元済み**。作業ツリーはクリーン、remote は `git@github.com:YIke23/skills.git`。デスクトップアプリが作る `Claude outputs/` は `.git/info/exclude` でローカル除外してある

GitHub 側で失われたものは無い。`make sync` は revert に含まれたので、いまは存在しない。

## 確認済みの状態（2026-09-06）

会社Mac の Claude Code で実際に見て確定させた事実。

| 見たもの | 結果 |
|---|---|
| `git log` / `git status` | main = `9f341e3`、作業ツリーはクリーン。ローカルブランチは main のみ |
| `~/.claude/skills` | **空**。フラット化の残骸は無く、作業場として正常な状態 |
| `Makefile` | 確認時点は `build` / `check` / `clean` の3つ。**この PR で `install` / `uninstall` を追加した** |
| `marketplace.json` | `studio` に4本、`git-flow` に5本。意図どおり分かれている |
| 導入済みプラグイン | 会社Mac に `studio@yike-skills` と `git-flow@yike-skills` の**両方**（sha `583eb49`、2026-09-05 導入） |
| 生えているスキル | `git-flow` は 4 本、`studio` は 8 本 |
| `skills/eli15/` | 確認時点は `SKILL.md` と `assets/base.css` のみで `check_contrast.py` は無かった。**別 PR で `scripts/check_contrast.py` を実装し、参照切れを解消した** |

**プラグインの導入状態は `skill-workflow.md` が正しかった。** 旧版のこの文書が書いていた
「会社Mac にはプラグインを入れない」は事実と違う。両方入っている前提で読むこと。

導入済み sha `583eb49` と main `9f341e3` の差は README.md だけなので、**プラグイン版が数コミット
遅れていてもスキル本体は最新**。慌てて `plugin update` する必要はない。

## プラグインの二重登録: 構成変更は要らない

`studio:git-commit` と `git-flow:git-commit` が並ぶ件。旧版は原因を「両プラグインの `source` が
どちらも `"./"` で、`skills` 配列の絞り込みが効いていない」と推定していた。**この推定は誤り。**

### 絞り込みは効いている

`git-flow` が反証になる。

| 見るもの | 中身 |
|---|---|
| `~/.claude/plugins/cache/yike-skills/git-flow/<sha>/skills/` | 9 フォルダ（リポジトリ全体の複製） |
| 実際に生えるスキル | `skills` 配列に書いた 5 本のうち 4 本 |

`source: "./"` はリポジトリ全体を複製するので、キャッシュには必ず 9 フォルダが並ぶ。
**フォルダの数は根拠にならない。** 同じ `source: "./"` を使っていて `git-flow` は絞れている。

5 本に対して 4 本なのは `create-branch` に `disable-model-invocation: true` が付いているため。
明示的に `/git-flow:create-branch` と叩いたときだけ動く。配布の失敗ではない。

### 混ざっているのは inline のほう

`studio` だけ実体が二重にある。marketplace 版とは別に、claude.ai アカウントへ上げた `.plugin`
バンドルが入っており、その中身が 9 本ある。

```
.../rpm/plugin_01Dzt7trPpH4REHvpeBGFi83/.claude-plugin/plugin.json の skills 配列   → 4 本
.../rpm/plugin_01Dzt7trPpH4REHvpeBGFi83/skills/ の中身                              → 9 本
```

`studio` が 8 本見えるのは、この 9 フォルダから `create-branch` を引いた数と一致する。
`git-flow` に同じ症状が出ないのは、`git-flow` をアカウントに上げていないから。

### 2案の判断材料

原因が inline バンドルである以上、**どちらの案も症状に当たらない。**

| 案 | 二重登録が直るか | 代償 |
|---|---|---|
| **1プラグインに統合** | **直らない。** 古いバンドルがアカウントに残る限り `studio:` は 9 本を出し続ける | `studio` / `git-flow` の呼び分けを失う。`git-flow` をアカウントに上げない運用も崩れる |
| **ディレクトリを分ける** | **直らない。** `source` をサブディレクトリへ向けてもキャッシュの複製範囲が変わるだけで、既に上げたバンドルの中身は変わらない | `7d737f5` が寄せた anthropics/skills 準拠のレイアウトを捨てる。PR #4 で一度壊した道と同じ |

**採る手は「どちらも採らない」。** `scripts/build.py` は `skills` 配列を回して該当フォルダだけを
staging へ写すので、いまビルドすれば 4 本のバンドルができる。上げ直せば直る。

```bash
make build
python3 -c "import zipfile; z=zipfile.ZipFile('dist/studio.plugin'); print(sorted({n.split('/')[1] for n in z.namelist() if n.startswith('skills/') and n.count('/') > 1}))"
```

4 本であることを確かめてから `dist/studio.plugin` を **Customize > Plugins** に上げ直す。
会社と個人で 1 回ずつ。**marketplace 側は触らない。** 手順は README にも同じものがある。

差し替えはリポジトリの変更ではなく手作業なので、コミットには現れない。上げ直したらこの節に日付を書き足す。

## 未確認 / 未実装

確認したら結果を「確認済みの状態」に書き、項目を消す。

- **個人Mac がフラット化中に `plugin update` していないか。** 会社Mac からは見えない。していれば
  旧 marketplace を掴んでいるので取り直す必要がある。個人Mac 側で確認する

## 接続方式の検討（決着済み）

フラット化の狙いは**「同じスキルを二か所に置かない」の一点**だった。書く場所（リポジトリ）と読まれる場所（`~/.claude/skills`）が別なので、あいだにコピーが要る。コピーを忘れると、動いているスキルと履歴に残るスキルが食い違い、しかも壊れないので気づかない。

狙い自体は筋が通っている。**払い方（リポジトリの形を捨てる）が行きすぎていた。**

| 案 | 内容 | 判断 |
|---|---|---|
| **コピー** | `make install` で写し、ずれは `make check` で見張る | **採用。** 確実に動き、既存の build / check / clean と揃う |
| symlink | `~/.claude/skills` を `<repo>/skills` へのリンクにする | 見送り。Claude Code が symlink を辿るか未検証で、辿らなければスキルが黙って消える |
| git worktree | `~/.claude/skills` を main 専用の worktree にする | 見送り。ブランチ切替の問題は解けるが、構成が重い |

なお、フラット化が必要になったのは `~/.claude/skills` の直下にスキルが並ぶのに対し、リポジトリは根の直下に `.claude-plugin` `scripts` `template` を持ち、スキルが一段深いから。根で両者を重ねようとすると「根の直下で SKILL.md を持つフォルダ = スキル」という規則が要り、`template/SKILL.md` がスキルとして登録される事故が起きた。

## 変わらない決定

- **スキルの編集・コミット・検証はすべて会社Mac の Claude Code で行う。**（2026-09-06 に「Cowork は事前調査・下書き・記録に使う」を取り消した）
- ドキュメントは `~/dev/skills/docs/` に置く。スキル本体と同じ履歴で追えるようにするため
- 個人Mac は `plugin update` で受け取るだけ
- `marketplace update` だけでは反映されない。`plugin update` と再起動まで必要

## 教訓

既存のレイアウトやルールを変える手順を書く前に、**そのレイアウトを作ったコミットが何を意図していたかを git log で確認する。** リファクタのコミットメッセージは、その時点の決定の記録になっている。

そして、**確認できない場所の手順を書かない。** 履歴もローカルの状態も見えない側が手順を書くと、事故は「間違った手順」ではなく「確認されていない前提」として混入する。
