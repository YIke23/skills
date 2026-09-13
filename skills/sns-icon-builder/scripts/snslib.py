#!/usr/bin/env python3
"""snslib — build / preview / verify が共有する土台。

ラスタライズは Chromium(Playwright) で行う。理由は1つで、**SVG内のCSS
(prefers-color-scheme)・グラデーション・clipPath を、実際に描くのと同じエンジンで
解決したいから**。cairosvg や ImageMagick は CSS を無視するので、ダークモード対応の
アイコンが黙って別物に焼き上がる。

このスキル固有の中身は下半分の「インクの半径」まわり。SNSは面ごとに切り抜き形状が
違うので、「外接矩形が収まるか」ではなく「中心からいちばん遠いインクがどこにあるか」で
縮尺を決める必要がある。矩形で見ると、丸いマークや菱形のマークを必要以上に縮めてしまう。
"""
import io, math, pathlib, re, shutil, subprocess, sys, tempfile

TAG = "sns-icon-builder"


def die(msg: str):
    print(f"\n[{TAG}] エラー: {msg}\n", file=sys.stderr)
    sys.exit(1)


def warn(msg: str):
    print(f"[{TAG}] 警告: {msg}", file=sys.stderr)


# ------------------------------------------------------------------ SVG
VIEWBOX_RE = re.compile(r'viewBox\s*=\s*["\']([-\d.\s,]+)["\']')


def read_svg(path) -> str:
    p = pathlib.Path(path).expanduser()
    if not p.is_file():
        die(f"SVGが見つかりません: {p}")
    return p.read_text(encoding="utf-8")


def check_viewbox(svg: str):
    m = VIEWBOX_RE.search(svg)
    if not m:
        die('マスターSVGに viewBox がありません。`viewBox="0 0 512 512"` を必ず付けること。\n'
            "        viewBox が無いSVGは拡大縮小の基準が決まらず、各社の寸法に合わせられない。")
    nums = [float(x) for x in re.split(r'[\s,]+', m.group(1).strip())]
    if len(nums) != 4:
        die(f"viewBox の値が4つではありません: {m.group(1)}")
    x, y, w, h = nums
    if abs(w - h) > 0.5:
        die(f"viewBox が正方形ではありません ({w}x{h})。SNSのアイコンは全社が正方形で受け取り、"
            "円か角丸に切る。正方形で設計しないと必ずどこかが欠ける。")
    return x, y, w, h


def outline_text(svg: str, font_path: str | None) -> str:
    """<text> を <path> に置き換える。

    SNSに上げるのはPNGなので焼いてしまえば文字は残らない。それでも変換するのは、
    **フォントが解決できていないことに気づかないまま焼くのを防ぐため**。豆腐や
    別フォントで焼かれたPNGは、見た目には成功しているように見える。
    """
    if "<text" not in svg:
        return svg
    if not font_path:
        die("SVGに <text> が含まれていますが --font が指定されていません。\n"
            "        描画環境にそのフォントがある保証は無く、無ければ別のフォントか □ で焼かれます。\n"
            "        焼き上がったPNGは一見正常なので、ここで止めます。")
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


def _strip_root_size(svg: str) -> str:
    m = re.search(r'<svg\b[^>]*>', svg)
    if not m:
        return svg
    tag = re.sub(r'\s+(width|height)\s*=\s*["\'][^"\']*["\']', '', m.group(0))
    return svg[:m.start()] + tag + svg[m.end():]


def clean_svg(svg: str) -> str:
    """描画前に落としても安全なものだけ落とす。壊すリスクのある変換はしない。"""
    svg = re.sub(r'<!--.*?-->', '', svg, flags=re.S)
    svg = re.sub(r'<metadata\b.*?</metadata\s*>', '', svg, flags=re.S)
    svg = re.sub(r'<(sodipodi|inkscape):[^>]*>', '', svg)
    svg = re.sub(r'\s+(xmlns:(?:sodipodi|inkscape|serif|figma)|sodipodi:[\w-]+|inkscape:[\w-]+)\s*=\s*["\'][^"\']*["\']', '', svg)
    svg = _strip_root_size(svg)
    svg = re.sub(r'>\s+<', '><', svg)
    return svg.strip()


