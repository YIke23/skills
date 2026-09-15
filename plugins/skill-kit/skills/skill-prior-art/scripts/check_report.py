#!/usr/bin/env python3
"""skill-prior-art の調査レポートを機械検証する。

    python3 check_report.py docs/prior-art-foo.md
    python3 check_report.py report.md --date 2026-09-08   # 基準日を指定する

雛形は assets/report.md。見出しの文言で照合するので、見出しを変えると落ちる。

見るのは「根拠が書かれているか」だけ。**「判断が正しいか」は見ない。**
adopt すべき場面で build-new を選んだ、のような妥当性は機械では判定できないし、
判定できるふりをすると、通ったこと自体が誤った安心になる。

ネットワークには出ない。URLの生死は確かめない。標準ライブラリだけで動く。

落とすもの（不適合 / exit 2）:

  1. 雛形の必須見出しが無い
  2. T0 / T1 / T2 の層が調査されていない（クエリも結果も空）
  3. 「該当なし」と書いた層に、実行したクエリが書かれていない
     — クエリの無い「該当なし」は未調査と同じ。層を問わず落とす
  4. 出典の無い数値がある（同じ行のURL、またはその節で実行したコマンド）
  5. 結論が adopt / vendor / derive / build-new のどれでもない
  6. 結論が derive / build-new なのに「既存で満たせない点」が1件も無い
  7. 結論が adopt / vendor / derive で、採用元（T0 以外）の監査結果が空

警告（exit 1）:

  - T3 / T4 / T5 が調査されていない（上で見つかったなら軽く流してよい）
  - 候補の「足りないこと」が空（adopt なら空でも筋は通る）
  - 調査日が基準日と違う、または書かれていない
  - 検索語が英語3個未満、または日本語0個
  - 採用元が「## 候補」に見つからず、監査の要否を判定できない
  - 見出しの順序が雛形と違う
  - 「## 調査を省略した理由」が埋まっている（SKILL.md の例外を使った記録）

4 の数値は、外部から取ってきた指標に見えるものだけを対象にする。
桁区切りのある数、★数、`12k` / `1.2M`、`N件` / `N本` / `N個`、
`N stars` / `installs` / `downloads` / `forks`、パーセント。
日付・バージョン番号・層タグ・終了コードは対象外。
コードブロックと HTML コメントの中身、「### 検索語」と
「### 既存で満たせない点」の節も対象外。

出典は SKILL.md L33 に合わせ「画面かコマンド出力」の**どちらでもよい**。
同じ行に http(s):// があるか、その節に実行したコマンドが残っていれば通る。
URLだけを求めると、search_local.sh の出力のようなローカル由来の数が書けなくなる。
候補の節にはコマンドが無いので、★数やインストール数には引き続きURLが要る。

終了コード: 0=問題なし / 1=警告あり / 2=不適合
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

# --- 雛形の形 -----------------------------------------------------------

# 見出しの順序。ここに無い見出しを足すのは自由。
TOP_HEADINGS = [
    "調査日",
    "何を探したか",
    "調査を省略した理由",
    "調査した層",
    "候補",
    "結論",
]
SUB_HEADINGS = ["検索語", "既存で満たせない点"]

LAYERS = ["T0", "T1", "T2", "T3", "T4", "T5"]
MUST_INVESTIGATE = {"T0", "T1", "T2"}      # 抜けたら落とす層

VERDICTS = ["adopt", "vendor", "derive", "build-new"]
NEEDS_GAP = {"derive", "build-new"}         # 「既存で満たせない点」が要る結論
NEEDS_AUDIT = {"adopt", "vendor", "derive"}  # 採用元の監査結果が要る結論

CANDIDATE_FIELDS = ["層", "提供元", "取得元URL", "できること",
                    "足りないこと", "保守状況", "監査結果"]

# --- 判定に使うパターン -------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
LAYER_RE = re.compile(r"^(T[0-5])\b")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
FIELD_RE = re.compile(r"^[-*]\s*([^:：]+)[:：]\s*(.*)$")
URL_RE = re.compile(r"https?://\S")

# 「該当なし」と言い切っている表現。これを書くならクエリが要る。
NONE_RE = re.compile(r"該当なし|候補なし|見つから(?:な|ぬ)|ヒットなし|0\s*件|なかった")

# 外部から取ってきた指標に見える数値。日付・バージョン・層タグは拾わない。
METRIC_RE = re.compile(
    r"\d{1,3}(?:,\d{3})+"                                  # 1,376,738
    r"|[★⭐]\s*\d[\d,]*"                                    # ★2,584
    r"|\d[\d,]*\s*[★⭐]"                                    # 2,584★
    r"|\d+(?:\.\d+)?\s*[kKmM](?![A-Za-z0-9])"              # 12k / 1.2M
    r"|\d[\d,]*\s*(?:stars?|installs?|downloads?|forks?)\b"
    r"|\d[\d,]*\s*(?:件|本|個)"
    r"|\d+(?:\.\d+)?\s*[%％]"
)

# 埋めていない箇所。<...> と、空の箇条書きと、日付のプレースホルダ。
PLACEHOLDER_RE = re.compile(r"^(?:<[^>]*>|YYYY-MM-DD|[-*]?\s*)$")

# 値の無いラベル行（「結果:」「実行したクエリ:」など）。雛形が置いている見出しなので、
# 中身が書かれたことにしない。これを埋め忘れと見なさないと、雛形のまま検査が通る。
BARE_LABEL_RE = re.compile(r"^[-*]?\s*[^:：]{0,24}[:：]\s*$")

# 行頭のラベル。「結果:」のように値が続くものも含む。値を次の行から拾うときに、
# 別のラベルの行まで食べないための境界。
LABEL_LINE_RE = re.compile(r"^[-*]?\s*[^:：]{0,24}[:：]")


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    @property
    def code(self) -> int:
        if self.fails:
            return 2
        return 1 if self.warns else 0


class Section:
    """見出し1つと、その配下の行。"""

    def __init__(self, level: int, title: str, start: int) -> None:
        self.level = level
        self.title = title
        self.start = start
        self.end = start
        self.lines: list[str] = []      # 見出しの次から次の見出しまで（子見出しを含む）
        self.own: list[str] = []        # 子見出しに入らない、自分の直下の行だけ
        self.fenced: list[str] = []     # 自分の直下のコードブロックの中身


def split_fences(lines: list[str]) -> tuple[list[str], list[str]]:
    """コードブロックの外と中に分ける。"""
    outside, inside, in_fence = [], [], False
    for ln in lines:
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        (inside if in_fence else outside).append(ln)
    return outside, inside


def parse_sections(lines: list[str]) -> list[Section]:
    heads: list[Section] = []
    in_fence = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(ln)
        if m:
            heads.append(Section(len(m.group(1)), m.group(2), i))

    for n, sec in enumerate(heads):
        sec.end = len(lines)
        for later in heads[n + 1:]:
            if later.level <= sec.level:
                sec.end = later.start
                break
        sec.lines = lines[sec.start + 1:sec.end]

        # 自分の直下だけ（最初の子見出しまで）
        own_end = sec.end
        for later in heads[n + 1:]:
            if later.start < sec.end:
                own_end = later.start
                break
        own_all = lines[sec.start + 1:own_end]
        sec.own, sec.fenced = split_fences(own_all)
    return heads


def find(secs: list[Section], title: str) -> Section | None:
    for s in secs:
        if s.title == title:
            return s
    return None


def meaningful(lines: list[str]) -> list[str]:
    """空行・プレースホルダ・値の無いラベル行を落とした行。"""
    out = []
    for ln in lines:
        s = ln.strip()
        if not s or PLACEHOLDER_RE.match(s) or BARE_LABEL_RE.match(s):
            continue
        out.append(s)
    return out


def value_after(lines: list[str], label: str) -> str:
    """「ラベル:」の後ろの値。同じ行に無ければ、次の中身のある行を値とみなす。"""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith(label):
            continue
        rest = s[len(label):].lstrip(":： 　").strip()
        if rest:
            return rest
        for nxt in lines[i + 1:]:
            t = nxt.strip()
            if not t:
                continue
            # 別のラベル行まで食べない。「実行したクエリ:」が空のときに
            # 次の「結果: 該当なし」を値として拾うと、クエリ有りに化ける。
            if t.startswith("#") or LABEL_LINE_RE.match(t):
                break
            if PLACEHOLDER_RE.match(t):
                break
            return t
        return ""
    return ""


# --- 検査 ---------------------------------------------------------------

def check_headings(secs: list[Section], r: Report) -> None:
    for title in TOP_HEADINGS + SUB_HEADINGS:
        if find(secs, title) is None:
            r.fail(f"見出し「{title}」が無い。assets/report.md の形に合わせる")

    layer_titles = [s.title for s in secs if LAYER_RE.match(s.title)]
    for tag in LAYERS:
        if not any(t.startswith(tag) for t in layer_titles):
            r.fail(f"層「{tag}」の節が無い。調べていないなら、その旨とクエリを書く")

    seen = [s.title for s in secs if s.level == 2 and s.title in TOP_HEADINGS]
    expect = [t for t in TOP_HEADINGS if t in seen]
    if seen != expect:
        r.warn(f"見出しの順序が雛形と違う: {' → '.join(seen)}")


def check_date(secs: list[Section], today: str, r: Report) -> None:
    sec = find(secs, "調査日")
    if sec is None:
        return
    body = " ".join(meaningful(sec.own))
    m = DATE_RE.search(body)
    if not m:
        r.warn("調査日が書かれていない。今日取得した情報で書いたことの証跡になる")
        return
    if m.group(0) != today:
        r.warn(f"調査日 {m.group(0)} が基準日 {today} と違う。"
               "使い回すなら、数値と存在を取り直す")


def check_terms(secs: list[Section], r: Report) -> None:
    sec = find(secs, "検索語")
    if sec is None:
        return

    def count(label: str) -> int:
        raw = value_after(sec.own, f"- {label}") or value_after(sec.own, label)
        parts = [p.strip() for p in re.split(r"[,、，]", raw) if p.strip()]
        return len(parts)

    n_en, n_ja = count("英語"), count("日本語")
    if n_en < 3:
        r.warn(f"英語の検索語が {n_en} 個。3〜5個作る（英語が主戦場）")
    if n_ja < 1:
        r.warn("日本語の検索語が無い。1〜2個作る")


def check_layers(secs: list[Section], skipped: bool, r: Report) -> None:
    if skipped:
        return
    for sec in secs:
        m = LAYER_RE.match(sec.title)
        if not m:
            continue
        tag = m.group(1)
        inline_query = value_after(sec.own, "実行したクエリ")
        queries = meaningful(sec.fenced) + ([inline_query] if inline_query else [])
        result = value_after(sec.own, "結果")
        body = meaningful(sec.own)

        # 雛形は各層に例示のクエリを同梱している。クエリがあることを「調査した」の
        # 根拠にすると、結果が空のまま雛形が通ってしまう。見るのは結果のほう。
        if not result and not body:
            if tag in MUST_INVESTIGATE:
                r.fail(f"{tag} の結果が空。T0〜T2 は必ず全部見る")
            else:
                r.warn(f"{tag} の結果が空。上の層で見つかっているなら軽く流してよい")
            continue

        claims_none = NONE_RE.search(result or " ".join(body))
        if claims_none and not queries:
            r.fail(f"{tag} は「該当なし」と書いているが、実行したクエリが無い。"
                   "クエリの無い「該当なし」は未調査と同じ")


def parse_candidates(secs: list[Section]) -> list[dict]:
    top = find(secs, "候補")
    if top is None:
        return []
    out = []
    for sec in secs:
        if sec.level <= top.level or not (top.start < sec.start < top.end):
            continue
        if LAYER_RE.match(sec.title):
            continue
        fields = {}
        for ln in sec.own:
            m = FIELD_RE.match(ln.strip())
            if m:
                fields[m.group(1).strip()] = m.group(2).strip()
        out.append({"name": sec.title, "fields": fields, "sec": sec})
    return out


def check_candidates(cands: list[dict], r: Report) -> None:
    for c in cands:
        name = c["name"]
        if PLACEHOLDER_RE.match(name):
            r.fail(f"候補名が埋まっていない（{name}）")
        for key in CANDIDATE_FIELDS:
            if not c["fields"].get(key):
                if key == "足りないこと":
                    r.warn(f"候補「{name}」の「足りないこと」が空。"
                           "ここが空なら、それは自作の理由が無いということ")
                elif key != "監査結果":     # 監査結果は結論と併せて見る
                    r.warn(f"候補「{name}」の「{key}」が空")


def innermost(secs: list[Section], i: int) -> Section | None:
    """行 i を含む、いちばん深い節。"""
    hit = None
    for s in secs:
        if s.start < i < s.end and (hit is None or s.level > hit.level):
            hit = s
    return hit


def check_sources(lines: list[str], secs: list[Section], r: Report) -> None:
    """出典の無い数値を探す。コードブロックと一部の節は見ない。

    SKILL.md L33 は根拠を「今日取得した画面かコマンド出力」と書いている。
    URLだけを認めると、search_local.sh の出力のようなローカル由来の数が
    書けなくなる。そこで、同じ行のURLか、その節で実行したコマンドの
    **どちらか**があれば通す。候補の節にはコマンドが無いので、
    ★数やインストール数には引き続きURLが要る。
    """
    skip = set()
    for title in ("検索語", "既存で満たせない点"):
        sec = find(secs, title)
        if sec is not None:
            skip.update(range(sec.start, sec.end))

    in_fence = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or i in skip:
            continue
        m = METRIC_RE.search(ln)
        if not m or URL_RE.search(ln):
            continue
        sec = innermost(secs, i)
        if sec is not None and (meaningful(sec.fenced)
                                or value_after(sec.own, "実行したクエリ")):
            continue
        r.fail(f"{i + 1}行目: 数値「{m.group(0).strip()}」に出典が無い。"
               "同じ行に http(s):// を置くか、その節に実行したコマンドを残す")


def check_verdict(secs: list[Section], cands: list[dict], r: Report) -> None:
    sec = find(secs, "結論")
    if sec is None:
        return

    verdict = ""
    for ln in meaningful(sec.own):
        if BULLET_RE.match(ln):
            continue
        token = ln.strip().strip("`*_ 。").lower()
        if token:
            verdict = token
            break

    if verdict not in VERDICTS:
        shown = verdict or "（空欄）"
        r.fail(f"結論が「{shown}」。{' / '.join(VERDICTS)} のどれか1語で書く")

    gap_sec = find(secs, "既存で満たせない点")
    gaps = []
    if gap_sec is not None:
        for ln in gap_sec.own:
            m = BULLET_RE.match(ln.strip())
            if m and m.group(1).strip():
                gaps.append(m.group(1).strip())
    if verdict in NEEDS_GAP and not gaps:
        r.fail(f"結論が {verdict} なのに「既存で満たせない点」が1件も無い。"
               "書けないなら答えは adopt か vendor")

    source = value_after(sec.own, "- 採用元") or value_after(sec.own, "採用元")
    if verdict in NEEDS_AUDIT:
        if not source or source in ("なし", "無し"):
            r.fail(f"結論が {verdict} なのに採用元が書かれていない。"
                   "「## 候補」にある候補名を採用元に書く")
            return
        hit = next((c for c in cands if c["name"] == source), None)
        if hit is None:
            r.warn(f"採用元「{source}」が「## 候補」に見つからない。"
                   "監査結果の要否を判定できなかった")
            return
        layer = hit["fields"].get("層", "").strip().upper()
        if layer.startswith("T0"):
            return
        if not hit["fields"].get("監査結果"):
            where = f"（層 {layer}）" if layer else "（層が未記入）"
            r.fail(f"採用元「{source}」{where}の監査結果が空。"
                   "外部スキルを採用・派生するなら必須。"
                   "観点は references/sources.md の末尾")
    elif source and source not in ("なし", "無し"):
        r.warn(f"結論が build-new なのに採用元「{source}」が書かれている。"
               "借りているなら derive ではないか")


# --- 入口 ---------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="skill-prior-art 調査レポートの検証")
    p.add_argument("path", type=Path, help="レポートの Markdown")
    p.add_argument("--date", default=date.today().isoformat(),
                   help="基準日（既定は今日）")
    args = p.parse_args()

    if not args.path.is_file():
        print(f"ファイルが無い: {args.path}", file=sys.stderr)
        return 2

    raw = args.path.read_text(encoding="utf-8", errors="replace")
    # HTML コメントは雛形の説明書きなので、検査から外す。
    # 行番号を保つため、コメントの中身は改行だけ残して潰す。
    text = COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), raw)
    lines = text.splitlines()

    secs = parse_sections(lines)
    r = Report()

    check_headings(secs, r)

    skip_sec = find(secs, "調査を省略した理由")
    reason = " ".join(meaningful(skip_sec.own)) if skip_sec else ""
    skipped = bool(reason) and reason not in ("なし", "無し", "特になし")
    if skipped:
        r.warn(f"調査を省略している: {reason[:60]}。"
               "ユーザーが明示的に依頼した場合のみ通る")

    check_date(secs, args.date, r)
    check_terms(secs, r)
    check_layers(secs, skipped, r)
    cands = parse_candidates(secs)
    check_candidates(cands, r)
    check_sources(lines, secs, r)
    check_verdict(secs, cands, r)

    layers_done = sum(
        1 for s in secs
        if LAYER_RE.match(s.title) and meaningful(s.own)
    )
    print(f"検査: {args.path.name}  層 {layers_done}/6  候補 {len(cands)} 件  "
          f"基準日={args.date}")
    print("-" * 68)
    for m in r.fails:
        print(f"[不適合] {m}")
    for m in r.warns:
        print(f"[警告]   {m}")
    if not r.fails and not r.warns:
        print("問題なし")
    print("-" * 68)
    print(f"不適合 {len(r.fails)} / 警告 {len(r.warns)}")
    return r.code


if __name__ == "__main__":
    sys.exit(main())
