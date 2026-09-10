# 3系統の詳細と、出力の読み方

`SKILL.md` が参照する背景資料。**macOS の Claude Code 2.1.260 で
2026-09-10 に実測して確認した内容。** パスの形やコマンドの出力形式は本体の更新で変わりうるので、
書いてある構造が合わなくなったら、決め打ちで直すより実物を見て確認し直すこと。

## 目次

- [なぜ系統を分けて数えるのか](#なぜ系統を分けて数えるのか)
- [系統ごとの実体](#系統ごとの実体)
- [差分をどう計算しているか](#差分をどう計算しているか)
- [出力の読み方（JSON キー）](#出力の読み方json-キー)
- [踏んではいけない7つの罠](#踏んではいけない7つの罠)
- [公式の手段でできること・できないこと](#公式の手段でできることできないこと)

## なぜ系統を分けて数えるのか

セッションに生えるスキルは1箇所から来ていない。3系統が同時にロードされ、
**それぞれ版の形式も更新経路も違う。**

だから「全部で何本あるか」だけを数えても行動につながらない。
`studio:eli15` が古いとき、直し方は系統によって変わる。CLI プラグインなら
`plugin update`、デスクトップなら claude.ai 側の設定、ユーザースキルなら手で直す。
系統が分からないと、どのボタンを押せばいいかが分からない。

## 系統ごとの実体

### 組み込み

本体バイナリの中にある。**ディスクに SKILL.md が無い**ので、ファイル走査では見つからない
（`find <claude.app>/Contents -name SKILL.md` の結果が 0 件であることを確認済み）。

- 名前空間: 付かない（素の名前で呼べる）
- 版: 本体のバージョンに追随する。個別の版を持たない
- 差分: 概念が無い。本体を更新すれば全部入れ替わる
- **列挙: できない。** セッションのスキル一覧が唯一の正

### CLI のプラグイン

```
~/.claude/plugins/
├── installed_plugins.json                       # 何をどの SHA で入れているか
├── marketplaces/<mp>/                           # marketplace の git クローン ← GitHub との接点
│   └── .claude-plugin/marketplace.json          # プラグイン → 配るスキルの対応
└── cache/<mp>/<plugin>/<sha>/                   # 展開されたツリー（実際にロードされる）
    ├── .in_use                                  # 稼働中プロセスが握っているマーカー
    ├── skills/<name>/SKILL.md
    └── commands/<name>.md
```

- 名前空間: `<plugin>:<skill>`
- 版: **git SHA。** `plugin list --json` の `version` が marketplace リポジトリのコミット SHA
- 取り方: `claude plugin list --json`、`claude plugin marketplace list --json`
- **GitHub との差分が取れる唯一の系統。** marketplace が git クローンなので比較の基準がある

`marketplaces/<mp>/` が GitHub の作業コピーそのものなので、`git fetch` + `rev-list` で
リモートとの位置関係が出る。**ここが差分の土台。**

### デスクトップアプリのプラグイン

```
~/Library/Application Support/Claude/local-agent-mode-sessions/<A>/<B>/rpm/
├── manifest.json                     # プラグインの id / name / marketplaceName / updatedAt
└── plugin_<id>/
    ├── .claude-plugin/plugin.json    # name / version（semver）
    ├── .mcp.json                     # MCP サーバーを同梱している場合
    └── skills/<name>/SKILL.md
```

- 名前空間: `<plugin>:<skill>`
- 版: **semver**（`plugin.json` の `version`）。`manifest.json` の `updatedAt` で更新時刻も分かる
- **`claude plugin list` に載らない。** `installed_plugins.json` にも無い
- 差分: 取れない。手元に git クローンが無く、更新はアプリが行う

### デスクトップのスキル（`anthropic-skills`）

```
~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/<B>/<A>/
├── .claude-plugin/plugin.json    # name: "anthropic-skills"
├── manifest.json                 # skills[]: skillId / name / description ← 有効なものの正
└── skills/<name>/SKILL.md
```

claude.ai のスキル設定で有効化したものを、アプリが**1個の合成プラグインにまとめて**渡す。
`plugin.json` の description が `"Anthropic-managed skills for Claude Desktop"`。

- 名前空間: `anthropic-skills:<skill>`
- 差分: 取れない
- **ディレクトリには有効化していないスキルも置かれている。** 現役の判定は
  `manifest.json` の `skills` 配列が正。ディレクトリ走査だけだと無効なものまで数える
  （収集スクリプトは差を `dormant_on_disk` に出す）

**パス順が rpm 側と入れ替わっている。** rpm は `<A>/<B>/rpm/`、こちらは
`skills-plugin/<B>/<A>/`。決め打ちで組み立てると片方が空振りするので glob で探す。

### ユーザー / プロジェクト

- `~/.claude/skills/<name>/` — 保存した瞬間に効く作業場
- `<repo>/.claude/skills/<name>/` — そのリポジトリ限定
- 名前空間: 付かない（素の名前）
- 版: 無い。**だから git クローンの同名スキルとファイル単位で比べるしかない**

## 差分をどう計算しているか

3つの差分は**独立に起こる。** どれか1つが 0 でも他が 0 とは限らない。

### 1. marketplace ↔ GitHub

```bash
git -C <marketplaces/mp> fetch --quiet
git -C <marketplaces/mp> rev-list --left-right --count HEAD...@{u}   # → "ahead behind"
```

`behind > 0` なら GitHub に未取得のコミットがある。`upstream` が未設定なら比較できないので、
`sync_note` にそう書く（空欄にすると同期済みに見える）。

### 2. 導入済みプラグイン ↔ marketplace の HEAD

`plugin list --json` の `version` が marketplace リポジトリのコミット SHA なので、
git で正確に計算できる。

```bash
git -C <marketplaces/mp> rev-list --count <cache_sha>..HEAD          # 何コミット遅れているか
git -C <marketplaces/mp> diff --name-only <cache_sha>..HEAD -- <そのプラグインが配るパス>
```

2行目が肝。**そのコミット差が、このプラグインの中身に本当に触れているか**を見る。
触れていなければ「遅れているが実害なし」で、更新の優先度が下がる。
比較対象のパスは marketplace.json の `skills` 配列から取る。

`cache_sha` がクローンに存在しない（`git cat-file -e` が失敗する）場合は `unrelated`。
改名や URL 変更の後に入れ直していないと起きる。

### 3. 手元のコピー ↔ GitHub 側の同名スキル

`~/.claude/skills/<name>/` と、marketplace クローンの `skills/<name>/` の**ファイル単位の比較**。
相対パスの集合と、各ファイルの sha256 先頭12桁を突き合わせる。

- `missing_files` — リポジトリにあって手元に無い → 手元のコピーが不完全
- `extra_files` — 手元にあってリポジトリに無い → 未反映の追加かもしれない
- `differing_files` — 両方にあるが中身が違う → 未反映の編集かもしれない

**版の比較では絶対に捕まらない差分がここ。** `plugin list` はプラグインの版しか見ないので、
「リポジトリには `references/` と `scripts/` があるのに手元のコピーは SKILL.md だけ」という
状態を同期済みに見せてしまう。参照ファイルが欠けたスキルは動作中に失敗する。

比較の基準にしているクローン自体が GitHub より遅れている場合、その旨を `note` に書く。
遅れたクローンと一致していることは、GitHub と一致していることを意味しない。

## 出力の読み方（JSON キー）

| キー | 中身 |
|---|---|
| `host` | cwd、本体バージョン、使った claude バイナリ、`fetched`（false なら ahead/behind は古い） |
| `builtin_skills.enumerable` | 常に `false`。**「無い」ではなく「ここでは分からない」** |
| `marketplaces[]` | `remote` / `head_sha` / `ahead` / `behind` / `dirty` / `sync_note` / `plugins_declared` |
| `plugins[]` | `origin` / `version` / `version_kind` / `skill_count` / `command_count` / `drift` |
| `plugins[].drift.state` | `current` / `behind` / `unrelated` / `not-comparable` / `unknown` |
| `plugins[].drift.changed_paths` | 遅れている区間でこのプラグインの中身が変わったファイル。空なら実害なし |
| `skills[]` | 1行 = 1つの呼び出し可能なもの。`kind` が `skill` か `command` |
| `skills[].invocable_as` | 実際に打つ形。素の名前か名前空間付きかが出自の手掛かり |
| `loose_skill_drift[]` | 手元のコピーとリポジトリのファイル単位の差 |
| `loose_skill_drift[].state` | `in-sync` / `diverged` / `untracked` |
| `loose_skill_drift[].reference` | 照合に使ったクローンのパス。marketplace のクローンか作業クローン |
| `loose_skill_drift[].also_loaded_as` | 同名がプラグインからも生えている場合の名前空間 |
| `skills[].manual_only` | `disable-model-invocation: true`。人が打つスラッシュ専用で、モデルからは呼べない |
| `totals.manual_only` | 上の件数。`totals.skills` からは除いてある |
| `shadowed_plugins[]` | プラグインとして配られているのに手元のコピーが使われているもの |
| `duplicate_names` | `kind:name` → その名前を持つ全実体（`namespace` / `origin` / `path`） |
| `totals` | `marketplaces_behind` / `plugins_behind` / `loose_diverged` が要対応の件数 |
| `notes` | 収集中に欠けた情報。**空でなければ必ず報告に含める** |

## 踏んではいけない7つの罠

すべて実測で確認済み。収集スクリプトは対策済みだが、出力を解釈するときにも効く。

1. **`claude plugin list` はデスクトップアプリ側を1件も返さない。**
   実測では CLI が 4 プラグインを返す一方、セッションには 9 プラグインが生えていた。
   CLI だけ見ると半分以上落ちる。

2. **キャッシュ配下の `skills/` を数えても意味がない。**
   marketplace の `source: "./"` はリポジトリ全体を展開するので、生えないスキルの
   ディレクトリまで並ぶ。実測では `git-flow` のキャッシュに 9 個のディレクトリがあり、
   実際に生えるのは `marketplace.json` の `skills` が選んだ 4 個だけだった。
   `claude plugin details <name>@<mp>` も正しい 4 個を返す。

3. **`plugin list --json` の `version` は semver ではなく git SHA。**
   だから遅れを git で正確に計算できる。semver として比較しようとすると何も分からない。

4. **`marketplace update` 済みでも導入済みプラグインの版は切り替わらない。**
   `installed_plugins.json` が古い SHA を指したまま残る。稼働中プロセスが
   `.in_use` マーカーで旧ツリーを握っているため。つまり
   **「marketplace は GitHub と同期しているのにプラグインが古い」が正常に起こる。**
   marketplace の ahead/behind だけ見ていると見逃す。切り替えには
   `plugin update <plugin>@<mp>` と再起動が要る。

5. **`local-agent-mode-sessions` のパス順は系統ごとに入れ替わる。**
   rpm は `<A>/<B>/rpm/`、skills-plugin は `skills-plugin/<B>/<A>/`。glob で探す。
   また過去セッションの残骸が並ぶので、mtime の新しいものを現役として扱う。

6. **組み込みスキルはディスクに SKILL.md を持たない。** セッションの一覧が正。

7. **スキルを1本も持たないプラグインがある。** `commit-commands` は `commands/*.md` だけを配る。
   セッションの一覧にはスキルと並んで出てくるので、`skills/` しか見ると
   「使えるのに表に無い」ことになる。だから `kind` で区別して両方集める。

## 公式の手段でできること・できないこと

要件の部品はすべて公式にある。要件そのものを満たすものが無い。

| 公式の手段 | 返すもの | 足りないこと |
|---|---|---|
| `plugin list --json` | 導入済みプラグインの id / SHA / パス / 更新時刻 | プラグイン単位。**デスクトップ側が丸ごと欠ける** |
| `plugin list --available --json` | `{installed, available}` の2配列 | 新旧の比較は自前。marketplace のカタログ全部が並ぶ |
| `plugin details <name>@<mp>` | 1プラグインの構成とトークン量 | **1個ずつ。** 横断の表にならない |
| `plugin marketplace list --json` | marketplace 名 / source / url / パス | 差分は取らない |
| `plugin marketplace update` | クローンを最新にする | **更新してしまうので差分が消える** |
| `/skill-doctor` | スキルの診断 | 単体の健全性寄り。3系統横断の台帳ではない |

`claude` CLI が PATH に無い Mac がある。`$CLAUDE_CODE_EXECPATH`
（デスクトップアプリ同梱のバイナリ）を優先して探すこと。収集スクリプトはそうしている。
なおこのバイナリで `plugin` 系のサブコマンドは通るが、`claude -p`（推論を伴う起動）は
OAuth セッションをアプリ側が持っているため落ちる。


## 照合先の選び方（GitHub が正）

手元のコピーを比べる相手は2種類ある。どちらも GitHub そのものではなく、その複製。

| 照合先 | 場所 | 更新のされ方 |
|---|---|---|
| marketplace のクローン | `~/.claude/plugins/marketplaces/<mp>/` | `plugin marketplace update` を打つまで止まる |
| 作業クローン | `~/dev/skills` | ユーザーが直接 pull / commit する |

**両方に同名があるときは、GitHub とのずれが小さい方を採る。** `(遅れ, 進み, 未コミットの変更)`
の順に並べて先頭を選ぶ。marketplace のクローンだけを基準にすると、それ自体が遅れている場合に
「手元が新しすぎる」と読み違える。

作業クローンを採ったとき、それが `ahead > 0`（未 push）か dirty なら、
**その事実を必ず note に書く。** 正は GitHub 上の main であって、
手元の作業クローンではないため。

`disable-model-invocation: true` のスキルは、ディスクにあってもモデルの一覧に出ない。
`totals.skills` から外し、`totals.manual_only` で別に数える。台帳の行には残して
「手動のみ」と印を付ける — 存在はするので、消えたように見せない。