# ------------------------------------------------------------ ラスタライズ
class Renderer:
    """Chromium を1回だけ起動して、必要なサイズを順に焼く。

    毎サイズ直接ラスタライズするのが要点。大きく焼いて縮小すると、20px では
    ブラウザが実際に行う描画と別物（にじんだもの）になり、判定を誤る。
    """

    def __init__(self, svg: str, color_scheme: str = "light"):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            die("playwright が入っていません。`pip install playwright && playwright install chromium`")
        self._pw = sync_playwright().start()
        self._b = self._pw.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
        self._pg = self._b.new_page(viewport={"width": 1200, "height": 1200}, device_scale_factor=1)
        self._pg.emulate_media(color_scheme=color_scheme)
        self._svg = svg
        self._tmp = tempfile.TemporaryDirectory()

    def use(self, svg: str):
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
        try:
            self._b.close(); self._pw.stop(); self._tmp.cleanup()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# ------------------------------------------------------------- 色
def hex_rgb(s: str):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        die(f"色は #RRGGBB で指定してください: {s}")
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        die(f"色として読めません: #{s}")


def contrast_ratio(c1, c2) -> float:
    def lum(c):
        f = []
        for v in c[:3]:
            v /= 255.0
            f.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
    a, b = sorted([lum(c1), lum(c2)], reverse=True)
    return (a + 0.05) / (b + 0.05)


# --------------------------------------------------- インクの位置と大きさ
def ink_bbox(img):
    """不透明ピクセルの外接矩形 (l, t, r, b) をピクセルで返す。無ければ None。"""
    bb = img.getchannel("A").getbbox()
    return bb


def is_full_bleed(img, thresh: float = 0.70) -> bool:
    """キャンバスをほぼ塗り切っているか（プレート型か、透過の図案型か）。

    四辺の画素で見てはいけない。角丸の矩形プレートは四隅が透明なので、プレート型
    なのに図案型と誤判定される。面積で見れば、角丸矩形96%・円78%・文字だけ15% と
    きれいに分かれる。
    """
    import numpy as np
    a = np.array(img.getchannel("A"))
    return float((a > 200).mean()) >= thresh


def ink_reach(img):
    """インクが画像の中心からどこまで届いているかを返す。

    返り値は (r_circle, r_square) で、どちらも「半辺を1.0としたときの距離」。
      r_circle … 中心からの直線距離の最大（円形クロップで効く）
      r_square … 中心からの縦横いずれかの距離の最大（角丸クロップで効く）

    外接矩形の角ではなく実際のインク画素で測るのが要点。矩形の角で測ると、丸い
    マークや菱形のマークを、実際には切れないのに縮めてしまう。
    """
    import numpy as np
    a = np.array(img.getchannel("A"))
    ys, xs = np.nonzero(a > 40)
    if len(xs) == 0:
        return None
    h, w = a.shape
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    half = w / 2.0
    dx, dy = np.abs(xs - cx), np.abs(ys - cy)
    return (float(np.hypot(dx, dy).max() / half), float(np.maximum(dx, dy).max() / half))


def crop_to_ink(img):
    """インクの外接矩形で切り出す。マークが viewBox の中心からずれていても中央に置き直せる。"""
    bb = ink_bbox(img)
    if bb is None:
        return None
    return img.crop(bb)


def fit_scale(mark, canvas: int, crop: str, safe: float) -> float:
    """マークを canvas に載せるときの倍率を返す。

    「切り抜かれる形の内側に、インクがぎりぎり収まる最大の大きさ」を狙う。円で切る社では
    対角が効き、角丸で切る社では縦横が効くので、同じマークでも角丸の社のほうが大きく載る。
    **同じ1枚を7箇所に上げてはいけない理由がここにある。**
    """
    reach = ink_reach(mark)
    if reach is None:
        return 1.0
    r_circle, r_square = reach
    w, h = mark.size
    half = w / 2.0
    # mark 自身の半辺を基準にした値を、canvas の半辺を基準に読み替える
    px_circle = r_circle * half
    px_square = r_square * half
    limit = (canvas / 2.0) * safe
    k = limit / (px_circle if crop == "circle" else px_square)
    # キャンバスからはみ出す倍率にはしない
    return min(k, canvas / max(w, h))


