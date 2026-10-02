---
name: create-worktree
description: >-
  作業用の git worktree を命名規則に沿ったブランチで作り、セッションをその中へ移す。
  リポジトリのファイルを書き換える作業（実装・修正・リファクタ・ドキュメント更新など）を
  始める前に、最初の編集より先に必ず使うこと。ユーザーが worktree やブランチに触れて
  いなくても、変更を伴う依頼なら適用する。「worktree 作って」「ブランチ切って」
  「作業を始めて」「PROJ-123 ログイン修正」のようにチケット番号やタイトルを渡されたときも使う。
  同じリポジトリを複数のセッションで開いていると、1つの作業フォルダに全員の変更が積まれて
  コミットが混ざる。ブランチを切るだけでは防げない（同じフォルダのブランチを全員で
  切り替えることになる）。読むだけ・調べるだけの依頼と、すでに worktree の中にいるときは使わない。
argument-hint: "[TICKET-ID] [title] [type]"
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/create_worktree.sh *), EnterWorktree
---

# create-worktree

作業用の worktree をブランチごと作り、**セッションの作業場所をそこへ移す**。
以降の編集・コミットはすべてその中で行うので、同じリポジトリを開いている
他のセッションと変更が混ざらない。

## 担当範囲

開発の流れのうち、**1番目**を担当する。

1. **作業用の worktree を作る** ← ここ
2. 開発作業をする
3. 時折コミットする → `git-commit`
4. 作業ブランチの内容を PR にまとめる → `create-pr`
5. PR をマージして後始末する（worktree の削除を含む） → `merge-pr`

## いつ実行するか

**リポジトリのファイルを書き換える作業の、最初の編集より前に1回。**
編集を始めてから作ると、元の作業フォルダに変更が取り残される。

実行しないとき:

- 読む・調べる・説明するだけで、ファイルを書き換えない
- git リポジトリの外で作業する
- **すでに worktree の中にいる**（デスクトップアプリがセッション用に作った場合を含む）。
  スクリプトが判定して終了コード 3 で止まるので、そのまま作業を続ける
- ユーザーが「このフォルダで直接やって」「worktree は要らない」と言った

途中で読むだけの作業から書き換える作業に変わったら、その時点で実行する。

## 手順

1. **ブランチ名の材料を決める。**
   - チケット番号（`PROJ-123` など）が渡されていれば `-t` に渡す。無ければ省く
   - type は作業の中身から選ぶ: `feature` / `fix` / `chore` / `docs` / `refactor`
   - title は作業の要約を**英単語2〜5語**で作る（例: `fix login button`）。
     日本語のままだと slug が空になり、ブランチ名から中身が分からなくなる
2. **スクリプトを実行する。**
   ```bash
   ${CLAUDE_SKILL_DIR}/scripts/create_worktree.sh [-t TICKET-ID] [-k type] "<title>"
   ```
3. **結果で分岐する。**
   - 終了コード 0: 最終行 `WORKTREE=<パス>` のパスを `EnterWorktree` の `path` に渡し、
     セッションを移す。`name` は使わない（ブランチ名が命名規則から外れる）
   - 終了コード 3: すでに worktree の中。何もせず作業に進む
   - 終了コード 1: エラー内容をそのまま伝えて止まる。元の作業フォルダで編集を始めない
4. **報告する。** ブランチ名・起点・worktree のパス・コピーした未追跡ファイルを1〜3行で。

## スクリプトがやること

- **起点は origin の既定ブランチ。** 先に fetch する。今のフォルダで誰かが作業中の
  未コミットの変更や、別のブランチの状態を引き継がない。origin が無い・fetch できない
  ときだけ今の HEAD から作る
- **置き場所は `<ルート>/.claude/worktrees/<ブランチ名>`。** Claude Code が自前で worktree を
  作る場所と同じなので、`EnterWorktree` で出入りできる。`.git/info/exclude` に登録するので、
  リポジトリの `.gitignore` は触らず、`git status` にも出ない
- **`.env` 系をコピーする。** ルートにある `.env` / `.env.*` のうち git が無視しているものだけ。
  無いと dev サーバーやテストが起動しない。`.env.example` のように追跡されているものは
  worktree に最初からある

## 移ったあとの注意

- **依存は入っていない。** `node_modules` などは worktree ごとに別。dev サーバーやテストを
  動かす前に、そのプロジェクトの install コマンド（`npm ci` など）を worktree の中で実行する
- **ポートは共有。** フォルダを分けても Mac のポートは1つ。dev サーバーはユーザー共通ルールの
  Claude 用ポートで起動する

## 命名規則

`<type>/<TICKET-ID>-<slug>`。チケットが無ければ `<type>/<slug>`。

- slug は title を小文字化・英数字以外をハイフン化・50文字で切り詰めたもの
- slug が空になると、チケットがあれば `<type>/<TICKET-ID>`、無ければ `<type>/<日時>`

| 入力 | ブランチ |
|---|---|
| `-t PROJ-123 -k fix "Login button not responding"` | `fix/PROJ-123-login-button-not-responding` |
| `-k docs "update readme"` | `docs/update-readme` |
| `-t PROJ-789 -k fix "ログイン修正"` | `fix/PROJ-789` |
