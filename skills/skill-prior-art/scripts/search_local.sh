#!/usr/bin/env bash
#
# search_local.sh
# 手元にあるスキルを横断して、検索語に一致する重複候補を洗い出す（T0）。
#
# 使い方:
#   search_local.sh <検索語> [検索語...]
#     検索語 : 英語でも日本語でもよい。複数渡すと、いずれかに一致したものを出す（OR）
#
# 探す場所（無い場所は黙って飛ばす）:
#   1. カレントリポジトリの skills/
#   2. ~/.claude/skills                        作業場
#   3. ~/.claude/plugins/cache/*/*/*/skills    marketplace/plugin/sha
#   4. Claude Desktop のプラグイン配下
#
# 照合するのは SKILL.md のフロントマター（name と description）だけ。本文は見ない。
# description は「どんなときに呼ばれたいか」を書く場所なので、仕事が重なっている
# スキルはここで当たる。本文まで見ると実装の都合で語が一致しただけの誤検出が増える。
#
# 終了コード: 0=候補なし / 1=候補あり（人が読む必要がある）
#   2 は使い方の誤りで、判定ではない。この道具は「落とす」検証ではないため、
#   候補が出たこと自体を不適合として扱わない。
#
# bash 3.2（macOS 同梱）で動く範囲で書く。連想配列と mapfile は使わない。

set -uo pipefail

# --- 引数チェック ---
if [ "$#" -eq 0 ]; then
  echo "エラー: 検索語が指定されていません。" >&2
  echo '使い方: search_local.sh <検索語> [検索語...]' >&2
  echo '例:     search_local.sh "pull request" "pr template" PR作成' >&2
  exit 2
fi

for term in "$@"; do
  if [ -z "$term" ]; then
    echo "エラー: 空の検索語は渡せません。" >&2
    exit 2
  fi
done

# --- 探す場所を集める ---
roots=""

add_root() {
  [ -d "$1" ] || return 0
  roots="${roots}${1}
"
}

if repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  add_root "${repo_root}/skills"
fi

add_root "${HOME}/.claude/skills"

# プラグインキャッシュは marketplace/plugin/sha/skills の4階層。
# 同じプラグインの古い sha が並ぶので、後で重複としてまとめる。
cache="${HOME}/.claude/plugins/cache"
if [ -d "$cache" ]; then
  while IFS= read -r d; do
    add_root "$d"
  done < <(find "$cache" -maxdepth 4 -type d -name skills 2>/dev/null | sort)
fi

# Claude Desktop は2つの置き方が混在する（skills-plugin/ 配下と rpm/plugin_*/ 配下）。
desktop="${HOME}/Library/Application Support/Claude/local-agent-mode-sessions"
if [ -d "$desktop" ]; then
  while IFS= read -r d; do
    add_root "$d"
  done < <(find "$desktop" -maxdepth 6 -type d -name skills 2>/dev/null | sort)
fi

if [ -z "$roots" ]; then
  echo "探せる場所が1つも見つかりませんでした。" >&2
  echo "カレントが git リポジトリでなく、~/.claude も無い状態です。" >&2
  exit 2
fi

# --- ホーム配下のパスを ~ に縮める ---
# ${path/#$HOME/~} は bash 5.x で置換側の ~ がチルダ展開され、3.2 と挙動が割れる。
# 版差を持ち込まないよう sed で書く。
shorten() {
  printf '%s' "$1" | sed "s|^${HOME}|~|"
}

# --- YAML のクォートを剥がす ---
# name: "be-pr-create" のように引用されている SKILL.md がある。
# awk の substr は環境によってバイト単位で動くので、切るのは bash 側でやる。
strip_quotes() {
  local v="$1"
  case "$v" in
    '"'*'"') v="${v#\"}"; v="${v%\"}" ;;
    "'"*"'") v="${v#\'}"; v="${v%\'}" ;;
  esac
  printf '%s' "$v"
}

