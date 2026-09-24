#!/usr/bin/env python3
"""meeting-deck が生成した会議資料HTMLを、投影に耐えるかで検査する。

    python3 check_deck.py deck.html
    python3 check_deck.py ../assets/deck.css           # 配色だけ測る
    python3 check_deck.py deck.html --widths 800,2000  # 測る画面の幅を変える

5つを見る。前の2つは eli15 の check_contrast.py から引き継いだもの。

1. CSSの組 — deck.css が保証している「文字色 × 下地」の全組み合わせを、
   :root と @media (prefers-color-scheme:dark) の値で実際に計算する。
2. SVG内の文字の色 — <text> の座標を、それを囲んでいる図形の座標と突き合わせ、
   実際に重なっている図形の fill を下地として比を出す。
3. 画面の幅ごとの文字の大きさ — ここがこのスキル固有の検査。
4. 幅の固定 — 本文・見出し・紙面に最大幅を足していないか、余白を書き換えていないか。
5. 図中の文字のはみ出し — 箱や図の端を越えていないか、バーや箱と重なっていないか。

3 が要る理由。SVG は viewBox の座標系で書き、表示時に紙面の幅へ引き伸ばされる。
紙面の幅は画面の幅で決まる（最大幅を置かない）ので、同じ font-size でも
狭い画面では縮み、広い画面では膨らむ。

    実際の大きさ = font-size × (紙面の幅 ÷ viewBox の幅)
    紙面の幅     = 画面の幅 − 余白 × 2      余白 = max(24px, 12vw − 72px)

だから1つの幅で測っても足りない。いちばん狭い幅（既定 800px）で 14px を割らないか、
いちばん広い幅（既定 2000px）で本文に比べて大きくなりすぎないかを両側で測る。

5 は文字数から幅を見積もる（全角 1em、英数字は実測した平均幅）。見積もりは
やや大きめに出るので、ここで通れば実際にも収まっている。正確な値は
shoot_deck.py がブラウザで描画して測る。

終了コード: 0=問題なし / 1=警告あり / 2=不適合
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

AA_TEXT = 4.5          # 本文・図中の文字
AA_NONTEXT = 3.0       # 枠線など、文字でない要素

# 投影・画面共有に耐える下限（描画後の px）。
# 画面共有は受け手側で 70〜80% に縮むことがあるので、原寸で足りていても足りない。
LEGIBLE_MIN = 14.0     # これを割ったら不適合
BODY_MIN = 18.0        # 本文の下限
WIDTHS = (800, 1600, 2000)   # 測る画面の幅。狭い側で下限、広い側で上限を見る
TOO_BIG = 1.75         # 図中の文字が本文の何倍を超えたら「図だけ浮く」とみなすか
FIG_MAX_H = 420        # viewBox の高さの目安。これを超えると 16:9 の画面で図が 6 割を超える
INNER_PAD = 6.0        # 箱の中の文字が枠から空ける最小の余白（user unit）。枠に触れた文字は窮屈に見える

# deck.css の余白と文字の基準。幅の計算はこの式を前提にしているので、
# 書き換えられていたら計算そのものが成り立たない。
GUTTER_RULE = "max(24px,12vw-72px)"
ROOT_RULE = "clamp(16px,8px+.5vw,24px)"

FONT_SIZE_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
LEN_RE = re.compile(r"^\s*([-+]?[\d.]+)\s*(px|em|rem|pt|%)?\s*$")

# deck.css が保証している「文字色 × 下地」の組。値は変わっても、組は設計そのもの。
CSS_PAIRS = [
    ("本文 body",                      "--ink",  "--paper"),
    ("カード内の本文 .card",            "--ink",  "--card"),
    ("見出し h1/h2/h3",                "--ink",  "--paper"),
    ("見出し h3（カード内）",           "--ink",  "--card"),
    ("節番号 h2 .n",                   "--on-accent-soft", "--accent-soft"),
    ("節の索引 .rail a",               "--sub",  "--paper"),
    ("節の索引（現在地）",              "--on-accent-soft", "--accent-soft"),
    ("ラベル .eyebrow",                "--sub",  "--paper"),
    ("強調カード .card.accent",         "--ink",  "--accent-soft"),
    ("強調カードの見出し h3",           "--on-accent-soft", "--accent-soft"),
    ("強調カードのリンク",              "--accent", "--accent-soft"),
    ("注意書きの本文 .warn",            "--ink",  "--warn-soft"),
    ("注意書きの強調 .warn b",          "--warn", "--warn-soft"),
    ("危険の本文 .warn.danger",         "--ink",  "--danger-soft"),
    ("危険の強調 .warn.danger b",       "--danger", "--danger-soft"),
    ("数字 .stat b",                   "--ink",  "--paper"),
    ("数字の説明 .stat span",           "--sub",  "--paper"),
    ("数字の出典 .stat cite",           "--sub",  "--paper"),
    ("表の見出し th",                   "--on-accent-soft", "--accent-soft"),
    ("表の本体 td",                    "--ink",  "--card"),
    ("figcaption",                     "--sub",  "--paper"),
    ("リンク a",                       "--accent", "--paper"),
    ("リンク a（カード内）",            "--accent", "--card"),
    ("図の文字 svg .t",                "--ink",  "--card"),
    ("図の補助文字 svg .t-sub",         "--sub",  "--card"),
    ("図の強調面の文字 svg .t-a",       "--on-accent-soft", "--accent-soft"),
    ("図の警告面の文字 svg .t-w",       "--warn", "--warn-soft"),
    ("図の強調文字 svg .t-em",         "--accent", "--card"),
    ("図の強調文字 svg .t-em（地）",   "--accent", "--paper"),
]

# 図形の輪郭と矢印。ここは 3:1 を譲らない。
#
# 図の中の四角や矢印は飾りではなく、それ自体が「箱が2つある」「こちらへ流れる」という
# 情報を持っている。輪郭が見えなくなった図は、中の文字が読めても意味が伝わらない。
# 投影すると線はさらに飛ぶので、ここを緩めると会議室で真っ先に崩れる。
CSS_OUTLINES = [
    ("図の面の輪郭 svg .box",       "--line-strong", ["--card", "--paper"]),
    ("図の強調面の輪郭 svg .box-a", "--accent",      ["--accent-soft"]),
    ("図の警告面の輪郭 svg .box-w", "--warn",        ["--warn-soft"]),
    ("図の線と矢じり svg .ln/.ar",  "--line-strong", ["--card", "--paper"]),
    ("図の囲い svg .group",         "--line-strong", ["--card", "--paper"]),
    ("数字の上端 .stat",            "--line-strong", ["--paper"]),
    ("フォーカスの輪郭 :focus-visible", "--accent",  ["--paper", "--card"]),
]

# 紙面の罫線。ここは 3:1 を求めない。
#
# カードの枠や表の区切りは、それ自体が情報を持っているわけではない。
# 「ここから別の塊」と分かればよく、中身を読むのに枠を見る必要はない。
# 現代的な組版でこれらが 1px の淡い線なのは手抜きではなく、
# 線を強くするほど1画面あたりの線の本数が増え、読む前に視線が引っかかるため。
#
# なのでここで見るのは「見えるかどうか」だけ。--line を --paper と同じ値に
# してしまった、といった事故を止めるのがこの検査の仕事。
CHROME_MIN = 1.15
CSS_CHROME = [
    ("カードの枠 .card",      "--line", ["--card", "--paper"]),
    ("図の枠 figure svg",     "--line", ["--card", "--paper"]),
    ("節の区切り .panel",     "--line", ["--paper"]),
    ("索引の下端 .rail",      "--line", ["--paper"]),
    ("索引の枠 .rail a",      "--line", ["--paper"]),
    ("表の罫線 th,td",        "--line", ["--card", "--accent-soft"]),
    ("表の外枠 .scroll",      "--line", ["--card", "--paper"]),
    ("注意書きの縦線 .warn",  "--warn",   ["--warn-soft"]),
    ("危険の縦線 .warn.danger", "--danger", ["--danger-soft"]),
]

SHAPES = ("rect", "circle", "ellipse", "polygon", "polyline")
COLOR_ATTR = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|currentColor$)")
TRANSLATE = re.compile(r"translate\(\s*([-\d.eE]+)[\s,]+([-\d.eE]+)?\s*\)")
OTHER_TRANSFORM = re.compile(r"\b(matrix|rotate|scale|skew[XY])\s*\(")


# --- 色 -----------------------------------------------------------------

def parse_color(raw: str) -> tuple[float, float, float] | None:
    """#rgb / #rrggbb / rgb() を (r,g,b) 0-255 で返す。透過や不明は None。"""
    if not raw:
        return None
    s = raw.strip().lower()
    if s.startswith("#"):
        h = s[1:]
        if len(h) in (4, 8):          # アルファ付きは下地が決まらない
            return None
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6 or any(c not in "0123456789abcdef" for c in h):
            return None
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    m = re.match(r"rgba?\(([^)]*)\)", s)
    if m:
        parts = [p.strip() for p in re.split(r"[,\s/]+", m.group(1)) if p.strip()]
        if len(parts) >= 4 and parts[3] not in ("1", "1.0", "100%"):
            return None
        try:
            vals = []
            for p in parts[:3]:
                vals.append(float(p[:-1]) * 255 / 100 if p.endswith("%") else float(p))
        except ValueError:
            return None
        return tuple(max(0.0, min(255.0, v)) for v in vals)  # type: ignore[return-value]
    return {"white": (255.0, 255.0, 255.0), "black": (0.0, 0.0, 0.0)}.get(s)


