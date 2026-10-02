#!/usr/bin/env bash
#
# create_worktree.sh
# 命名規則に沿ったブランチで git worktree を作る。セッションの切り替えはしない
# （呼び出し側が EnterWorktree の path に、最終行の WORKTREE= を渡す）。
#
# 使い方:
#   create_worktree.sh [-t TICKET-ID] [-k type] "<title>"
#     -t TICKET-ID : 例 PROJ-123（任意）
#     -k type      : feature | fix | chore など（省略時は feature）
#     title        : 作業の要約。英単語で短く（日本語だけだと slug が空になる）
#
# 命名規則:
#   ブランチ   <type>/<TICKET-ID>-<slug> 。チケットが無ければ <type>/<slug>
#   slug も空なら日時（<type>/<yyyymmdd-hhmm>）
#   置き場所   <リポジトリのルート>/.claude/worktrees/<ブランチ名の / を - にしたもの>
#   起点       origin の既定ブランチ（取れなければ今の HEAD）
#
# 終了コード: 0=作成した / 1=エラー / 3=すでに worktree の中にいるので作らなかった

set -euo pipefail

ticket_id=""
type="feature"
while getopts "t:k:" opt; do
  case "$opt" in
    t) ticket_id="$OPTARG" ;;
    k) type="$OPTARG" ;;
    *) echo '使い方: create_worktree.sh [-t TICKET-ID] [-k type] "<title>"' >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))
title="${1:-}"

# --- gitリポジトリ内か確認 ---
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "エラー: ここは git リポジトリではありません。" >&2
  exit 1
fi

# --- すでに worktree の中なら作らない（デスクトップアプリが作った場合を含む）---
git_dir="$(cd "$(git rev-parse --git-dir)" && pwd -P)"
common_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)"
if [ "$git_dir" != "$common_dir" ]; then
  echo "SKIP: すでに worktree の中にいます: $(git rev-parse --show-toplevel)（ブランチ $(git branch --show-current)）"
  exit 3
fi

root="$(git rev-parse --show-toplevel)"

# --- タイトルから slug を生成 ---
# 小文字化 → 英数字以外をハイフン → 連続ハイフンを1つに → 前後のハイフン除去 → 50文字に切り詰め
slug="$(printf '%s' "$title" \
  | tr '[:upper:]' '[:lower:]' \
  | LC_ALL=C sed 's/[^a-z0-9]/-/g' \
  | sed 's/-\{2,\}/-/g' \
  | sed 's/^-*//; s/-*$//' \
  | cut -c1-50 \
  | sed 's/-*$//')"

# --- ブランチ名を組み立て ---
if [ -n "$ticket_id" ] && [ -n "$slug" ]; then
  branch="${type}/${ticket_id}-${slug}"
elif [ -n "$ticket_id" ]; then
  branch="${type}/${ticket_id}"
elif [ -n "$slug" ]; then
  branch="${type}/${slug}"
else
  branch="${type}/$(date +%Y%m%d-%H%M)"
fi

dir="${root}/.claude/worktrees/${branch//\//-}"

# --- 衝突チェック ---
if git show-ref --verify --quiet "refs/heads/${branch}"; then
  echo "エラー: ブランチ '${branch}' はすでに存在します。" >&2
  existing="$(git worktree list --porcelain | awk -v b="branch refs/heads/${branch}" '/^worktree /{w=substr($0,10)} $0==b{print w}')"
  if [ -n "$existing" ]; then
    echo "そのブランチの worktree: ${existing}" >&2
  fi
  exit 1
fi
if [ -e "$dir" ]; then
  echo "エラー: '${dir}' がすでにあります。" >&2
  exit 1
fi

# --- 起点を決める（origin の既定ブランチ。無ければ今の HEAD）---
base="HEAD"
if git remote get-url origin >/dev/null 2>&1; then
  if git fetch --quiet origin 2>/dev/null; then
    default="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
    if [ -z "$default" ]; then
      for b in main master; do
        if git show-ref --verify --quiet "refs/remotes/origin/$b"; then default="origin/$b"; break; fi
      done
    fi
    [ -n "$default" ] && base="$default"
  else
    echo "注意: origin から fetch できなかったので、今の HEAD を起点にします。" >&2
  fi
fi

# --- worktree 置き場を git の追跡対象から外す（コミットされない .git/info/exclude に書く）---
exclude="${common_dir}/info/exclude"
mkdir -p "$(dirname "$exclude")"
if ! grep -qxF '.claude/worktrees/' "$exclude" 2>/dev/null; then
  printf '\n.claude/worktrees/\n' >> "$exclude"
fi

git worktree add --quiet --no-track -b "$branch" "$dir" "$base"

# --- git が追跡していない .env 系をルートからコピー（無いと dev サーバーが起動しない）---
copied=()
for f in "$root"/.env "$root"/.env.*; do
  [ -f "$f" ] || continue
  name="$(basename "$f")"
  if git -C "$root" check-ignore -q "$name" && [ ! -e "$dir/$name" ]; then
    cp -p "$f" "$dir/$name"
    copied+=("$name")
  fi
done

echo "作成しました: ブランチ ${branch}（起点 ${base}）"
if [ ${#copied[@]} -gt 0 ]; then
  echo "コピーした未追跡ファイル: ${copied[*]}"
fi
echo "WORKTREE=${dir}"
