# スキル運用ガイド（2026-09-13）

会社Mac でスキルを書き、個人Mac まで届けるまでの手順。読者は YIke 本人と、このプロジェクトを引き継ぐ Claude。

**0章と1章は初回に通読する。2〜4章は必要になったときに引く。** 経緯や設計の背景は `skill-distribution-pipeline.md` にある。

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

## 4. 完成したスキルを両方の Mac に届ける → plugin update と再起動

マージしたあと、各 Mac で受け取る。

1. `/plugin marketplace update` — 一覧を取り直す
2. `/plugin update` — 実体を取り込む
3. **Claude Code を再起動する**

`marketplace update` だけでは反映されない。手順2と3まで通して初めて新しいスキルが使える。

個人Mac ではこれだけ。個人Mac の `~/.claude/skills` は常に空で、何も書かない。

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

再発を疑うときは、アカウントのプラグイン画面で「スキル」タブの本数を見る。
`studio` なら 7 本。CLI 側は `claude plugin details studio@yike-skills` で確かめる。
