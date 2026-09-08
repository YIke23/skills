# スキル運用ガイド（2026-09-06）

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

`~/.claude/skills` は完成品の置き場ではない。**書いている途中の1本だけを一時的に置く作業場**で、定常状態では空。マージしたら消す。全部を入れるとプラグイン側と二重に並ぶ。

`main` は保護してあり、直接 push できない。GitHub へ届けるには必ずブランチと PR を経由する。

### 深掘りノート: make install の仕様

`make install name=<x>` / `make uninstall name=<x>` は実装済み（2026-09-06）。中身は
`scripts/install.py` で、Makefile からはこれを呼ぶだけ。

- `make install name=<x>` — `skills/<x>/` を `~/.claude/skills/<x>/` へ写す。既にあれば
  入れ替える。**引数なしの全件コピーは作らない**
- `make uninstall name=<x>` — `~/.claude/skills/<x>/` を消す。マージ後の後片付け用。
  無ければ黙って skip するので、二重に叩いても壊れない
- 写す前に、同名のプラグイン版が有効かどうかは見ない。二重に並ぶのは作業中だけなので許容する

`name` は `skills/` 直下のフォルダ名 1 つだけを受ける。空・`/` を含む・`.` で始まるものは
弾く。`uninstall` は宛先が `~/.claude/skills` の直下であることを確かめてから消すので、
`name` を書き間違えて作業場ごと消す事故は起きない。

`uninstall` のあとに他のスキルが残っていれば警告する。定常状態の作業場は空。

## 2. 新しくスキルを作る → ブランチを切って書き、marketplace.json に登録する

marketplace.json への登録が要るのは、この場面だけ。

1. **先に既存を調べる。** `skill-prior-art` を回して、同じ仕事をするスキルが公開されていないか確認する。採用で済むならここで終わる
2. `cd ~/dev/skills && git switch -c add-<name>` — main では作業しない
3. `cp -r template skills/<name>` して SKILL.md を書く
4. `make check` — frontmatter の形式やフォルダ名の一致を機械が見る
5. `make install name=<name>` して Claude Code を再起動し、**実際に呼んで発火するか確かめる**。description を書き間違えても静かに呼ばれなくなるだけなので、ここを飛ばすと気づけない
6. `.claude-plugin/marketplace.json` の該当プラグインに `./skills/<name>` を足す。**これを忘れると個人Mac には永久に届かない**
7. `git push -u origin add-<name>` → `gh pr create` → PR をマージ
8. `make uninstall name=<name>` で作業場を空に戻す。以降はプラグイン版が担当する

## 3. スキルを更新する → 同じ道を通る。marketplace.json は触らない

道筋は2章と同じで、違いは二つだけ。

**marketplace.json は触らない。** パスは既に登録済みで、中身が変わっても一覧は変わらない。

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
| `~/.claude/skills` | 書いている途中の1本を置く作業場。定常状態では空 |
| GitHub main | 公開先。保護されていて直接 push できない |
| `marketplace.json` | どのスキルをどのプラグインとして配るかの一覧。新規追加のときだけ更新する |
| `studio` / `skill-kit` / `git-flow` | 配布用のプラグイン3つ |
| `plugin update` | 各 Mac が GitHub から取り込む操作 |

## studio に git 系が混ざるのは、上げたバンドルが古いから

`studio:git-commit` と `git-flow:git-commit` が並んで見えることがある。**`marketplace.json` の
割り当ては正しく効いており、リポジトリの構成を変える必要はない。**（2026-09-06 確認）

原因は、claude.ai アカウントへ上げた `studio.plugin` バンドルが古いこと。実物はこの形で
残っていた。

```
.../rpm/plugin_<id>/.claude-plugin/plugin.json の skills 配列   → 4 本
.../rpm/plugin_<id>/skills/ の中身                              → 9 本
```

バンドルに 9 本ぶんのフォルダが同梱されているため、git 系まで `studio:` で引けてしまう。
`git-flow` に同じ症状が出ないのは、`git-flow` をアカウントに上げていないから。

直し方は `make build` して `dist/studio.plugin` を **Customize > Plugins** に上げ直すだけ。
手順は README の「studio に git 系が混ざるのは、上げたバンドルが古いから」にある。
**marketplace 側は触らない。**

検討していた「1プラグインに統合」「ディレクトリを分ける」は、どちらも原因に当たらないため
採らない。判断の根拠は `skill-distribution-pipeline.md` の「プラグインの二重登録」にある。

## 詰まったとき

フラット化を試して戻した経緯、`~/.claude/skills` を作業ツリーにする構想がなぜ成立しなかったか、他に検討した接続案は `skill-distribution-pipeline.md` にある。

最終更新 2026-09-06。`make install` / `make uninstall` は実装済みで、2章と3章の手順はそのまま実行できる。