def luminance(rgb: tuple[float, float, float]) -> float:
    def lin(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# --- CSS ----------------------------------------------------------------

def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def extract_css(text: str, path: Path) -> str:
    if path.suffix.lower() == ".css":
        return strip_comments(text)
    blocks = re.findall(r"<style\b[^>]*>(.*?)</style>", text, re.S | re.I)
    return strip_comments("\n".join(blocks))


def decls(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in block.split(";"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out


def root_vars(css: str) -> tuple[dict[str, str], dict[str, str]]:
    """(light, dark) の変数表を返す。dark は light を上書きした完全な表。"""
    dark_css = ""
    for m in re.finditer(r"@media[^{]*prefers-color-scheme\s*:\s*dark[^{]*\{", css):
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += (css[i] == "{") - (css[i] == "}")
            i += 1
        dark_css += css[m.end():i - 1]
    light_css = css.replace(dark_css, " ") if dark_css else css

    def collect(src: str) -> dict[str, str]:
        found: dict[str, str] = {}
        for m in re.finditer(r":root\s*\{([^}]*)\}", src):
            for k, v in decls(m.group(1)).items():
                if k.startswith("--"):
                    found[k] = v
        return found

    light = collect(light_css)
    dark = dict(light)
    dark.update(collect(dark_css))
    return light, dark


def resolve(value: str, table: dict[str, str], seen: frozenset[str] = frozenset()) -> str:
    """var(--x, fallback) を辿って実際の値にする。"""
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.*))?\)", value.strip(), re.S)
    if not m:
        return value.strip()
    name, fallback = m.group(1), m.group(2)
    if name in seen:
        return ""
    if name in table:
        return resolve(table[name], table, seen | {name})
    return resolve(fallback, table, seen | {name}) if fallback else ""


