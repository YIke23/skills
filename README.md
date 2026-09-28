# skills

YIke の自作 Claude スキルを1箇所で管理し、2台の Mac と2つの claude.ai アカウントへ配るリポジトリ。
GitHub のこのリポジトリがそのまま marketplace（`yike-skills`）になり、構成は
[anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) に合わせて
プラグインごとに `plugins/<plugin>/` で束ねている。

- 開発状況: 稼働中（スキルの追加・更新を続けている）
- 開発URL: なし
- 本番URL: なし（配布は `main` から marketplace 経由）
- 最終確認日: 2026-09-28

## ディレクトリ構成

```
.claude-plugin/   marketplace.json。プラグインの一覧で、name と source だけを書く
plugins/          配るプラグイン。plugins/<plugin>/skills/<name>/ が1スキル（Markdown / Python）
template/         新しいスキルの雛形（SKILL.md）
scripts/          make check と make install の中身（Python）
docs/             運用ガイドと設計判断の記録
.github/          CI（make check）と PR テンプレート
```

スキルがどのプラグインに属するかは、`plugins/<plugin>/skills/` のどこに置いたかだけで決まる。

| プラグイン | 役割 | 配布先 |
|---|---|---|
| `studio` | 画像・アイコン、解説記事、ドキュメント、README、会議資料をつくる | Mac + claude.ai アカウント |
| `skill-kit` | スキル着手前の先行事例調査と、入っているスキルの棚卸し | Mac + claude.ai アカウント |
| `git-flow` | ブランチ・コミット・PR・マージ・Issue の定型作業 | Mac のみ（手元の git を触るため） |

呼び出しは `/studio:eli15` のように `プラグイン名:スキル名` になる。

## セットアップ

前提: Claude Code の CLI / GitHub に SSH で接続できること / Python 3（CI は 3.12）と `make` / `gh`（PR を出すため）

1. リポジトリを取得する

   ```bash
   git clone git@github.com:YIke23/skills.git ~/dev/skills
   ```

2. 点検を通す。`エラー 0 件` と出れば手元の状態は正常

   ```bash
   cd ~/dev/skills && make check
   ```

3. この Mac に marketplace を登録する。**SSH の URL で登録する**（HTTPS だと、裏で marketplace を取り直す処理だけが無言で失敗する）

   ```bash
   claude plugin marketplace add git@github.com:YIke23/skills.git
   ```

4. プラグインを入れる。Claude Code を再起動し、新しいセッションで `/studio:eli15` が候補に出れば完了

   ```bash
   claude plugin install studio@yike-skills
   claude plugin install skill-kit@yike-skills
   claude plugin install git-flow@yike-skills
   ```

claude.ai アカウントへの入れ方と、初回に足しておく設定は関連文書の運用ガイド（4〜5章）にある。

## ブランチとデプロイ先

| ブランチ | 役割 | マージ先 | デプロイ先 |
|---|---|---|---|
| `main` | 配布の正。保護されていて直接 push できない | — | Mac は `claude plugin update`、claude.ai は管理画面の「更新」で取り込む（自動では切り替わらない） |
| 作業ブランチ（`add-<name>` / `fix-<name>` など） | 1テーマ1ブランチ。`main` から切る | `main` | — |

`main` へは PR 経由でのみ入れる。承認者は不要で自分でマージしてよいが、CI の `check`（`make check`）が
緑で、ブランチが最新の `main` に追いついている必要がある。

## よく使うコマンド

| コマンド | 用途 |
|---|---|
| `make check` | SKILL.md の形式と配布の構成を点検する（CI と同じ） |
| `make install name=<name>` | 作業中の1本を `~/.claude/skills` へ写して試す |
| `make uninstall name=<name>` | マージ後に作業場（`~/.claude/skills`）から消す |
| `claude plugin update studio@yike-skills` | マージ後に Mac へ取り込む（`skill-kit` / `git-flow` も同様） |

## 関連文書

| 資料 | 内容 | いつ読むか |
|---|---|---|
| [スキル運用ガイド](docs/skill-workflow.md) | 作る・直す・配る・新しい Mac に入れる手順と、main 保護などの決まりごと | スキルを作る・直す・配るとき |
| [スキル配布パイプライン](docs/skill-distribution-pipeline.md) | 今のレイアウトと配布方式に至った経緯と設計判断 | 構成や配布方式を変えたくなったとき、同じ症状が再発したとき |
| [meeting-deck 先行事例調査](docs/meeting-deck-prior-art.md) | 会議用の単一 HTML 資料スキルの既存調査 | meeting-deck を作り直す・同種を探すとき |
| [merge-pr 先行事例調査](docs/merge-pr-prior-art.md) | PR のマージと後始末のスキルの既存調査 | merge-pr を作り直す・同種を探すとき |
| [readme-builder 先行事例調査](docs/readme-builder-prior-art.md) | 引き継ぎ向け README スキルの既存調査 | readme-builder を作り直す・同種を探すとき |
| [skill-inventory 先行事例調査](docs/skill-inventory-prior-art.md) | スキル一覧と GitHub との差分を出すスキルの既存調査 | skill-inventory を作り直す・同種を探すとき |
