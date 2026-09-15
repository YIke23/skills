#!/usr/bin/env python3
"""Markdown の「地の文」の字数を見出し単位で数える。

数えるのは読者が順に読み下す文字だけ。コードブロック・表・メタ行・リンクのURLは
除外する。これらを含めて数えると、読者が実際に必要としているコマンドや設定値を
削る圧力がかかり、字数を守った結果として使えない文書ができあがるため。

使い方:
    python3 count.py <file> [--limit N] [--json]

上限を超えると exit 2。入力エラーは exit 1。
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_LIMIT = 5000

# ヘッダのメタ行。読者が読み下す文ではなく、文書の属性なので数えない。
META_LINE = re.compile(r"^\s*(作成日|最終更新日|更新日|作成者|著者|版|バージョン)\s*[:：]")

FENCE = re.compile(r"^\s*(```|~~~)")
TABLE_ROW = re.compile(r"^\s*\|")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
BARE_URL = re.compile(r"<https?://[^>]*>|https?://\S+")
INLINE_CODE_TICKS = re.compile(r"`+")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
LIST_MARKER = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
HEADING_MARK = re.compile(r"^\s*#{1,6}\s+")
BLOCKQUOTE = re.compile(r"^\s*>\s?")


def prose_chars(line: str) -> int:
    """1行から、読者が読み下す文字の数を返す。空白は数えない。"""
    s = HTML_COMMENT.sub("", line)
    s = IMAGE.sub("", s)            # 画像は本文ではない
    s = LINK.sub(r"\1", s)          # リンクは表示テキストだけ数える
    s = BARE_URL.sub("", s)         # 裸のURLは数えない
    s = HEADING_MARK.sub("", s)
    s = LIST_MARKER.sub("", s)
    s = BLOCKQUOTE.sub("", s)
    s = INLINE_CODE_TICKS.sub("", s)  # バッククォート記号だけ落とし、中身は数える
    s = re.sub(r"[*_~]{1,3}", "", s)  # 強調記号
    return len(re.sub(r"\s", "", s))


def analyze(text: str):
    lines = text.splitlines()

    # 先頭の YAML frontmatter を落とす
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break

    sections = []            # [{"heading": str, "line": int, "chars": int}]
    current = {"heading": "（前文）", "line": 1, "chars": 0}
    sections.append(current)

    in_fence = False
    excluded = {"code": 0, "table": 0, "meta": 0}

    for lineno, raw in enumerate(lines, start=1):
        if FENCE.match(raw):
            in_fence = not in_fence
            excluded["code"] += 1
            continue
        if in_fence:
            excluded["code"] += 1
            continue
        if TABLE_ROW.match(raw):
            excluded["table"] += 1
            continue
        if META_LINE.match(raw):
            excluded["meta"] += 1
            continue

        m = HEADING.match(raw)
        if m and len(m.group(1)) <= 2:
            # h1/h2 で節を切る。h3 以下は親の節に含める
            current = {"heading": raw.strip(), "line": lineno, "chars": 0}
            sections.append(current)

        current["chars"] += prose_chars(raw)

    sections = [s for s in sections if s["chars"] > 0]
    total = sum(s["chars"] for s in sections)
    return sections, total, excluded


def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown の地の文の字数を数える")
    ap.add_argument("file")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"上限字数（既定 {DEFAULT_LIMIT}）。0 で上限チェックを外す")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"error: ファイルがありません: {path}", file=sys.stderr)
        return 1
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: 読めません: {e}", file=sys.stderr)
        return 1

    sections, total, excluded = analyze(text)
    over = args.limit > 0 and total > args.limit

    if args.json:
        print(json.dumps({
            "file": str(path), "total": total, "limit": args.limit,
            "over": over, "sections": sections, "excluded_lines": excluded,
        }, ensure_ascii=False, indent=2))
        return 2 if over else 0

    print(f"{path}")
    print()
    width = max((len(s["heading"]) for s in sections), default=10)
    width = min(max(width, 12), 46)
    for s in sections:
        head = s["heading"]
        if len(head) > width:
            head = head[:width - 1] + "…"
        share = (s["chars"] / total * 100) if total else 0
        flag = ("  ← 全体の半分超。付録に属していないか確認"
                if share > 50 and len(sections) >= 3 else "")
        print(f"  L{s['line']:>4}  {head:<{width}}  {s['chars']:>6,}字  {share:>5.1f}%{flag}")
    print()
    if args.limit > 0:
        print(f"  合計 {total:,} / {args.limit:,}字  （残り {args.limit - total:,}字）")
    else:
        print(f"  合計 {total:,}字")
    print(f"  除外した行: コード {excluded['code']} / 表 {excluded['table']} / メタ {excluded['meta']}")

    if over:
        print()
        print(f"  超過 {total - args.limit:,}字。削る前に分割を検討すること"
              f"（SKILL.md §3「超過したら、削る前に上から試す」）", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