def svg_class_colors(css: str, table: dict[str, str]) -> dict[str, dict[str, str]]:
    """`svg .box{fill:var(--card)}` の形から クラス → {fill, stroke} を作る。"""
    out: dict[str, dict[str, str]] = {}
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        classes = re.findall(r"svg\s+\.([\w-]+)", sel)
        if not classes:
            continue
        d = decls(body)
        for name in classes:
            entry = out.setdefault(name, {})
            for prop in ("fill", "stroke"):
                if prop in d:
                    entry[prop] = resolve(d[prop], table)
    return out


# --- SVG ----------------------------------------------------------------

def tag_of(el) -> str:
    return el.tag.rsplit("}", 1)[-1].lower()


def floats(el, *names, default=0.0) -> list[float]:
    vals = []
    for n in names:
        raw = (el.get(n) or "").strip()
        m = re.match(r"^[-+]?[\d.]+(?:[eE][-+]?\d+)?", raw)
        vals.append(float(m.group(0)) if m else default)
    return vals


def contains(el, tag: str, px: float, py: float) -> bool:
    if tag == "rect":
        x, y, w, h = floats(el, "x", "y", "width", "height")
        return x <= px <= x + w and y <= py <= y + h
    if tag == "circle":
        cx, cy, r = floats(el, "cx", "cy", "r")
        return math.hypot(px - cx, py - cy) <= r
    if tag == "ellipse":
        cx, cy, rx, ry = floats(el, "cx", "cy", "rx", "ry")
        if rx <= 0 or ry <= 0:
            return False
        return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1
    if tag in ("polygon", "polyline"):
        nums = [float(v) for v in re.findall(r"[-+]?[\d.]+(?:[eE][-+]?\d+)?", el.get("points") or "")]
        pts = list(zip(nums[::2], nums[1::2]))
        if len(pts) < 3:
            return False
        inside = False
        for i in range(len(pts)):
            (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
            if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside
    return False


def walk(el, dx: float, dy: float, classes: tuple[str, ...], out: list, r) -> None:
    tr = el.get("transform") or ""
    if OTHER_TRANSFORM.search(tr):
        r.warn(f"<{tag_of(el)}> に translate 以外の transform があり、座標を追えない: {tr[:40]}")
    m = TRANSLATE.search(tr)
    if m:
        dx += float(m.group(1))
        dy += float(m.group(2) or 0)

    own = tuple(c for c in (el.get("class") or "").split() if c)
    here = classes + own
    out.append((el, tag_of(el), dx, dy, here))
    for child in el:
        walk(child, dx, dy, here, out, r)


def text_of(el) -> str:
    return " ".join("".join(el.itertext()).split())


# --- 報告 ---------------------------------------------------------------

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
        return 2 if self.fails else (1 if self.warns else 0)


def judge(r: Report, label: str, fg_raw: str, bg_raw: str, theme: str,
          need: float, rows: list) -> None:
    fg, bg = parse_color(fg_raw), parse_color(bg_raw)
    if fg is None or bg is None:
        missing = fg_raw if fg is None else bg_raw
        r.warn(f"[{theme}] {label}: 色を解決できない（{missing or '未定義'}）。半透明や未定義の変数は測れない")
        return
    v = ratio(fg, bg)
    rows.append((theme, label, fg_raw, bg_raw, v, need))
    if v < need:
        r.fail(f"[{theme}] {label}: {v:.2f}:1（必要 {need}:1）  文字 {fg_raw} / 下地 {bg_raw}")
    elif v < need * 1.1:
        r.warn(f"[{theme}] {label}: {v:.2f}:1。基準 {need}:1 すれすれ。値をいじると落ちる")


def judge_border(r: Report, label: str, line_raw: str,
                 surfaces: list[tuple[str, str]], theme: str, rows: list,
                 need: float = AA_NONTEXT) -> None:
    """線は隣り合う面のうち良いほうで見る。両側とも基準を割ったときだけ落とす。

    need は線の役割で変える。図形の輪郭は 3:1（CSS_OUTLINES）、
    紙面の罫線は「見えていること」だけを見る（CSS_CHROME / CHROME_MIN）。
    """
    line = parse_color(line_raw)
    if line is None:
        r.warn(f"[{theme}] {label}: 線の色を解決できない（{line_raw or '未定義'}）")
        return
    scored = []
    for name, raw in surfaces:
        c = parse_color(raw)
        if c is not None:
            scored.append((ratio(line, c), name, raw))
    if not scored:
        r.warn(f"[{theme}] {label}: 隣の面の色を解決できない")
        return
    best, name, raw = max(scored)
    rows.append((theme, f"{label}（対 {name}）", line_raw, raw, best, need))
    if best < need:
        pairs = "、".join(f"{n} で {v:.2f}:1" for v, n, _ in sorted(scored, reverse=True))
        r.fail(f"[{theme}] {label}: どの面とも {need}:1 に届かない（{pairs}）。"
               "線が消えて見える")


def check_palette(r: Report, themes: dict[str, dict[str, str]], min_text: float,
                  rows: list) -> None:
    for theme, table in themes.items():
        for label, fg, bg in CSS_PAIRS:
            judge(r, label, resolve(f"var({fg})", table), resolve(f"var({bg})", table),
                  theme, min_text, rows)
        for label, line, surfaces in CSS_OUTLINES:
            judge_border(r, label, resolve(f"var({line})", table),
                         [(s, resolve(f"var({s})", table)) for s in surfaces],
                         theme, rows, AA_NONTEXT)
        for label, line, surfaces in CSS_CHROME:
            judge_border(r, label, resolve(f"var({line})", table),
                         [(s, resolve(f"var({s})", table)) for s in surfaces],
                         theme, rows, CHROME_MIN)


def check_svg(r: Report, html: str, themes: dict[str, dict[str, str]], css: str,
              min_text: float, rows: list) -> int:
    svgs = re.findall(r"<svg\b.*?</svg>", html, re.S | re.I)
    if not svgs:
        return 0

    checked = 0
    for i, src in enumerate(svgs, 1):
        try:
            root = ElementTree.fromstring(src)
        except ElementTree.ParseError as e:
            r.warn(f"図{i}: SVG を解析できない（{e}）。座標の検査を飛ばした")
            continue

        nodes: list = []
        walk(root, 0.0, 0.0, (), nodes, r)

        shapes = [(el, tag, dx, dy, cls) for el, tag, dx, dy, cls in nodes if tag in SHAPES]
        texts = [(el, dx, dy, cls) for el, tag, dx, dy, cls in nodes if tag == "text"]

        for el, tag, _, _, _ in nodes:
            for prop in ("fill", "stroke"):
                raw = (el.get(prop) or "").strip()
                if raw and raw.lower() not in ("none", "inherit") and COLOR_ATTR.match(raw):
                    r.fail(f"図{i}: <{tag}> が {prop}=\"{raw}\" を直書きしている。"
                           "クラス+CSS変数にする（ダークで図だけ取り残される）")

        for el, dx, dy, cls in texts:
            tx, ty = floats(el, "x", "y")
            px, py = tx + dx, ty + dy
            head = text_of(el)[:24] or "(空)"
            where = f"図{i}「{head}」(x={px:g}, y={py:g})"

            under = None
            for sel, tag, sdx, sdy, scls in shapes:
                local = type(sel)(sel.tag, dict(sel.attrib))
                if contains(local, tag, px - sdx, py - sdy):
                    under = (tag, scls)          # 後に描いたものが上に乗る
            if under is None and not shapes:
                under = ("(図の地)", ())
            if under is None:
                # 図の地に直接置く文字は、この資料では普通（バーのラベル、枝の条件、
                # 時系列の見出し、やりとりの説明）。下地は figure svg{background:var(--card)}
                # と分かっているので、比はそのまま測れる。件数だけ数えて警告にはしない。
                r.ground = getattr(r, "ground", 0) + 1
                under = ("(図の地)", ())

            for theme, table in themes.items():
                palette = svg_class_colors(css, table)
                fg = next((palette[c]["fill"] for c in reversed(cls)
                           if c in palette and "fill" in palette[c]), None)
                if fg is None:
                    r.warn(f"[{theme}] {where}: 文字色のクラスが無い。"
                           "`.t` `.t-sub` `.t-a` などを付ける")
                    break
                shape_tag, shape_cls = under
                bg = next((palette[c]["fill"] for c in reversed(shape_cls)
                           if c in palette and "fill" in palette[c]), None)
                # 塗っていない図形（.group のような囲い）は何も覆っていないので、
                # その内側の文字が乗っているのは図の地。透明を下地として測ろうとすると
                # 「色を解決できない」で止まるが、実際には測れる。
                if bg is not None and bg.strip().lower() in ("none", "transparent"):
                    bg, shape_tag = None, "(図の地)"
                if bg is None:
                    bg = resolve("var(--card)", table)   # figure svg{background:var(--card)}
                label = f"{where} on <{shape_tag}>"
                judge(r, label, fg, bg, theme, min_text, rows)
            checked += 1

    return checked


# --- 投影したときの文字の大きさ -----------------------------------------

def parse_len(raw: str | None, inherited: float | None) -> float | None:
    """SVG 内の長さを user unit に直す。em は継承値に対する倍率。"""
    if not raw:
        return None
    m = LEN_RE.match(raw)
    if not m:
        return None
    v = float(m.group(1))
    unit = m.group(2) or "px"          # SVG では単位なし = user unit = px 相当
    if unit in ("px",):
        return v
    if unit == "pt":
        return v * 4 / 3
    if unit == "rem":
        return v * 16.0
    if unit == "em":
        return v * (inherited if inherited else 16.0)
    if unit == "%":
        return (inherited if inherited else 16.0) * v / 100
    return None


def css_font_sizes(css: str) -> dict[str, str]:
    """セレクタ → font-size の値。`svg .t{font-size:14px}` のような指定を拾う。"""
    out: dict[str, str] = {}
    for sel, body in FONT_SIZE_RULE.findall(strip_comments(css)):
        d = decls(body)
        if "font-size" not in d:
            continue
        for one in sel.split(","):
            out[" ".join(one.split())] = d["font-size"]
    return out


def layout(width: float) -> tuple[float, float]:
    """画面の幅 → (紙面の幅, 本文の px)。deck.css の --gutter と html の font-size の式。"""
    gutter = max(24.0, 0.12 * width - 72.0)
    root = min(24.0, max(16.0, 8.0 + 0.005 * width))
    return width - 2 * gutter, root * 1.25


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


# deck.css 自身が持っている幅の指定。どれも「紙面の幅」ではなく部品の中の話。
ALLOWED_WIDTH = {
    ("figuresvg", "width", "100%"),         # 図を紙面いっぱいに出す
    ("table", "width", "max-content"),      # 列の幅を中身に決めさせる
    ("table", "min-width", "100%"),         # 中身の少ない表が縮まないように
    ("th,td", "max-width", "22em"),         # 1セルの上限。表が数千pxに伸びるのを防ぐ
}
WIDTH_PROPS = ("width", "max-width", "min-width", "inline-size",
               "max-inline-size", "min-inline-size")


def check_fixed_width(r: Report, html: str, css: str) -> None:
    """幅の固定を止める。本文・見出し・紙面に上限を置くと、広い画面で右が空き、
    本文が短く折れて改行が崩れる。deck.css は上限を置かない設計で、
    左右の余白だけを --gutter で決めている。"""
    clean = strip_comments(css)

    m = re.search(r"--gutter\s*:\s*([^;}]+)", clean)
    if not m:
        r.fail("--gutter（左右の余白）が定義されていない。deck.css をそのまま貼る")
    elif squash(m.group(1)) != GUTTER_RULE:
        r.fail(f"--gutter が書き換えられている（{m.group(1).strip()}）。"
               "余白の幅はテンプレートで決めてあり、資料ごとに変えない")
    mh = re.search(r"(?<![\w.#-])html\s*\{[^{}]*font-size\s*:\s*([^;}]+)", clean)
    if not mh or squash(mh.group(1)) != ROOT_RULE:
        r.fail("html の font-size が deck.css と違う。広い画面で本文と図の文字の比を"
               "保つための式なので、書き換えない")

    for sel, body in FONT_SIZE_RULE.findall(clean):
        sel_n = squash(sel)
        if sel_n.startswith("@"):
            continue
        d = decls(body)
        for prop in WIDTH_PROPS:
            if prop in d and (sel_n, prop, squash(d[prop])) not in ALLOWED_WIDTH:
                if re.search(r"(^|,)svg\s", " ".join(sel.split())) and prop == "width":
                    continue
                r.fail(f"`{' '.join(sel.split())}{{{prop}:{d[prop]}}}` で幅を固定している。"
                       "本文・見出し・図・紙面に幅の上限を足さない（広い画面で右が空き、"
                       "改行が崩れる）。余白は --gutter だけで決まる")
        for prop, val in d.items():
            if not (prop.startswith("padding") or prop.startswith("margin")):
                continue
            v = squash(val)
            if re.search(r"-(top|bottom|block)", prop):
                continue                       # 縦の余白は幅に関係しない
            if sel_n == ".deck" and "var(--gutter)" not in v:
                r.fail(f"`.deck{{{prop}:{val}}}` が --gutter を使っていない。"
                       "左右の余白は var(--gutter) で取る")
            elif "vw" in v or re.search(r"calc\([^)]*%", v) or "50%" in v:
                r.fail(f"`{' '.join(sel.split())}{{{prop}:{val}}}` は余白で幅を作っている"
                       "（画面の幅に連動する余白は、最大幅を置くのと同じ）。余白は --gutter だけ")

    for m in re.finditer(r"<(?!svg\b)(\w+)\b[^>]*\bstyle\s*=\s*(\"[^\"]*\"|'[^']*')", html, re.I):
        st = squash(m.group(2))
        if any(re.search(rf"(^|[;\"']){p}:", st) for p in WIDTH_PROPS):
            r.fail(f"<{m.group(1)}> の style 属性で幅を指定している（{m.group(2)[:50]}）。"
                   "幅は固定しない")

    for i, m in enumerate(re.finditer(r"<svg\b[^>]*>", html, re.I), 1):
        if re.search(r"\s(width|height)\s*=", m.group(0)):
            r.fail(f"図{i}: <svg> に width / height の属性がある。図の大きさが固定され、"
                   "紙面の幅に合わせて伸び縮みしなくなる。viewBox だけにする")


# --- 図中の文字のはみ出し -----------------------------------------------

NARROW = set(".,:;'!|`")
MID = set("()[]{}-/\\\"")


def text_width(s: str, fs: float, bold: bool) -> float:
    """文字列の幅（user unit）を見積もる。やや大きめに出る。

    全角（かな・漢字・全角記号）は 1em。英数字は Chrome + Hiragino / SF で実測した
    平均幅を少し切り上げた値。矢印などの幅が曖昧な記号は、全角として数える。"""
    import unicodedata
    w = 0.0
    for ch in s:
        if ch == " ":
            w += 0.28
        elif ord(ch) < 128:
            if ch.isdigit():
                w += 0.62
            elif ch.isupper():
                w += 0.68
            elif ch.islower():
                w += 0.52
            elif ch in NARROW:
                w += 0.25
            elif ch in MID:
                w += 0.36
            else:
                w += 0.62
        else:
            w += 0.62 if unicodedata.east_asian_width(ch) in ("Na", "H") else 1.0
    return w * fs * (1.07 if bold else 1.0)


def shape_box(el, tag: str, dx: float, dy: float) -> tuple[float, float, float, float] | None:
    if tag == "rect":
        x, y, w, h = floats(el, "x", "y", "width", "height")
    elif tag == "circle":
        cx, cy, rr = floats(el, "cx", "cy", "r")
        x, y, w, h = cx - rr, cy - rr, 2 * rr, 2 * rr
    elif tag == "ellipse":
        cx, cy, rx, ry = floats(el, "cx", "cy", "rx", "ry")
        x, y, w, h = cx - rx, cy - ry, 2 * rx, 2 * ry
    else:
        return None
    return x + dx, y + dy, w, h


def check_overflow(r: Report, html: str) -> int:
    """文字が箱や図の端を越えていないか、地に置いた文字がバーや箱と重なっていないか。"""
    checked = 0
    for i, src in enumerate(re.findall(r"<svg\b.*?</svg>", html, re.S | re.I), 1):
        try:
            root = ElementTree.fromstring(src)
        except ElementTree.ParseError:
            continue
        vb = (root.get("viewBox") or "").replace(",", " ").split()
        if len(vb) != 4:
            continue
        vx, vw = float(vb[0]), float(vb[2])

        nodes: list = []
        walk(root, 0.0, 0.0, (), nodes, Report())
        fsn: list = []
        walk_fs(root, None, (), fsn)
        fs_of = {id(el): fs for el, _, _, fs in fsn}

        boxes = []
        for el, tag, dx, dy, cls in nodes:
            b = shape_box(el, tag, dx, dy)
            if b and b[2] > 0 and b[3] > 0:
                boxes.append((b, tag, "group" in cls))

        for el, tag, dx, dy, cls in nodes:
            if tag != "text":
                continue
            s = text_of(el)
            if not s:
                continue
            fs = fs_of.get(id(el)) or 16.0
            x, y = floats(el, "x", "y")
            x, y = x + dx, y + dy
            bold = (el.get("font-weight") or "400") in ("600", "700", "800", "900", "bold")
            w = text_width(s, fs, bold)
            anchor = el.get("text-anchor") or "start"
            x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
            x1 = x0 + w
            top, bot = y - 0.82 * fs, y + 0.18 * fs
            cy = y - 0.35 * fs
            head = s[:20]
            where = f"図{i}「{head}」"
            checked += 1

            holders = [(b, t, g) for b, t, g in boxes
                       if b[0] <= x <= b[0] + b[2] and b[1] <= cy <= b[1] + b[3]]
            solid = [h for h in holders if not h[2]]
            holder = min(solid or holders, key=lambda h: h[0][2] * h[0][3], default=None)

            if holder:
                bx, by, bw, bh = holder[0]
                left, right = bx + INNER_PAD - x0, x1 - (bx + bw - INNER_PAD)
                over = max(left, right)
                if over > 0:
                    r.fail(f"{where}: 箱の{'左' if left > right else '右'}端に"
                           f"約 {over:.0f} はみ出す（文字の幅 約 {w:.0f}、箱の幅 {bw:g}、"
                           f"枠との余白 {INNER_PAD:g} を含む）。文言を縮めるか、箱を広げる")
                continue

            over = max(vx - x0, x1 - (vx + vw))
            if over > 0:
                r.fail(f"{where}: 図の{'左' if vx - x0 > x1 - (vx + vw) else '右'}端を"
                       f"約 {over:.0f} 越えて切れる（viewBox の幅 {vw:g}）。"
                       "文言を縮めるか、置く位置を変える")
                continue

            for (bx, by, bw, bh), t, g in boxes:
                if g:
                    continue
                v_ov = min(bot, by + bh) - max(top, by)
                h_ov = min(x1, bx + bw) - max(x0, bx)
                if v_ov > 0.3 * fs and h_ov > 0:
                    r.fail(f"{where}: 地に置いた文字が <{t}>（x={bx:g}〜{bx + bw:g}）と"
                           f"約 {h_ov:.0f} 重なる。長いラベルはバーの上に置く型"
                           "（figures.md 4b）にする")
                    break
    return checked


def walk_fs(el, inherited: float | None, classes: tuple[str, ...], out: list) -> None:
    own = tuple(c for c in (el.get("class") or "").split() if c)
    here = classes + own
    fs = parse_len(el.get("font-size"), inherited) or inherited
    out.append((el, tag_of(el), here, fs))
    for child in el:
        walk_fs(child, fs, here, out)


def check_legibility(r: Report, html: str, css: str, widths: tuple[float, ...],
                     rows: list) -> int:
    """図が主役の資料として、投影に耐えるかを見る。色ではなく大きさと構造の検査。"""
    clean = strip_comments(css)

    mb = re.search(r"(?<![\w.#-])body\s*\{[^{}]*font-size\s*:\s*([\d.]+)(px|rem)", clean)
    if mb:
        px = float(mb.group(1)) * (16.0 if mb.group(2) == "rem" else 1.0)
        if px < BODY_MIN:
            r.fail(f"本文が {px:g}px。投影と画面共有では {BODY_MIN:g}px 以上にする"
                   "（受け手側で 70〜80% に縮むことがある）")

    narrow, wide = min(widths), max(widths)
    c_narrow, _ = layout(narrow)
    c_wide, body_wide = layout(wide)

    svgs = re.findall(r"<svg\b.*?</svg>", html, re.S | re.I)
    if not svgs:
        r.fail("図（インラインSVG）が1点も無い。図が本文の仕事を引き受けるのがこの資料の設計で、"
               "図を置けない題材なら、そもそもこの形式が合っていない")

    for i, block in enumerate(re.findall(r"<figure\b.*?</figure>", html, re.S | re.I), 1):
        if "<figcaption" not in block.lower():
            r.warn(f"図{i}: figcaption が無い。"
                   "会議では図だけを指して話すので、何の図か単体で分かる必要がある")

    for m in re.finditer(r"<table\b", html, re.I):
        head = html[max(0, m.start() - 260):m.start()]
        if 'class="scroll"' not in head and "class='scroll'" not in head:
            r.warn("<table> が .scroll の中に入っていない。"
                   "狭い画面で全列を押し込むと、その瞬間に誰も読めない表になる")

    sizes = css_font_sizes(css)
    checked = 0

    for i, src in enumerate(svgs, 1):
        try:
            root = ElementTree.fromstring(src)
        except ElementTree.ParseError:
            continue                                   # 色の検査側で既に警告が出ている

        vb = (root.get("viewBox") or "").replace(",", " ").split()
        if len(vb) == 4:
            vw = float(vb[2])
        else:
            vw = parse_len(root.get("width"), None) or 0.0
            if vw:
                r.warn(f"図{i}: viewBox が無い。width から幅を取ったが、"
                       "viewBox を付けないと拡大時に文字がぼける")
        if not vw:
            r.warn(f"図{i}: 幅が読めないので、文字の大きさを測れなかった")
            continue

        if len(vb) == 4 and float(vb[3]) > FIG_MAX_H:
            share = float(vb[3]) * layout(1600)[0] / vw / 900
            r.warn(f"図{i}: viewBox の高さが {float(vb[3]):g}。1600×900 の画面で縦の "
                   f"{share:.0%} を占め、見出しと一緒に1画面に収まらない。"
                   f"{FIG_MAX_H} 以下に収めるか、図を分ける")

        s_narrow, s_wide = c_narrow / vw, c_wide / vw
        small_hits: list = []
        big_hits: list = []
        nodes: list = []
        walk_fs(root, None, (), nodes)

        for el, tag, cls, fs in nodes:
            if tag != "text":
                continue
            if fs is None:                             # CSS 側の指定を探す
                raw = None
                for c in reversed(cls):
                    raw = sizes.get(f"svg .{c}") or sizes.get(f".{c}")
                    if raw:
                        break
                raw = raw or sizes.get("svg text") or sizes.get("text")
                fs = parse_len(raw, None)
            head = text_of(el)[:20] or "(空)"
            where = f"図{i}「{head}」"
            if fs is None:
                r.warn(f"{where}: font-size が指定されていない。"
                       "既定の 16 user unit で出るが、意図した大きさか確認する")
                fs = 16.0
            small, big = fs * s_narrow, fs * s_wide
            rows.append(("size", f"{where} @{narrow:g}px", f"{fs:g}u", f"×{s_narrow:.2f}",
                         small, LEGIBLE_MIN))
            if small < LEGIBLE_MIN:
                small_hits.append((small, fs, head))
            elif big > body_wide * TOO_BIG:
                big_hits.append((big, fs, head))
            checked += 1

        # 1文字ずつ並べると数十行になって読まれないので、図ごとにまとめる。
        if small_hits:
            px, fs, head = min(small_hits)
            sizes_ = "・".join(f"{s:g}" for s in sorted({h[1] for h in small_hits}))
            r.fail(f"図{i}: {len(small_hits)} 件の文字が画面 {narrow:g}px で {LEGIBLE_MIN:g}px を割る"
                   f"（最小 {px:.1f}px「{head}」、font-size {sizes_}）。紙面 {c_narrow:g}px ÷ "
                   f"viewBox {vw:g} = {s_narrow:.2f} 倍に縮むため。font-size を 18 以上にする"
                   "（figures.md の 18 / 20 / 22）")
        if big_hits:
            px, fs, head = max(big_hits)
            r.warn(f"図{i}: {len(big_hits)} 件の文字が画面 {wide:g}px で本文（{body_wide:g}px）の "
                   f"{TOO_BIG:g} 倍を超える（最大 {px:.0f}px「{head}」、font-size {fs:g}）。"
                   "図だけが浮くので font-size を下げる（figures.md の 18 / 20 / 22）")

    return checked


def main() -> int:
    p = argparse.ArgumentParser(description="meeting-deck 会議資料の検証")
    p.add_argument("path", type=Path, help="資料HTML、または deck.css")
    p.add_argument("--widths", default=",".join(map(str, WIDTHS)),
                   help="測る画面の幅(px)をカンマ区切りで。最小で下限、最大で上限を見る")
    p.add_argument("--min", type=float, default=AA_TEXT,
                   help=f"文字に求める比（既定 {AA_TEXT}。AAA で見るなら 7）")
    p.add_argument("--table", action="store_true", help="測った組を全部並べる")
    args = p.parse_args()

    if not args.path.is_file():
        print(f"ファイルが無い: {args.path}", file=sys.stderr)
        return 2

    text = args.path.read_text(encoding="utf-8", errors="replace")
    css = extract_css(text, args.path)
    if not css.strip():
        print("<style> が無い。base.css の中身を <style> に貼る（外部読み込みはしない）",
              file=sys.stderr)
        return 2

    light, dark = root_vars(css)
    if not light:
        print(":root の変数が見つからない。base.css を貼っているか確認する", file=sys.stderr)
        return 2

    r = Report()
    themes = {"light": light}
    if dark != light:
        themes["dark"] = dark
    else:
        r.fail("@media (prefers-color-scheme:dark) の上書きが無い。"
               "ダークで測れないので、ダーク側の :root を足す")

    rows: list = []
    check_palette(r, themes, args.min, rows)
    is_css = args.path.suffix.lower() == ".css"
    n_text = 0 if is_css else check_svg(r, text, themes, css, args.min, rows)
    n_size = n_over = 0
    widths = tuple(float(w) for w in args.widths.split(",") if w.strip())
    if not is_css:
        check_fixed_width(r, text, css)
        n_size = check_legibility(r, text, css, widths, rows)
        n_over = check_overflow(r, text)

    print(f"検査: {args.path.name}  テーマ {'/'.join(themes)}  "
          f"組 {len(rows) - n_size} 件（うち図中の文字 {n_text} 件）  基準 {args.min}:1")
    if not is_css:
        ground = getattr(r, "ground", 0)
        tail = f"  うち図の地に直接置いた文字 {ground} 件" if ground else ""
        spans = " / ".join(f"{w:g}→{layout(w)[0]:g}px" for w in widths)
        print(f"      画面→紙面の幅 {spans}  図中の文字 {n_size} 件を測った "
              f"（{min(widths):g}px で下限 {LEGIBLE_MIN:g}px）  はみ出し {n_over} 件を見た{tail}")
    print("-" * 68)
    if args.table:
        for theme, label, fg, bg, v, need in sorted(rows, key=lambda x: x[4]):
            mark = "NG" if v < need else ("!" if v < need * 1.1 else "ok")
            unit = "px  " if theme == "size" else ":1  "
            print(f"  {mark:>2}  {v:6.2f}{unit}[{theme:5}] {label}")
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
