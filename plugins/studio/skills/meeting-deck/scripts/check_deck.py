#!/usr/bin/env python3
"""meeting-deck が生成した会議資料HTMLを、投影に耐えるかで検査する。

    python3 check_deck.py deck.html
    python3 check_deck.py ../assets/deck.css      # 配色だけ測る
    python3 check_deck.py deck.html --stage-px 960   # 紙面幅を指定して測り直す

3つを見る。前の2つは eli15 の check_contrast.py から引き継いだもの。

1. CSSの組 — deck.css が保証している「文字色 × 下地」の全組み合わせを、
   :root と @media (prefers-color-scheme:dark) の値で実際に計算する。
2. SVG内の文字の色 — <text> の座標を、それを囲んでいる図形の座標と突き合わせ、
   実際に重なっている図形の fill を下地として比を出す。
3. 投影したときの文字の大きさ — ここがこのスキル固有の検査。

3 が要る理由。SVG は viewBox の座標系で書き、表示時に紙面の幅へ引き伸ばされる。
つまり font-size="12" が実際に何 px で出るかは viewBox の広さで決まり、
**広い viewBox を取った瞬間、図中の文字が黙って縮む**。エディタでは原寸で見えるので
気づけず、会議室で投影して初めて「読めない」と分かる。この事故を止めるのがこの検査。

    実際の大きさ = font-size × (紙面の幅 ÷ viewBox の幅)

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
LEGIBLE_WARN = 16.0    # これを割ったら警告
BODY_MIN = 18.0        # 本文の下限
DECK_PADDING_PX = 48.0 # .deck の左右パディング合計（1.5rem × 2、rem=16px）
STAGE_FALLBACK = 1152.0

FONT_SIZE_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
LEN_RE = re.compile(r"^\s*([-+]?[\d.]+)\s*(px|em|rem|pt|%)?\s*$")

# deck.css が保証している「文字色 × 下地」の組。値は変わっても、組は設計そのもの。
CSS_PAIRS = [
    ("本文 body",                     "--ink",       "--paper"),
    ("カード内の本文 .card",           "--ink",       "--card"),
    ("見出し h2（黄の上）",            "--on-yellow", "--yellow"),
    ("節番号 h2 .n（黒の上）",         "--paper",     "--ink"),
    ("節の索引 .rail a",              "--ink",       "--card"),
    ("節の索引（現在地・黄の上）",      "--on-yellow", "--yellow"),
    ("ラベル .eyebrow（赤の上）",      "--on-red",    "--red"),
    ("黄カード .card.accent",          "--on-yellow", "--yellow"),
    ("青カード .card.blue",            "--on-blue",   "--blue"),
    ("見出し h3",                     "--ink",       "--paper"),
    ("見出し h3（カード内）",          "--ink",       "--card"),
    ("数字 .stat b",                  "--ink",       "--card"),
    ("数字の説明 .stat span",          "--blue",      "--card"),
    ("数字の出典 .stat cite",          "--blue",      "--card"),
    ("表の見出し th（黄の上）",        "--on-yellow", "--yellow"),
    ("表の本体 td",                   "--ink",       "--card"),
    ("figcaption（青）",               "--blue",      "--paper"),
    ("リンク a",                      "--blue",      "--paper"),
    ("リンク a（カード内）",           "--blue",      "--card"),
    ("図の補助文字 svg .t-sub",        "--blue",      "--card"),
    ("図の強調文字 svg .t-red",        "--red",       "--card"),
    ("フォーカスの輪郭 :focus-visible", "--red",       "--paper"),
]

# 枠線は2つの面のあいだに引かれる。片側と 3:1 あれば境界は見分けられるので、
# 隣り合う面のうち良いほうで見る。両側とも割ったときだけ落とす。
CSS_BORDERS = [
    ("カードの枠 .card",       "--ink",  ["--card", "--paper"]),
    ("見出しの枠 h2",          "--ink",  ["--yellow", "--paper"]),
    ("h1 の下罫",              "--ink",  ["--paper"]),
    ("図の枠 figure svg",      "--ink",  ["--card", "--paper"]),
    ("図の中の面の輪郭 svg .box-*", "--ink", ["--yellow", "--red", "--blue", "--card"]),
    ("節の区切り .panel",       "--ink",  ["--paper"]),
    ("索引の下端 .rail",        "--ink",  ["--paper"]),
    ("索引の枠 .rail a",        "--ink",  ["--card", "--paper"]),
    ("表の罫線 th,td",          "--ink",  ["--card", "--yellow"]),
    ("数字の枠 .stat",          "--ink",  ["--card", "--paper"]),
    ("数字の上端 .stat",        "--red",  ["--card", "--paper"]),
    ("figcaption の縦線",       "--blue", ["--paper"]),
    ("h3 の四角",              "--red",  ["--paper", "--card"]),
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
                 surfaces: list[tuple[str, str]], theme: str, rows: list) -> None:
    """枠線は隣り合う面のうち良いほうで見る。両側とも 3:1 を割ったときだけ落とす。"""
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
    rows.append((theme, f"{label}（対 {name}）", line_raw, raw, best, AA_NONTEXT))
    if best < AA_NONTEXT:
        pairs = "、".join(f"{n} で {v:.2f}:1" for v, n, _ in sorted(scored, reverse=True))
        r.fail(f"[{theme}] {label}: どちらの面とも {AA_NONTEXT}:1 に届かない（{pairs}）。"
               "枠が消えて見える")


def check_palette(r: Report, themes: dict[str, dict[str, str]], min_text: float,
                  rows: list) -> None:
    for theme, table in themes.items():
        for label, fg, bg in CSS_PAIRS:
            judge(r, label, resolve(f"var({fg})", table), resolve(f"var({bg})", table),
                  theme, min_text, rows)
        for label, line, surfaces in CSS_BORDERS:
            judge_border(r, label, resolve(f"var({line})", table),
                         [(s, resolve(f"var({s})", table)) for s in surfaces], theme, rows)


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
                           "`.t` `.t-sub` `.t-y` などを付ける")
                    break
                shape_tag, shape_cls = under
                bg = next((palette[c]["fill"] for c in reversed(shape_cls)
                           if c in palette and "fill" in palette[c]), None)
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


def stage_width(css: str, override: float | None) -> tuple[float, str]:
    """図が実際に引き伸ばされる幅（px）。--stage と body の font-size から出す。"""
    if override:
        return override, "指定値"
    clean = strip_comments(css)
    mb = re.search(r"\bbody\s*\{[^{}]*font-size\s*:\s*([\d.]+)px", clean)
    ms = re.search(r"--stage\s*:\s*([\d.]+)em", clean)
    if mb and ms:
        px = float(ms.group(1)) * float(mb.group(1)) - DECK_PADDING_PX
        return px, f"--stage {ms.group(1)}em × body {mb.group(1)}px − 余白 {DECK_PADDING_PX:g}px"
    return STAGE_FALLBACK, "既定値（--stage か body の font-size を読めなかった）"


def walk_fs(el, inherited: float | None, classes: tuple[str, ...], out: list) -> None:
    own = tuple(c for c in (el.get("class") or "").split() if c)
    here = classes + own
    fs = parse_len(el.get("font-size"), inherited) or inherited
    out.append((el, tag_of(el), here, fs))
    for child in el:
        walk_fs(child, fs, here, out)


def check_legibility(r: Report, html: str, css: str, stage_px: float, rows: list) -> int:
    """図が主役の資料として、投影に耐えるかを見る。色ではなく大きさと構造の検査。"""
    clean = strip_comments(css)

    mb = re.search(r"\bbody\s*\{[^{}]*font-size\s*:\s*([\d.]+)px", clean)
    if mb and float(mb.group(1)) < BODY_MIN:
        r.fail(f"本文が {mb.group(1)}px。投影と画面共有では {BODY_MIN:g}px 以上にする"
               "（受け手側で 70〜80% に縮むことがある）")

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

        scale = stage_px / vw
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
            shown = fs * scale
            rows.append(("size", where, f"{fs:g}u", f"×{scale:.2f}", shown, LEGIBLE_MIN))
            if shown < LEGIBLE_MIN:
                r.fail(f"{where}: 投影すると {shown:.1f}px で出る（font-size={fs:g}、"
                       f"viewBox の幅 {vw:g} で {scale:.2f} 倍）。"
                       f"{LEGIBLE_MIN:g}px を割る。viewBox を狭めるか font-size を上げる")
            elif shown < LEGIBLE_WARN:
                r.warn(f"{where}: 投影すると {shown:.1f}px。"
                       f"{LEGIBLE_WARN:g}px までは上げたい（画面共有で縮むと消える）")
            checked += 1

    return checked


def main() -> int:
    p = argparse.ArgumentParser(description="meeting-deck 会議資料の検証")
    p.add_argument("path", type=Path, help="資料HTML、または deck.css")
    p.add_argument("--stage-px", type=float, default=None,
                   help="図が引き伸ばされる幅(px)。既定は --stage と body の font-size から計算")
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
    n_size = 0
    stage, how = stage_width(css, args.stage_px)
    if not is_css:
        n_size = check_legibility(r, text, css, stage, rows)

    print(f"検査: {args.path.name}  テーマ {'/'.join(themes)}  "
          f"組 {len(rows) - n_size} 件（うち図中の文字 {n_text} 件）  基準 {args.min}:1")
    if not is_css:
        ground = getattr(r, "ground", 0)
        tail = f"  うち図の地に直接置いた文字 {ground} 件" if ground else ""
        print(f"      紙面の幅 {stage:g}px（{how}）  図中の文字 {n_size} 件を測った "
              f"（下限 {LEGIBLE_MIN:g}px）{tail}")
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
