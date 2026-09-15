#!/usr/bin/env python3
"""iconlib — build/preview/verify が共有する土台。

ラスタライズは Chromium(Playwright) で行う。理由は1つで、
**SVG内のCSS(prefers-color-scheme)・グラデーション・clipPath を、実際にタブへ
描くのと同じエンジンで解決したいから**。cairosvg や ImageMagick は CSS を無視するので、
ダークモード対応のアイコンが黙って別物になる。
"""
import io, json, math, pathlib, re, shutil, subprocess, sys, tempfile

def die(msg: str, tag: str = "icon-builder"):
    print(f"\n[{tag}] エラー: {msg}\n", file=sys.stderr)
    sys.exit(1)

def warn(msg: str, tag: str = "icon-builder"):
    print(f"[{tag}] 警告: {msg}", file=sys.stderr)

# ------------------------------------------------------------------ SVG
VIEWBOX_RE = re.compile(r'viewBox\s*=\s*["\']([-\d.\s,]+)["\']')

def read_svg(path) -> str:
    p = pathlib.Path(path).expanduser()
    if not p.is_file():
        die(f"SVGが見つかりません: {p}")
    return p.read_text(encoding="utf-8")

def get_viewbox(svg: str):
    m = VIEWBOX_RE.search(svg)
    if not m:
        die("マスターSVGに viewBox がありません。`viewBox=\"0 0 512 512\"` を必ず付けること。\n"
            "        viewBox が無いSVGは、favicon として読まれたときに寸法が決まらず表示されない。")
    nums = [float(x) for x in re.split(r'[\s,]+', m.group(1).strip())]
    if len(nums) != 4:
        die(f"viewBox の値が4つではありません: {m.group(1)}")
    x, y, w, h = nums
    if abs(w - h) > 0.5:
        die(f"viewBox が正方形ではありません ({w}x{h})。アイコンは全ての面で正方形に切られるので、"
            "正方形で設計しないと必ずどこかが欠ける。")
    return x, y, w, h

# ------------------------------------------------- <text> をパスに変換する
def outline_text(svg: str, font_path: str | None) -> str:
    """<text> を <path> に置き換える。

    favicon の SVG は閲覧者の端末で描かれるので、フォントは絶対に解決されない。
    <text> を残したまま納品すると、環境依存で別のフォントに化けるか、何も出ない。
    ここで潰しておくのが唯一の解。
    """
    if "<text" not in svg:
        return svg
    if not font_path:
        die("SVGに <text> が含まれていますが --font が指定されていません。\n"
            "        favicon は閲覧者の端末で描かれるためフォントが解決されません。\n"
            "        --font でフォントファイルを渡すか、SVG側で最初からパスにしてください。")
    from fontTools.ttLib import TTFont, TTCollection
    from fontTools.pens.svgPathPen import SVGPathPen
    fp = pathlib.Path(font_path).expanduser()
    if not fp.is_file():
        die(f"フォントが見つかりません: {fp}")
    face = (TTCollection(str(fp)).fonts[0] if fp.suffix.lower() in (".ttc", ".otc")
            else TTFont(str(fp), fontNumber=0))
    upem = face["head"].unitsPerEm
    gs, cmap = face.getGlyphSet(), face.getBestCmap()

    def attr(tag: str, name: str, default=None):
        m = re.search(rf'\b{name}\s*=\s*["\']([^"\']*)["\']', tag)
        return m.group(1) if m else default

    def build(tag: str, body: str) -> str:
        size = float(attr(tag, "font-size", "100") or 100)
        x = float(attr(tag, "x", "0") or 0)
        y = float(attr(tag, "y", "0") or 0)
        anchor = attr(tag, "text-anchor", "start")
        tracking = float(attr(tag, "letter-spacing", "0") or 0)
        keep = []
        for a in ("fill", "class", "opacity", "fill-opacity", "transform", "id"):
            v = attr(tag, a)
            if v is not None:
                keep.append(f'{a}="{v}"')
        s = size / upem
        parts, cur, missing = [], 0.0, []
        for ch in body:
            if ch == " ":
                cur += size * 0.32 + tracking
                continue
            gname = cmap.get(ord(ch))
            if gname is None:
                missing.append(ch)
                continue
            g = gs[gname]
            pen = SVGPathPen(gs)
            g.draw(pen)
            d = pen.getCommands()
            if d:
                parts.append((d, cur))
            cur += g.width * s + tracking
        if missing:
            die("フォントに以下の文字のグリフがありません。□になるので停止します:\n"
                f"        {' '.join(sorted(set(missing)))}")
        total = cur - (tracking if parts else 0)
        dx = {"middle": -total / 2, "end": -total}.get(anchor, 0.0)
        inner = "".join(
            f'<path transform="translate({x+dx+ox:.3f} {y:.3f}) scale({s:.6f} {-s:.6f})" d="{d}"/>'
            for d, ox in parts)
        return f'<g {" ".join(keep)}>{inner}</g>'

    out = re.sub(r'(<text\b[^>]*>)(.*?)</text\s*>',
                 lambda m: build(m.group(1), m.group(2)), svg, flags=re.S)
    if "<text" in out:
        die("<text> の変換に失敗しました。tspan や入れ子は未対応なので、SVG側でパス化してください。")
    return out

