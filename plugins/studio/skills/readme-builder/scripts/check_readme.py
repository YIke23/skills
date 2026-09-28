#!/usr/bin/env python3
"""README を納品前に機械で検査する。

README は「このリポジトリについての主張の集合」で、主張の多くは機械で確かめられる。
書いたスクリプト名が package.json に無い、cp の元ファイルが無い、clone の URL が
実際の remote と違う——どれも読者が最初の10分で踏み、書き手は気づかない。

不適合（exit 2）:
  - 秘密情報らしき文字列（API キー・秘密鍵・トークン）
  - 書き手の手元の絶対パス（/Users/... など）
  - 雛形の埋め残し（{{...}} / YYYY-MM-DD / TODO / TBD）
  - 壊れた相対リンク・画像、README 内の見出しアンカー
  - npm / pnpm / yarn / bun の存在しないスクリプト名、make の存在しないターゲット
  - cp / mv の元ファイルが無い（.env.example など）
  - docker compose の存在しないサービス名
  - git clone の URL が実際の origin と違う

警告（exit 1）:
  - 冒頭の概要が無い / セットアップのコードブロックが無い / 最終確認日が無い・古い
  - 問い合わせ先が無い / デプロイ設定があるのにデプロイの記述が無い
  - コードが読む環境変数が README にも雛形への案内にも無い
  - コードから導ける長い一覧（20行超のディレクトリツリー）
  - 地の文が上限（既定 4,000 字）を超えている
  - インラインコードに書いたパスが存在しない

使い方:
    python3 check_readme.py <README.md> [--repo <リポジトリ>] [--limit N]

--repo を省くと README のあるディレクトリをリポジトリとみなす。
"""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_repo import compose_services, makefile_targets, scan  # noqa: E402

SECRET_PATTERNS = [
    (re.compile(r"sk_live_[0-9A-Za-z]{10,}"), "Stripe の本番キー"),
    (re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"), "OpenAI / Anthropic 形式の API キー"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS アクセスキー"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "GitHub トークン"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "Slack トークン"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "Google API キー"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "秘密鍵"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"), "JWT"),
    (re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+_\-]{12,}"),
     "値の入った秘密情報"),
]
LOCAL_PATH = re.compile(r"(/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Z]:\\\\Users\\\\)")
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}|YYYY-MM-DD|\bTODO\b|\bTBD\b|\bFIXME\b")

FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")
HTML_SRC = re.compile(r"""<(?:img|a)\b[^>]*\b(?:src|href)=["']([^"']+)["']""", re.I)
INLINE_CODE = re.compile(r"`([^`\n]+)`")

NPM_BUILTIN = {"install", "i", "ci", "add", "remove", "uninstall", "update", "init", "exec",
               "dlx", "create", "link", "outdated", "audit", "publish", "login", "whoami",
               "config", "cache", "list", "ls", "why", "x", "upgrade", "global", "set", "-v",
               "--version", "version", "help", "rebuild", "prune", "dedupe", "pack", "import",
               "store", "env", "setup", "patch", "fetch"}

CONTACT_WORDS = re.compile(r"担当|問い合わせ|問合せ|連絡先|窓口|オーナー|管理者|持ち主|owner|maintainer|contact", re.I)
DEPLOY_WORDS = re.compile(r"デプロイ|リリース|本番|deploy|release|production", re.I)
VERIFIED = re.compile(r"(最終確認日|最終更新日|最終確認|last (?:reviewed|verified|updated))\s*[:：]\s*(\d{4}-\d{2}-\d{2})", re.I)
ENV_POINTER = re.compile(r"\.env[\w.]*\.(example|sample|template|dist)|\.envrc\.example|環境変数|environment variables", re.I)
TREE_LINE = re.compile(r"[├└│]|^\s*[\w.-]+/\s*(#.*)?$")


