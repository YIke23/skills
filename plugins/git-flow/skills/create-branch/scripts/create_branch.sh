#!/usr/bin/env bash
#
# create_branch.sh
# チケット情報から命名規則に沿った git ブランチを作成し、切り替える。
#
# 使い方:
#   create_branch.sh <TICKET-ID> "<title>" [type]
#     TICKET-ID : 例 PROJ-123 (必須)
#     title     : チケットのタイトル (スペース/日本語を含む場合はクォートで囲む)
#     type      : feature | fix | chore など (省略時は feature)
#
# 命名規則:
#   <type>/<TICKET-ID>-<slug>
#   slug が空になる場合は <type>/<TICKET-ID>

set -euo pipefail

ticket_id="${1:-}"
title="${2:-}"
type="${3:-feature}"

# --- 引数チェック ---
if [ -z "$ticket_id" ]; then
  echo "エラー: チケットIDが指定されていません。" >&2
  echo '使い方: create_branch.sh <TICKET-ID> "<title>" [type]' >&2
  exit 1
fi

# --- gitリポジトリ内か確認 ---
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "エラー: ここは git リポジトリではありません。" >&2
  exit 1
fi

# --- タイトルから slug を生成 ---
# 小文字化 → 英数字以外をハイフン → 連続ハイフンを1つに → 前後のハイフン除去 → 50文字に切り詰め
slug="$(printf '%s' "$title" \
  | tr '[:upper:]' '[:lower:]' \
  | LC_ALL=C sed 's/[^a-z0-9]/-/g' \
  | sed 's/-\{2,\}/-/g' \
  | sed 's/^-*//; s/-*$//' \
  | cut -c1-50 \
  | sed 's/-*$//')"

# --- ブランチ名を組み立て（slugが空ならID部分のみ）---
if [ -z "$slug" ]; then
  branch="${type}/${ticket_id}"
else
  branch="${type}/${ticket_id}-${slug}"
fi

# --- 既存ブランチとの衝突チェック ---
if git show-ref --verify --quiet "refs/heads/${branch}"; then
  echo "エラー: ブランチ '${branch}' はすでに存在します。" >&2
  echo "既存ブランチに切り替えるには: git switch ${branch}" >&2
  exit 1
fi

# --- ブランチ作成 & 切り替え（git switch優先、なければ checkout）---
if git switch -c "$branch" >/dev/null 2>&1; then
  :
else
  git checkout -b "$branch"
fi

echo "作成して切り替えました: ${branch}"
