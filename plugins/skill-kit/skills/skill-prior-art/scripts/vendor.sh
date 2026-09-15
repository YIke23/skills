#!/usr/bin/env bash
#
# vendor.sh
# 外部スキルを、コミットSHAを固定して手元に取り込む。
#
# 使い方:
#   vendor.sh <owner/repo|URL> <スキルのパス> --dest <取り込み先> [--ref <ref>] [--force]
#     owner/repo : 例 supabase/agent-skills。git の URL をそのまま渡してもよい
#     スキルのパス: リポジトリ内のディレクトリ。例 skills/supabase
#     --dest     : 取り込み先。**リポジトリの中を指す**こと（下の「宛先の制限」）
#     --ref      : ブランチ・タグ・SHA（既定 HEAD）。SHAに解決してから取り込む
#     --force    : 取り込み先が既にこのスクリプトの成果物なら置き換える
#
# 例:
#   vendor.sh supabase/agent-skills skills/supabase --dest vendor/supabase
#
# 取り込み先に VENDOR.md を置き、取り込み元・SHA・日時・実行したコマンドを残す。
# 更新は同じコマンドを新しい --ref で走らせ、VENDOR.md の SHA を見比べる。
#
# 宛先の制限:
#   ~/.claude/skills 配下は宛先にできない。SKILL.md は「外部スキルを勝手に
#   インストールしない。レポートに載せて、ユーザーが選ぶ」と書いており、
#   このスクリプトは**選ばれた後に走る道具**。作業場へ直に生やす経路を残すと
#   その原則が迂回できてしまうので、スクリプト側で塞ぐ。
#   作業場に置きたいときは、リポジトリへ取り込んでレビューしてから make install。
#
# 終了コード:
#   0 = 取り込んだ
#   1 = 取り込まなかった（宛先が既存など、人の判断が要る）
#   2 = エラー（使い方の誤り、取得できない、宛先が許されない）
#
# bash 3.2（macOS 同梱）で動く範囲で書く。git だけあれば動く（gh は要らない）。

set -uo pipefail

die() {
  echo "エラー: $1" >&2
  shift
  for extra in "$@"; do echo "$extra" >&2; done
  exit 2
}

usage() {
  echo ' 使い方: vendor.sh <owner/repo|URL> <スキルのパス> --dest <取り込み先> [--ref <ref>] [--force]' >&2
  echo ' 例:     vendor.sh supabase/agent-skills skills/supabase --dest vendor/supabase' >&2
}

# --- 引数 ---
source_repo=""
sub_path=""
dest=""
ref="HEAD"
force=0
positional=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dest)
      [ "$#" -ge 2 ] || die "--dest に値がありません。"
      dest="$2"; shift 2 ;;
    --ref)
      [ "$#" -ge 2 ] || die "--ref に値がありません。"
      ref="$2"; shift 2 ;;
    --force)
      force=1; shift ;;
    -h|--help)
      usage; exit 2 ;;
    -*)
      usage
      die "知らないオプション: $1" ;;
    *)
      positional=$((positional + 1))
      case "$positional" in
        1) source_repo="$1" ;;
        2) sub_path="$1" ;;
        *) usage; die "引数が多すぎます: $1" ;;
      esac
      shift ;;
  esac
done

if [ -z "$source_repo" ] || [ -z "$sub_path" ] || [ -z "$dest" ]; then
  usage
  die "取り込み元・スキルのパス・--dest の3つが要ります。"
fi

case "$sub_path" in
  /*|*..*) die "スキルのパス '$sub_path' が不正。リポジトリからの相対パスを渡す。" ;;
esac

command -v git >/dev/null 2>&1 || die "git が見つかりません。"

# --- 取り込み元のURLを組み立てる ---
case "$source_repo" in
  *://*|git@*)
    url="$source_repo" ;;
  */*)
    url="https://github.com/${source_repo}.git" ;;
  *)
    die "取り込み元 '$source_repo' が読めません。owner/repo か git の URL を渡す。" ;;
esac

# --- 宛先を確かめる ---
parent="$(dirname "$dest")"
[ -d "$parent" ] || die "取り込み先の親ディレクトリがありません: $parent"
abs_parent="$(cd "$parent" && pwd -P)"
abs_dest="${abs_parent}/$(basename "$dest")"

workspace="${HOME}/.claude/skills"
if [ -d "$workspace" ]; then
  workspace="$(cd "$workspace" && pwd -P)"