# --- フロントマターから1項目を取り出す ---
# description は複数行に折り返されていることがあるので、次のキーか --- まで連結する。
extract_field() {
  awk -v field="$2" '
    NR == 1 && $0 != "---" { exit }
    NR == 1 { infm = 1; next }
    infm && $0 == "---" { exit }
    infm && index($0, field ":") == 1 {
      val = substr($0, length(field) + 2)
      sub(/^[ \t]+/, "", val)
      grab = 1
      next
    }
    infm && grab && /^[A-Za-z_-]+:/ { exit }
    infm && grab {
      line = $0
      sub(/^[ \t]+/, "", line)
      val = val " " line
      next
    }
    END { if (val != "") print val }
  ' "$1"
}

# --- 走査 ---
seen="$(mktemp -t search_local_seen)"
hits="$(mktemp -t search_local_hits)"
trap 'rm -f "$seen" "$hits"' EXIT

n_roots=0
n_skills=0
n_hits=0

while IFS= read -r root; do
  [ -n "$root" ] || continue
  n_roots=$((n_roots + 1))

  while IFS= read -r md; do
    [ -n "$md" ] || continue
    n_skills=$((n_skills + 1))

    name="$(strip_quotes "$(extract_field "$md" name)")"
    [ -n "$name" ] || name="$(basename "$(dirname "$md")")"
    desc="$(strip_quotes "$(extract_field "$md" description)")"

    # 一致した検索語を集める
    matched=""
    for term in "$@"; do
      if printf '%s\n%s' "$name" "$desc" | grep -qiF -- "$term"; then
        matched="${matched}${term}
"
      fi
    done
    [ -n "$matched" ] || continue

    # 同じ中身が別の sha 配下に並んでいるだけなら、1件にまとめる
    key="${name}:$(printf '%s' "$desc" | cksum | awk '{print $1}')"
    if grep -qxF -- "$key" "$seen" 2>/dev/null; then
      printf '%s\tDUP\n' "$key" >> "$hits"
      continue
    fi
    printf '%s\n' "$key" >> "$seen"
    n_hits=$((n_hits + 1))

    # TSV で持ち回るので、description 内のタブは潰しておく
    flat_desc="$(printf '%s' "$desc" | tr '\t' ' ')"
    printf '%s\t%s\t%s\t%s\t%s\n' "$key" "$n_hits" "$name" "$md" "$flat_desc" >> "$hits"
  done < <(find "$root" -mindepth 2 -maxdepth 2 -name SKILL.md 2>/dev/null | sort)
done <<EOF
$roots
EOF

# --- 出力 ---
echo "検索語: $*"
echo "探した場所 ${n_roots} / SKILL.md ${n_skills} 本 / 候補 ${n_hits} 件"
echo "------------------------------------------------------------------"

if [ "$n_hits" -eq 0 ]; then
  echo "候補なし。"
  echo
  echo "T0 に候補が無いことと、他の層に無いことは別。T1〜T5 を続けること。"
  exit 0
fi

TAB="$(printf '\t')"

while IFS="$TAB" read -r key idx name path desc; do
  [ "${idx:-}" = "DUP" ] && continue
  [ -n "${idx:-}" ] || continue

  dups=$(grep -cF -- "${key}${TAB}DUP" "$hits" 2>/dev/null || true)
  dups=${dups:-0}

  echo "[${idx}] ${name}"
  echo "     $(shorten "$path")"
  if [ "$dups" -gt 0 ]; then
    echo "     （同じ中身が他 ${dups} 箇所にもある。古い sha やプラグイン版の重複）"
  fi

  for term in "$@"; do
    if printf '%s' "$name" | grep -qiF -- "$term"; then
      echo "     ヒット \"${term}\": スキル名そのもの"
      continue
    fi
    # 文単位に切って、当たった文だけを出す（該当箇所を見せるため）。
    # 日本語は「。」、英語は「. 」で切る。description は日英どちらもある。
    printf '%s' "$desc" | sed -e 's/。/。\
/g' -e 's/\. /.\
/g' | grep -iF -- "$term" | head -2 | while IFS= read -r sentence; do
      sentence="$(printf '%s' "$sentence" | sed 's/^[ \t]*//')"
      [ -n "$sentence" ] && echo "     ヒット \"${term}\": ${sentence}"
    done
  done
  echo
done < "$hits"

echo "------------------------------------------------------------------"
echo "候補 ${n_hits} 件。名前と description だけで切り捨てず、SKILL.md 本文を読むこと。"
exit 1
