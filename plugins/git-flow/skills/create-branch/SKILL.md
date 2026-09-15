---
name: create-branch
description: Create and switch to a git branch from a ticket ID and title. Use whenever the user gives a ticket ID/title (e.g. "PROJ-123 ログイン修正") and wants a branch, or says "ブランチ切って" / "ブランチ作って" / "start work on this ticket" / "create a branch".
disable-model-invocation: true
argument-hint: [TICKET-ID] [title] [type]
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/create_branch.sh *)
---

# Create Branch

チケット情報から命名規則に沿った git ブランチを作成し、切り替える。

## 手順

`${CLAUDE_SKILL_DIR}/scripts/create_branch.sh $ARGUMENTS` を実行し、
出力された「作成して切り替えました: <ブランチ名>」を報告する。
エラーが出た場合はその内容をそのまま伝える。

## 引数

- `$0` TICKET-ID … 例 `PROJ-123`（必須）
- `$1` title … チケットのタイトル。スペースや日本語を含む場合はダブルクォートで囲む
- `$2` type … `feature` / `fix` / `chore` など（省略時は `feature`）

## 命名規則

`<type>/<TICKET-ID>-<slug>`
- slug はタイトルを小文字化・英数字以外をハイフン化・50文字で切り詰めたもの
- タイトルが日本語のみなどで slug が空になる場合は `<type>/<TICKET-ID>` になる

**例1:**
Input: `PROJ-123 "Login button not responding" fix`
Output: `fix/PROJ-123-login-button-not-responding`

**例2（type省略）:**
Input: `PROJ-456 "Add CSV export"`
Output: `feature/PROJ-456-add-csv-export`

**例3（日本語タイトル → slugが空）:**
Input: `PROJ-789 "ログイン修正" fix`
Output: `fix/PROJ-789`