def github_slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"`|\*\*|\*|__|~~", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def split_blocks(lines: list[str]):
    """(行番号, 行, コードブロック内か, そのブロックの開始行) を返す。"""
    in_code = False
    start = 0
    for i, line in enumerate(lines, 1):
        if FENCE.match(line):
            if not in_code:
                start = i
            in_code = not in_code
            yield i, line, True, start
            continue
        yield i, line, in_code, start


def expand_braces(s: str) -> list[str]:
    m = re.search(r"\{([^{}]*,[^{}]*)\}", s)
    if not m:
        return [s]
    out = []
    for part in m.group(1).split(","):
        out += expand_braces(s[:m.start()] + part + s[m.end():])
    return out


def norm_remote(url: str) -> str:
    url = url.strip().removesuffix(".git")
    url = re.sub(r"^git@([^:]+):", r"\1/", url)
    url = re.sub(r"^(https?|ssh)://([^@/]+@)?", "", url)
    return url.lower()


def prose_chars(line: str) -> int:
    s = re.sub(r"<!--.*?-->", "", line)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"^\s*(#{1,6}|[-*+]|\d+[.)]|>)\s*", "", s)
    s = re.sub(r"[`*_~]", "", s)
    return len(re.sub(r"\s", "", s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("readme")
    ap.add_argument("--repo")
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--stale-days", type=int, default=180)
    a = ap.parse_args()

    readme = Path(a.readme).expanduser().resolve()
    if not readme.is_file():
        print(f"ERROR: README が無い: {readme}", file=sys.stderr)
        return 1
    repo = Path(a.repo).expanduser().resolve() if a.repo else readme.parent
    base = readme.parent
    raw = readme.read_text(encoding="utf-8")
    # HTML コメントは読者に見えないので検査しない。行番号がずれないよう改行だけ残す
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), raw, flags=re.S)
    lines = text.splitlines()
    facts = scan(repo)

    errs: list[str] = []
    warns: list[str] = []

    pj = facts["run"].get("package.json")
    scripts = set(pj["scripts"]) if pj else None
    targets = set(facts["run"].get("make_targets", [])) if "make_targets" in facts["run"] else None
    services = set()
    for svcs in facts["run"].get("compose_services", {}).values():
        services |= set(svcs)
    remote = facts["git"]["remote"]
    try:
        tracked = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True,
                                 text=True, timeout=20).stdout.splitlines()
    except (OSError, subprocess.TimeoutExpired):
        tracked = []

    # 見出しとアンカー
    slugs: dict[str, int] = {}
    anchors = set()
    for _, line, in_code, _ in split_blocks(lines):
        if in_code:
            continue
        m = HEADING.match(line)
        if m:
            s = github_slug(m.group(2))
            n = slugs.get(s, 0)
            anchors.add(s if n == 0 else f"{s}-{n}")
            slugs[s] = n + 1
    for m in re.finditer(r"""<a\s+(?:name|id)=["']([^"']+)["']""", text):
        anchors.add(m.group(1))

    code_blocks: list[tuple[int, list[str]]] = []
    cur: list[str] = []
    prose = 0
    first_h2 = None
    summary_seen = False
    in_code = False
    start = 0
    for i, line in enumerate(lines, 1):
        # 行単位の検査（コードの中も外も）
        for pat, label in SECRET_PATTERNS:
            if pat.search(line):
                errs.append(f"{i}行目: {label}らしき文字列がある。値ではなく置き場所を書く")
                break
        if LOCAL_PATH.search(line):
            errs.append(f"{i}行目: 書き手の手元の絶対パスがある（{LOCAL_PATH.search(line).group(1)}）。リポジトリからの相対パスで書く")
        if FENCE.match(line):
            if in_code:
                code_blocks.append((start, cur))
                cur = []
            else:
                start = i
            in_code = not in_code
            continue
        # 埋め残しは地の文だけ見る。コードの中の {{var}} はテンプレート構文として正当
        if not in_code:
            bare = INLINE_CODE.sub("", line)
            if PLACEHOLDER.search(bare):
                errs.append(f"{i}行目: 埋め残し「{PLACEHOLDER.search(bare).group(0)}」")
        if in_code:
            cur.append(line)
            continue

        if first_h2 is None and line.startswith("## "):
            first_h2 = i
        if first_h2 is None and line.strip() and not line.startswith("#") and not re.match(r"^\s*(\[!\[|!\[|<)", line) \
                and not VERIFIED.search(line) and not re.match(r"^\s*\S+\s*[:：]", line):
            summary_seen = True
        if not line.lstrip().startswith("|"):
            prose += prose_chars(line)

        # リンクと画像
        for target in LINK.findall(line) + HTML_SRC.findall(line):
            if re.match(r"^(https?:|mailto:|tel:|data:)", target):
                continue
            if target.startswith("#"):
                if target[1:] and target[1:].lower() not in anchors:
                    errs.append(f"{i}行目: アンカー {target} に当たる見出しが無い")
                continue
            path = target.split("#", 1)[0].split("?", 1)[0]
            if path and not (base / path).exists():
                errs.append(f"{i}行目: リンク先 {path} が無い")

        # インラインコードのパス
        for code in INLINE_CODE.findall(line):
            c = code.strip()
            if " " in c or "*" in c or "<" in c or "{" in c or c.startswith(("http", "-", "$", "@")):
                continue
            # 拡張子付きのパスだけ見る。`next/image` や `react/xxx` のような
            # パッケージ名・ルール名を拾わないため
            if "/" in c and re.match(r"^\.?[\w.\-/]+\.\w{1,5}$", c) and not c.startswith("/"):
                p = c.removeprefix("./")
                if not (repo / p).exists() and not (base / p).exists() \
                        and not any(f == p or f.endswith("/" + p) for f in tracked):
                    warns.append(f"{i}行目: `{c}` が見当たらない（生成物なら無視してよい）")

    # コードブロックの中のコマンド
    all_code = [(s, l) for s, block in code_blocks for l in block]
    inline_cmds = [(0, c) for c in INLINE_CODE.findall(text)
                   if re.match(r"^(npm|pnpm|yarn|bun|make|cp|mv|docker|docker-compose|git)\s", c.strip())]
    for start, raw in all_code + inline_cmds:
        where = f"{start}行目からのコードブロック" if start else "インラインコード"
        bucket = errs if start else warns
        line = re.sub(r"^\s*[$>%#]\s+", "", raw)
        for seg in re.split(r"&&|\|\||;|\|", line):
            w = seg.split()
            if not w:
                continue
            if w[0] == "sudo":
                w = w[1:]
            if not w:
                continue
            if scripts is not None and w[0] in {"npm", "pnpm", "yarn", "bun"} and len(w) >= 2:
                name = None
                if w[1] in {"run", "run-script"} and len(w) >= 3:
                    name = w[2]
                elif w[0] == "npm" and w[1] in {"test", "start", "t"}:
                    name = {"t": "test"}.get(w[1], w[1])
                    if name == "start" and name not in scripts:
                        name = None  # npm start は server.js でも動く
                elif w[0] != "npm" and w[1] not in NPM_BUILTIN and not w[1].startswith("-"):
                    name = w[1]
                if name and not name.startswith("-") and name not in scripts:
                    bucket.append(f"{where}: `{w[0]} {' '.join(w[1:3])}` — package.json に script `{name}` が無い")
            if targets is not None and w[0] == "make" and len(w) >= 2:
                for t in w[1:]:
                    if t.startswith("-") or "=" in t:
                        continue
                    if t not in targets:
                        bucket.append(f"{where}: `make {t}` — Makefile にターゲットが無い")
                    break
            if w[0] in {"cp", "mv"} and len(w) >= 2:
                args = [x for x in w[1:] if not x.startswith("-")]
                srcs = expand_braces(args[0]) if len(args) == 1 else args[:-1]
                if len(args) == 1 and len(srcs) == 2:
                    srcs = srcs[:1]
                for src in srcs:
                    if re.search(r"[$~*]", src) or src.startswith("/"):
                        continue
                    if not (repo / src).exists():
                        bucket.append(f"{where}: `{seg.strip()}` — 元ファイル {src} がリポジトリに無い")
            if services and w[0] in {"docker", "docker-compose"}:
                ws = w[1:] if w[0] == "docker-compose" else (w[2:] if len(w) > 1 and w[1] == "compose" else [])
                if ws and ws[0] in {"exec", "run", "logs", "restart", "stop", "start"}:
                    rest = [x for x in ws[1:] if not x.startswith("-")]
                    if rest and rest[0] not in services:
                        bucket.append(f"{where}: `{seg.strip()}` — compose にサービス {rest[0]} が無い（{', '.join(sorted(services))}）")
            if w[0] == "git" and len(w) >= 3 and w[1] == "clone" and remote:
                url = next((x for x in w[2:] if not x.startswith("-")), "")
                if url and norm_remote(url) != norm_remote(remote):
                    bucket.append(f"{where}: clone の URL {url} が実際の origin（{remote}）と違う")

    # 構成の警告
    if not summary_seen:
        warns.append("冒頭（最初の ## より前）に概要の文が無い。何のリポジトリかを1〜3文で書く")
    if not code_blocks:
        warns.append("コードブロックが1つも無い。セットアップと起動のコマンドをコピーできる形で書く")
    m = VERIFIED.search(text)
    if not m:
        warns.append("「最終確認日: YYYY-MM-DD」が無い。手順を実際に通した日を書くと、読者が鮮度を判断できる")
    else:
        try:
            age = (dt.date.today() - dt.date.fromisoformat(m.group(2))).days
            if age > a.stale_days:
                warns.append(f"最終確認日が {age} 日前。手順を通し直して日付を更新する")
        except ValueError:
            errs.append(f"最終確認日の日付が読めない（{m.group(2)}）")
    if not CONTACT_WORDS.search(text):
        warns.append("問い合わせ先（担当・窓口）が無い。引き継いだ人が最初に困るのはここ")
    deploy_hint = [s for s in facts["services"] if s.startswith(("Vercel", "Netlify", "Fly", "Render", "Railway",
                   "Google App", "Firebase", "Cloudflare", "Serverless", "AWS", "Heroku", "デプロイ", "Kubernetes"))]
    if (deploy_hint or facts["ci"]) and not DEPLOY_WORDS.search(text):
        warns.append(f"デプロイ関連の設定があるのに（{', '.join(deploy_hint + facts['ci'])[:120]}）、デプロイ・本番の記述が無い")
    used = [k for k in facts["env"]["used_in_code"] if not k.startswith(("E2E_", "RUN_"))]
    if used and not ENV_POINTER.search(text):
        missing = [k for k in used if k not in text]
        if missing:
            head = ", ".join(missing[:15]) + (f" ほか {len(missing) - 15} 個" if len(missing) > 15 else "")
            warns.append(f"コードが読む環境変数が README に無く、雛形や一覧への案内も無い: {head}")
    for start, block in code_blocks:
        tree = sum(1 for l in block if TREE_LINE.search(l))
        if tree > 20:
            warns.append(f"{start}行目: {tree} 行のディレクトリツリー。コードを見れば分かる一覧は古びる。入口になる数か所だけに絞る")
    if prose > a.limit:
        warns.append(f"地の文が {prose:,} 字（上限 {a.limit:,}）。詳細は docs/ に移して README からリンクする")

    print(f"検査: {readme}  リポジトリ={repo}")
    print(f"地の文 {prose:,} 字 / コードブロック {len(code_blocks)} 個 / 見出しアンカー {len(anchors)} 個")
    print("-" * 68)
    for e in dict.fromkeys(errs):
        print(f"[不適合] {e}")
    for w in dict.fromkeys(warns):
        print(f"[警告]   {w}")
    if not errs and not warns:
        print("問題なし")
    print("-" * 68)
    print(f"不適合 {len(set(errs))} / 警告 {len(set(warns))}")
    return 2 if errs else 1 if warns else 0


if __name__ == "__main__":
    raise SystemExit(main())