# ------------------------------------------------------------ SVG 最適化
def _strip_root_size(svg: str) -> str:
    """ルート <svg> の width/height だけを消す。

    ルートに固定寸法が残っていると、面によっては拡大縮小が効かない。ただし
    <rect width=...> まで巻き添えにすると図案が消えるので、開始タグに限定する。
    """
    m = re.search(r'<svg\b[^>]*>', svg)
    if not m:
        return svg
    tag = re.sub(r'\s+(width|height)\s*=\s*["\'][^"\']*["\']', '', m.group(0))
    return svg[:m.start()] + tag + svg[m.end():]


def optimize_svg(svg: str) -> str:
    """納品する icon.svg を軽くする。壊すリスクのある変換はしない。"""
    svg = re.sub(r'<!--.*?-->', '', svg, flags=re.S)
    svg = re.sub(r'<metadata\b.*?</metadata\s*>', '', svg, flags=re.S)
    svg = re.sub(r'<(sodipodi|inkscape):[^>]*>', '', svg)
    svg = re.sub(r'\s+(xmlns:(?:sodipodi|inkscape|serif|figma)|sodipodi:[\w-]+|inkscape:[\w-]+)\s*=\s*["\'][^"\']*["\']', '', svg)
    svg = _strip_root_size(svg)   # ルートの width/height だけ落として viewBox に任せる
    svg = re.sub(r'(\d+\.\d{4,})', lambda m: f"{float(m.group(1)):.3f}".rstrip("0").rstrip("."), svg)
    svg = re.sub(r'>\s+<', '><', svg)
    return svg.strip()

# ------------------------------------------------------------ ラスタライズ
class Renderer:
    """Chromium を1回だけ起動して、必要なサイズを順に焼く。

    毎サイズ直接ラスタライズするのが要点。大きく焼いて縮小すると、16px では
    ブラウザが実際に行う描画と別物（にじんだもの）になり、判定を誤る。
    """
    def __init__(self, svg: str, color_scheme: str = "light"):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._b = self._pw.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
        self._pg = self._b.new_page(viewport={"width": 1200, "height": 1200}, device_scale_factor=1)
        self._pg.emulate_media(color_scheme=color_scheme)
        self._svg = svg
        self._tmp = tempfile.TemporaryDirectory()

    def use(self, svg: str):
        """描くSVGを差し替える。

        Chromium(Playwright)の同期APIは入れ子で起動できないので、別のSVGを焼きたい
        ときは新しい Renderer を作らずにこれを使う。マークだけのSVGやmonochrome用の
        SVGを同じセッションで処理するためのもの。
        """
        self._svg = svg
        return self

    def render(self, px: int):
        """px×px の透過 RGBA を返す。"""
        from PIL import Image
        html = ('<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:transparent}'
                f'#w{{width:{px}px;height:{px}px;line-height:0}}'
                '#w svg{width:100%;height:100%;display:block}</style>'
                f'<div id="w">{self._svg}</div>')
        p = pathlib.Path(self._tmp.name) / "i.html"
        p.write_text(html, encoding="utf-8")
        vw = max(px + 40, 400)
        self._pg.set_viewport_size({"width": vw, "height": vw})
        self._pg.goto(p.resolve().as_uri())
        self._pg.wait_for_timeout(80)
        buf = self._pg.locator("#w").screenshot(omit_background=True)
        return Image.open(io.BytesIO(buf)).convert("RGBA")

    def close(self):
        try: self._b.close(); self._pw.stop(); self._tmp.cleanup()
        except Exception: pass

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