fi
case "$abs_dest" in
  "$workspace"|"$workspace"/*)
    die "取り込み先が ~/.claude/skills 配下です: $abs_dest" \
        " 外部スキルを作業場へ直に生やさない。SKILL.md は「勝手にインストールしない。" \
        " レポートに載せて、ユーザーが選ぶ」と書いている。" \
        " リポジトリへ取り込んでレビューしたあと、make install で作業場へ写す。" ;;
esac

# --- 既存の取り込み先は黙って上書きしない ---
if [ -e "$abs_dest" ]; then
  if [ "$force" -ne 1 ]; then
    echo "取り込み先が既にあります: $abs_dest" >&2
    if [ -f "$abs_dest/VENDOR.md" ]; then
      echo " 前回の取り込み:" >&2
      grep -E '^- (取り込み元|コミットSHA|取り込み日時):' "$abs_dest/VENDOR.md" 2>/dev/null \
        | sed 's/^/   /' >&2
      echo " 置き換えるなら --force を付ける。" >&2
    else
      echo " このスクリプトが作ったものではありません（VENDOR.md が無い）。" >&2
      echo " 中身を確かめて、自分で退けてから実行する。" >&2
    fi
    exit 1
  fi
  # --force でも、自分が作ったもの以外は消さない。
  if [ ! -f "$abs_dest/VENDOR.md" ]; then
    die "--force が指定されましたが $abs_dest に VENDOR.md がありません。" \
        " このスクリプトの成果物でないディレクトリは置き換えません。" \
        " 中身を確かめて、自分で退けてから実行する。"
  fi
fi

# --- ref を SHA に解決する ---
# ブランチ名のまま取り込むと固定にならない。必ず SHA まで落とす。
sha=""
if printf '%s' "$ref" | grep -qE '^[0-9a-f]{40}$'; then
  sha="$ref"
else
  sha="$(git ls-remote "$url" "$ref" 2>/dev/null | head -1 | awk '{print $1}')"
  if [ -z "$sha" ] && [ "$ref" = "HEAD" ]; then
    sha="$(git ls-remote "$url" HEAD 2>/dev/null | head -1 | awk '{print $1}')"
  fi
fi
[ -n "$sha" ] || die "ref '$ref' を SHA に解決できません: $url" \
                     " リポジトリ名と ref を確かめる。非公開なら認証が要る。"

# --- 取ってくる ---
tmp="$(mktemp -d -t vendor_sh)"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

echo "取り込み元: $url"
echo "ref:        $ref  →  $sha"
echo "サブパス:   $sub_path"
echo "取り込み先: $abs_dest"
echo "----------------------------------------------------------------"

# blob は必要になったぶんだけ取る。履歴は残さない（取り込むのは中身だけ）。
if ! git clone --quiet --filter=blob:none --no-checkout "$url" "$tmp/repo" 2>"$tmp/err"; then
  sed 's/^/  /' "$tmp/err" >&2
  die "clone に失敗しました: $url"
fi
if ! git -C "$tmp/repo" checkout --quiet "$sha" 2>"$tmp/err"; then
  sed 's/^/  /' "$tmp/err" >&2
  die "SHA $sha を checkout できません。ref がこのリポジトリのものか確かめる。"
fi

got="$(git -C "$tmp/repo" rev-parse HEAD)"
[ "$got" = "$sha" ] || die "checkout した SHA が違います（要求 ${sha} / 実際 ${got}）。"

src="$tmp/repo/$sub_path"
[ -d "$src" ] || die "サブパスがありません: ${sub_path}（${sha} 時点）" \
                     " git -C <clone> ls-tree --name-only $sha で確かめる。"

# --- 置く ---
staged="$tmp/staged"
mkdir -p "$staged"
cp -R "$src" "$staged/payload" || die "コピーに失敗しました。"
rm -rf "$staged/payload/.git"

when="$(date +%Y-%m-%dT%H:%M:%S%z)"
cat > "$staged/payload/VENDOR.md" <<EOF
# 取り込み記録

このディレクトリは外部スキルの複製。**手で編集する前にこの記録を読む。**

- 取り込み元: $url
- サブパス: $sub_path
- コミットSHA: \`$sha\`
- 指定した ref: $ref
- 取り込み日時: $when
- 実行したコマンド: \`vendor.sh $source_repo $sub_path --dest $dest --ref $ref\`

## 差分を当てるとき

上のSHA時点の複製に対して、自分の変更が何かが後から分かるようにする。
**取り込みのコミットと、差分を当てるコミットを分ける。**

## 更新するとき

同じコマンドを新しい \`--ref\` で走らせ、このファイルのSHAを見比べる。
取り込み先が既にあると止まるので、置き換えるなら \`--force\` を付ける。

## ライセンス

取り込み元のライセンスがこの複製にも及ぶ。取り込み元の LICENSE を確認すること。
EOF

if [ -e "$abs_dest" ]; then
  rm -rf "$abs_dest"
fi
mv "$staged/payload" "$abs_dest" || die "取り込み先へ移動できませんでした: $abs_dest"

files=$(find "$abs_dest" -type f | wc -l | tr -d ' ')
echo "取り込みました: ${files} ファイル"
echo "記録: ${abs_dest}/VENDOR.md"
echo
echo "次にやること。"
echo "  1. 同梱スクリプトを読む。ネットワークに出るか、資格情報に触るか、消す操作があるか"
echo "  2. 取り込み元の LICENSE を確認する"
echo "  3. 取り込みだけで1コミットにする。差分を当てるのは次のコミット"
exit 0