def compose(mark, canvas: int, scale: float, bg: str):
    """不透明な canvas×canvas を作り、その中央に mark を scale 倍で置く。"""
    from PIL import Image
    w, h = mark.size
    tw, th = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    src = mark.resize((tw, th), Image.LANCZOS)
    base = Image.new("RGBA", (canvas, canvas), (*hex_rgb(bg), 255))
    base.alpha_composite(src, ((canvas - tw) // 2, (canvas - th) // 2))
    return base


def render_mark(renderer, crop: str, canvas: int, bg: str, full_bleed: bool, safe: float,
                ref_px: int = 1024):
    """1サービスぶんの不透明アバターを作る。

    プレート型（キャンバスを塗り切っている意匠）は「マスクされる前提で設計されたもの」
    なので、縮めずに全面のまま焼く。縮めると地色の板が浮いた入れ子になって見える。

    図案型は、必要な大きさを先に決めてから**その大きさで直接ラスタライズする**。
    大きく焼いて縮小すると、note の330pxのような小さい面で、ブラウザが実際に描くのとは
    別物（にじんだもの）になる。20px の可読性をそこから測ると判定を誤る。
    """
    from PIL import Image
    if full_bleed:
        img = renderer.render(canvas)
        base = Image.new("RGBA", (canvas, canvas), (*hex_rgb(bg), 255))
        base.alpha_composite(img)
        return base

    ref = renderer.render(ref_px)
    bb = ink_bbox(ref)
    if bb is None:
        die("SVGを描画したら空でした。fill が透明か、viewBox の外に図形があります。")
    mark_ref = ref.crop(bb)
    k = fit_scale(mark_ref, canvas, crop, safe)
    target_w = max(1, int(round(mark_ref.width * k)))

    # インクが ref 全体に占める横幅の比から、目的の大きさで焼くためのキャンバス寸法を逆算する
    frac_w = mark_ref.width / ref_px
    full = max(8, int(round(target_w / max(frac_w, 1e-6))))
    src = crop_to_ink(renderer.render(full))
    if src is None:
        die("SVGを描画したら空でした。")
    if max(src.size) > canvas:                       # 丸めで1〜2px溢れたときだけ詰める
        s = canvas / max(src.size)
        src = src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))), Image.LANCZOS)
    base = Image.new("RGBA", (canvas, canvas), (*hex_rgb(bg), 255))
    base.alpha_composite(src, ((canvas - src.width) // 2, (canvas - src.height) // 2))
    return base


# ------------------------------------------------------------- 保存
def save_opaque(img, path, fmt: str = "PNG", quality: int = 92) -> pathlib.Path:
    """アルファを完全に落として保存する。

    SNSは全社が透過の扱いを明記していない。白で合成する社、黒で合成する社、
    そのまま暗い背景に置く社があり、透過のまま上げると見え方が制御できなくなる。
    """
    from PIL import Image
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    flat = img.convert("RGB") if img.mode != "RGBA" else Image.alpha_composite(
        Image.new("RGBA", img.size, (255, 255, 255, 255)), img).convert("RGB")
    if fmt.upper() in ("JPG", "JPEG"):
        flat.save(p, "JPEG", quality=quality, optimize=True, subsampling=0)
    else:
        flat.save(p, "PNG", optimize=True)
    return p


def optimize_png(path, quality="70-95") -> int:
    """pngquant があれば通す。アイコンは色数が少ないので視認できる劣化はまず出ない。"""
    p = pathlib.Path(path)
    if shutil.which("pngquant"):
        try:
            subprocess.run(["pngquant", f"--quality={quality}", "--force", "--skip-if-larger",
                            "--strip", "--output", str(p), "--", str(p)],
                           check=False, capture_output=True, timeout=60)
        except Exception:
            pass
    return p.stat().st_size


def shrink_to_budget(img, path, max_bytes: int) -> tuple[pathlib.Path, str]:
    """容量上限に収まるまで、PNG → 減色PNG → JPEG の順に落とす。

    GitHub と Slack の1MBが効いてくる。**減色を先に試すのは、JPEGが輪郭に圧縮ノイズを
    出すから**。アイコンは輪郭が全てなので、色数を削るほうが見た目の損失が小さい。
    """
    p = save_opaque(img, path)
    n = optimize_png(p)
    if n <= max_bytes:
        return p, "png"
    for q in (95, 90, 85, 80):
        jp = p.with_suffix(".jpg")
        save_opaque(img, jp, "JPEG", quality=q)
        if jp.stat().st_size <= max_bytes:
            p.unlink(missing_ok=True)
            return jp, f"jpeg(q={q})"
    return p, "over"


def border_color(img, ring: int | None = None):
    """画像の外周から地色を拾う。アバターは不透明なので、これが「板の色」になる。

    ring を画像サイズに比例させるのが要点。固定幅にすると、20pxに縮めた画像では
    外周の帯がマークまで飲み込み、「地色が単色でない」と誤判定する。最小表示での
    可読性はこのスキルの本題なので、そこで判定不能になっては意味がない。
    """
    import numpy as np
    a = np.array(img.convert("RGB"))
    h, w = a.shape[:2]
    if ring is None:
        ring = max(1, min(4, w // 20))
    edge = np.concatenate([a[:ring].reshape(-1, 3), a[-ring:].reshape(-1, 3),
                           a[:, :ring].reshape(-1, 3), a[:, -ring:].reshape(-1, 3)])
    cols, cnt = np.unique(edge, axis=0, return_counts=True)
    i = int(cnt.argmax())
    return tuple(int(v) for v in cols[i]), float(cnt[i] / len(edge))


def ink_mask_opaque(img, tol: int = 28, bg=None):
    """不透明画像から「地色と違うピクセル」を拾う。返り値は (mask, 地色, 判定できたか)。

    `bg` を渡せる形にしているのが要点。外周から推定する方式は、インクが縁まで
    届いている意匠——まさに縁いっぱいまで使うのが正しいアバター——で推定に失敗する。
    書き出したときの `--pad-bg` が分かっているなら、推定せずそれを使うほうが正確。
    """
    import numpy as np
    if bg is None:
        bg, cover = border_color(img)
        if cover < 0.70:
            return None, bg, False
    elif isinstance(bg, str):
        bg = hex_rgb(bg)
    arr = np.array(img.convert("RGB")).astype(int)
    d = np.abs(arr - np.array(bg)).sum(axis=-1)
    return d > tol, tuple(int(v) for v in bg), True


def mask_reach(mask):
    """真値の画素が中心からどこまで届いているか。ink_reach と同じ単位で返す。"""
    import numpy as np
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    h, w = mask.shape
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    half = w / 2.0
    dx, dy = np.abs(xs - cx), np.abs(ys - cy)
    return (float(np.hypot(dx, dy).max() / half), float(np.maximum(dx, dy).max() / half))


def _erosion_width(mask) -> float:
    """マスクを収縮させ、面積が15%を切るまでの回数から最小線幅をピクセルで返す。"""
    import numpy as np
    from PIL import Image, ImageFilter
    m = Image.fromarray((mask.astype("uint8")) * 255)
    total = np.array(m).sum() / 255
    if not total:
        return 0.0
    rounds, cur = 0, m
    while rounds < 40:
        cur = cur.filter(ImageFilter.MinFilter(3))
        rounds += 1
        if np.array(cur).sum() / 255 < total * 0.15:
            break
    return rounds * 2


def stroke_at(img, display_px: int, bg=None, ss: int = 8) -> float:
    """その表示寸法で、マークの最小線幅が何ピクセルに相当するかを返す。

    **表示寸法そのもので収縮させてはいけない。** 収縮は1回あたり1px（両側で2px）しか
    削れないので、20pxの画像を測ると最小値が2pxで頭打ちになり、「1px未満なら線が消える」
    という判定が構造上まったく発火しない。実際に20pxで消えている線を合格にしてしまう。

    そこで ss 倍に拡大した像で測り、最後に割り戻す。20px に対して ss=8 なら 0.25px
    刻みで分かるので、0.75px の線を「消える」と正しく言える。
    """
    from PIL import Image
    n = display_px * ss
    big = img.convert("RGB").resize((n, n), Image.LANCZOS)
    mask, _, solid = ink_mask_opaque(big, tol=40, bg=bg)
    if not solid or mask is None or not mask.any():
        return 0.0
    return _erosion_width(mask) / ss