# ------------------------------------------------------------- 画像ユーティリティ
def ink_bbox(img):
    """不透明ピクセルの外接矩形を (l,t,r,b) の 0-1 比率で返す。無ければ None。"""
    a = img.getchannel("A")
    bb = a.getbbox()
    if bb is None:
        return None
    w, h = img.size
    return (bb[0] / w, bb[1] / h, bb[2] / w, bb[3] / h)

def is_full_bleed(img, thresh: float = 0.70) -> bool:
    """キャンバスをほぼ塗り切っているか（バッジ型か、透過の図案型か）。

    四辺の画素で見てはいけない。角丸の矩形プレートは四隅が透明なので、
    バッジ型なのに図案型と誤判定される。面積で見れば、角丸矩形96%・円78%・
    文字だけ15% と、きれいに分かれる。
    """
    import numpy as np
    a = np.array(img.getchannel("A"))
    return float((a > 200).mean()) >= thresh

def border_bg(img, ring: int = 3):
    """画像の外周から地色を推定し、(RGB, その色が外周に占める割合) を返す。

    「どこがインクか」を、宣言された地色ではなく画像自身から決めるための関数。
    全面塗りのプレートは外周に出るので地色側に回り、その上のマークだけがインクになる。
    これで「角丸プレートの四隅が円形クロップで切れる」を誤検出しなくなる。
    """
    import numpy as np
    a = np.array(img.convert("RGB"))
    h, w = a.shape[:2]
    edge = np.concatenate([a[:ring].reshape(-1, 3), a[-ring:].reshape(-1, 3),
                           a[:, :ring].reshape(-1, 3), a[:, -ring:].reshape(-1, 3)])
    cols, cnt = np.unique(edge, axis=0, return_counts=True)
    i = int(cnt.argmax())
    return tuple(int(v) for v in cols[i]), float(cnt[i] / len(edge))


def hex_rgb(s: str):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        die(f"色は #RRGGBB で指定してください: {s}")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))

def compose(renderer, canvas: int, content_frac: float, bg: str | None, bbox=None):
    """canvas×canvas の上に、インクが content_frac を占めるようマスターを載せる。

    bg が None なら透過のまま。content_frac が 1.0 かつ bg が None なら素通し。
    """
    from PIL import Image
    if content_frac >= 0.999 and bg is None:
        return renderer.render(canvas)
    target = max(1, int(round(canvas * content_frac)))
    if bbox is None:
        src = renderer.render(target)
        ox = oy = (canvas - target) // 2
    else:
        l, t, r, b = bbox
        fw, fh = max(r - l, 1e-6), max(b - t, 1e-6)
        scale = target / max(fw, fh)
        full = max(1, int(round(scale)))
        src = renderer.render(full)
        crop = src.crop((int(l * full), int(t * full), math.ceil(r * full), math.ceil(b * full)))
        src = crop
        ox = (canvas - src.width) // 2
        oy = (canvas - src.height) // 2
    base = Image.new("RGBA", (canvas, canvas), (*hex_rgb(bg), 255) if bg else (0, 0, 0, 0))
    base.alpha_composite(src, (max(ox, 0), max(oy, 0)))
    return base

def save_png(img, path, opaque: bool = False, bg: str = "#ffffff"):
    from PIL import Image
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if opaque:
        flat = Image.new("RGB", img.size, hex_rgb(bg))
        flat.paste(img, mask=img.getchannel("A"))
        flat.save(p, "PNG", optimize=True)
    else:
        img.save(p, "PNG", optimize=True)
    return p

def optimize_png(path, quality="70-95") -> int:
    """pngquant があれば通す。アイコンは色数が少ないので視認できる劣化はまず出ない。"""
    p = pathlib.Path(path)
    before = p.stat().st_size
    if shutil.which("pngquant"):
        try:
            subprocess.run(["pngquant", f"--quality={quality}", "--force", "--skip-if-larger",
                            "--strip", "--output", str(p), "--", str(p)],
                           check=False, capture_output=True, timeout=60)
        except Exception:
            pass
    after = p.stat().st_size
    return after if after else before

def contrast_ratio(c1, c2) -> float:
    def lum(c):
        f = []
        for v in c[:3]:
            v /= 255.0
            f.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
    a, b = sorted([lum(c1), lum(c2)], reverse=True)
    return (a + 0.05) / (b + 0.05)
