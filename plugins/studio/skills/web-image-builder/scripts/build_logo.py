#!/usr/bin/env python3
"""
build_logo.py - ロゴロックアップ(アイコン+社名)を SVG と透過PNG で生成する。

build_image.py との違いは3つ。ロゴは性質が逆なので別スクリプトにしてある。
  1. キャンバスを中身に合わせる（他の画像は中身をキャンバスに合わせる）
  2. 背景が透過（どんな地色にも載る必要がある）
  3. SVGが主成果物。ヘッダー・ヒーロー・フッターは全部Webなので、
     ラスタライズする理由が無い。SVGなら任意サイズ・任意DPRで常に鮮明。

  SVGの文字は fontTools でアウトライン(パス)に変換する。
  Webフォントの読み込みを待たないので表示時にガタつかず、
  閲覧環境のフォント有無にも一切依存しない。デザイナーが
  ロゴを「アウトライン化」して納品するのと同じ状態。

使い方:
  python3 build_logo.py --layout h --icon icon.svg --title "占星術アステリア" \
      --height 40 --out logo_h
  python3 build_logo.py --layout v --icon icon.svg --title "占星術アステリア" \
      --ruby "A S T E R I A" --height 120 --out logo_v

  --out は拡張子なしで渡す。logo_h.svg / logo_h.png / logo_h@2x.png ... が出る。
"""
from __future__ import annotations
import argparse, base64, math, pathlib, re, sys

def die(msg: str):
    print(f"\n[build_logo] エラー: {msg}\n", file=sys.stderr); sys.exit(1)

# ---------------------------------------------------------------- font
def load_face(path: str):
    from fontTools.ttLib import TTFont, TTCollection
    p = pathlib.Path(path).expanduser()
    if not p.is_file(): die(f"フォントが見つかりません: {p}")
    if p.suffix.lower() in (".ttc", ".otc"):
        # コレクションは先頭フェイスを使う。日本語フォントで先頭がJPでない場合は
        # 字形が中国語になるので、単体のotf/ttfを切り出して渡すほうが安全。
        return TTCollection(str(p)).fonts[0]
    return TTFont(str(p), fontNumber=0)

def text_to_paths(face, text: str, size: float, tracking: float = 0.0):
    """文字列を SVG パス片のリストに変換し、総送り幅を返す。

    カーニング(GPOS)は適用しない。日本語は全角送りが基本で影響が無く、
    ロゴは字間を意図的に調整するのが普通なので --tracking で足りる。
    """
    from fontTools.pens.svgPathPen import SVGPathPen
    upem = face["head"].unitsPerEm
    s = size / upem
    gs = face.getGlyphSet()
    cmap = face.getBestCmap()
    out, x = [], 0.0
    missing = []
    for ch in text:
        if ch == " ":
            x += size * 0.32 + tracking; continue
        gname = cmap.get(ord(ch))
        if gname is None:
            missing.append(ch); continue
        g = gs[gname]
        pen = SVGPathPen(gs)
        g.draw(pen)
        d = pen.getCommands()
        if d:
            out.append((d, x, s))
        x += g.width * s + tracking
    if missing:
        die("フォントに以下の文字のグリフがありません。ロゴが欠けるので停止します:\n"
            f"        {' '.join(sorted(set(missing)))}")
    if out:
        x -= tracking      # 末尾のトラッキングは幅に含めない
    return out, x

def font_metrics(face, size: float):
    """ベースラインからの上端/下端。ロックアップの縦位置合わせに使う。"""
    upem = face["head"].unitsPerEm
    s = size / upem
    try:
        os2 = face["OS/2"]
        asc, desc = os2.sTypoAscender, os2.sTypoDescender
    except Exception:
        asc, desc = face["hhea"].ascent, face["hhea"].descent
    return asc * s, abs(desc * s)

def cap_height(face, size: float) -> float:
    """実際のインクの高さ。ロゴの光学的な高さ合わせはここを基準にする。"""
    upem = face["head"].unitsPerEm
    try:
        ch = face["OS/2"].sCapHeight
        if ch: return ch * size / upem
    except Exception:
        pass
    return size * 0.72

# ---------------------------------------------------------------- icon
def read_icon(path: str):
    """SVGなら中身とviewBoxを返す。ラスタなら data URI にして返す。"""
    p = pathlib.Path(path).expanduser()
    if not p.is_file(): die(f"アイコンが見つかりません: {p}")
    if p.suffix.lower() == ".svg":
        src = p.read_text(encoding="utf-8")
        m = re.search(r'viewBox\s*=\s*["\']([\d.\-\s]+)["\']', src)
        if m:
            vb = [float(v) for v in m.group(1).split()]
        else:
            w = re.search(r'\swidth\s*=\s*["\']([\d.]+)', src)
            h = re.search(r'\sheight\s*=\s*["\']([\d.]+)', src)
            if not (w and h): die("アイコンSVGに viewBox も width/height もありません")
            vb = [0, 0, float(w.group(1)), float(h.group(1))]
        inner = re.sub(r'^.*?<svg[^>]*>', '', src, flags=re.S)
        inner = re.sub(r'</svg>\s*$', '', inner, flags=re.S)
        return {"kind": "svg", "inner": inner, "vb": vb}
    b = base64.b64encode(p.read_bytes()).decode()
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    from PIL import Image
    with Image.open(p) as im: w, h = im.size
    print(f"[build_logo] 注意: アイコンが {p.suffix} です。SVGにすると"
          f"任意サイズで無劣化になります。", file=sys.stderr)
    return {"kind": "raster", "uri": f"data:{mime};base64,{b}", "vb": [0, 0, w, h]}

# ---------------------------------------------------------------- layout
def build(cfg: dict) -> tuple[str, dict]:
    """ロックアップを組んで SVG 文字列と寸法情報を返す。

    基準は --height（ロゴ全体の高さ）。そこから各要素を比率で決めるので、
    どの高さで出しても同じ見た目になる。
    """
    H = cfg["height"]
    face = load_face(cfg["font"])
    icon = read_icon(cfg["icon"]) if cfg.get("icon") else None
    pad = H * cfg["pad"]
    color = cfg["color"]
    ic_color = cfg.get("icon_color")

    if cfg["layout"] == "h":
        # 横型: アイコン左 / テキスト右。アイコンは全高、文字はキャップ高で光学的に揃える
        icon_h  = H
        title_s = H * cfg["title_ratio_h"]
        sub_s   = H * cfg["sub_ratio_h"]
        gap     = H * cfg["gap_h"]

        t_paths, t_w = text_to_paths(face, cfg["title"], title_s, H * cfg["tracking"])
        cap = cap_height(face, title_s)
        s_paths, s_w = ([], 0.0)
        if cfg.get("sub"):
            s_paths, s_w = text_to_paths(face, cfg["sub"], sub_s, H * cfg["tracking_sub"])

        icon_w = icon_h * (icon["vb"][2] / icon["vb"][3]) if icon else 0
        text_w = max(t_w, s_w)
        W = icon_w + (gap if icon else 0) + text_w

        if s_paths:
            block = cap + H * cfg["line_gap_h"] + cap_height(face, sub_s)
            t_base = (H - block) / 2 + cap
            s_base = t_base + H * cfg["line_gap_h"] + cap_height(face, sub_s)
        else:
            t_base = (H + cap) / 2
            s_base = 0
        tx = icon_w + (gap if icon else 0)
        groups = [(t_paths, tx, t_base), (s_paths, tx, s_base)]
        icon_pos = (0.0, 0.0, icon_w, icon_h)

    else:
        # 縦型: アイコン上 / タイトル / ルビ。中央揃え
        icon_h  = H * cfg["icon_ratio_v"]
        title_s = H * cfg["title_ratio_v"]
        ruby_s  = H * cfg["ruby_ratio_v"]
        gap     = H * cfg["gap_v"]

        t_paths, t_w = text_to_paths(face, cfg["title"], title_s, H * cfg["tracking"])
        cap = cap_height(face, title_s)
        r_paths, r_w = ([], 0.0)
        if cfg.get("ruby"):
            r_paths, r_w = text_to_paths(face, cfg["ruby"], ruby_s, H * cfg["tracking_ruby"])
        r_cap = cap_height(face, ruby_s) if r_paths else 0

        icon_w = icon_h * (icon["vb"][2] / icon["vb"][3]) if icon else 0
        W = max(icon_w, t_w, r_w)
        y = icon_h + (gap if icon else 0)
        t_base = y + cap
        r_base = t_base + H * cfg["line_gap_v"] + r_cap if r_paths else 0
        groups = [(t_paths, (W - t_w) / 2, t_base), (r_paths, (W - r_w) / 2, r_base)]
        icon_pos = ((W - icon_w) / 2, 0.0, icon_w, icon_h)
        H = (r_base if r_paths else t_base) + (r_cap * 0.0)   # インク下端で締める

    VW, VH = W + pad * 2, H + pad * 2
    parts = []
    if icon:
        ix, iy, iw, ih = icon_pos
        ix += pad; iy += pad
        if icon["kind"] == "svg":
            vb = icon["vb"]
            sx, sy = iw / vb[2], ih / vb[3]
            # color も一緒に指定する。単色アイコンは fill="currentColor" で
            # 書かれていることが多く、fill属性だけでは currentColor が解決されない。
            fill = f' fill="{ic_color}" color="{ic_color}"' if ic_color else ""
            parts.append(f'<g transform="translate({ix:.3f} {iy:.3f}) scale({sx:.5f} {sy:.5f}) '
                         f'translate({-vb[0]:.3f} {-vb[1]:.3f})"{fill}>{icon["inner"]}</g>')
        else:
            parts.append(f'<image x="{ix:.3f}" y="{iy:.3f}" width="{iw:.3f}" height="{ih:.3f}" '
                         f'href="{icon["uri"]}"/>')
    for paths, ox, base in groups:
        if not paths: continue
        g = []
        for d, gx, s in paths:
            g.append(f'<path transform="translate({ox+pad+gx:.3f} {base+pad:.3f}) '
                     f'scale({s:.6f} {-s:.6f})" d="{d}"/>')
        parts.append(f'<g fill="{color}">{"".join(g)}</g>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{VW:.2f}" height="{VH:.2f}" '
           f'viewBox="0 0 {VW:.3f} {VH:.3f}" role="img" aria-label="{cfg["title"]}">'
           f'<title>{cfg["title"]}</title>{"".join(parts)}</svg>')
    return svg, {"w": VW, "h": VH, "ratio": VW / VH}


# ---------------------------------------------------------------- png
def svg_to_png(svg_path: str, out: str, height: int):
    """SVGをChromiumで透過PNGに焼く。ロゴの表示高さで指定する。"""
    from playwright.sync_api import sync_playwright
    import tempfile
    src = pathlib.Path(svg_path).read_text(encoding="utf-8")
    html = (f'<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:transparent}}'
            f'#w{{display:inline-block;line-height:0}} svg{{height:{height}px;width:auto;display:block}}'
            f'</style><div id="w">{src}</div>')
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "l.html"; p.write_text(html, encoding="utf-8")
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
            pg = b.new_page(viewport={"width": 2000, "height": 800}, device_scale_factor=1)
            pg.goto(p.resolve().as_uri()); pg.wait_for_timeout(200)
            pg.locator("#w").screenshot(path=out, omit_background=True)
            b.close()
    from PIL import Image
    with Image.open(out) as im: return im.size


DEFAULTS = dict(
    pad=0.0,
    # 横型: 文字はロゴ高の何倍か
    title_ratio_h=0.52, sub_ratio_h=0.26, gap_h=0.26, line_gap_h=0.30,
    # 縦型
    icon_ratio_v=0.46, title_ratio_v=0.26, ruby_ratio_v=0.105,
    gap_v=0.13, line_gap_v=0.13,
    tracking=0.0, tracking_sub=0.0, tracking_ruby=0.055,
)

def main():
    ap = argparse.ArgumentParser(description="ロゴロックアップを SVG と透過PNG で生成")
    ap.add_argument("--layout", choices=("h", "v"), required=True,
                    help="h=横型(アイコン左+テキスト右) / v=縦型(アイコン上+テキスト下)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--sub", default="", help="横型のタグライン(任意)")
    ap.add_argument("--ruby", default="", help="縦型のルビ/欧文表記(任意)")
    ap.add_argument("--icon", help="アイコン。SVG推奨")
    ap.add_argument("--icon-color", help="アイコンのfillを上書き(単色アイコン向け)")
    ap.add_argument("--font", required=True, help="TTF/OTF/TTC。ロゴなので必ず明示する")
    ap.add_argument("--color", default="#111111")
    ap.add_argument("--height", type=float, default=40, help="SVGの基準高さ")
    ap.add_argument("--pad", type=float, default=0.0, help="余白をロゴ高の比率で(既定0=密着)")
    ap.add_argument("--tracking", type=float, default=0.0, help="字間をロゴ高の比率で")
    ap.add_argument("--png-heights", default="",
                    help="PNGを出す表示高さ。例 40,80,120 (@1x,@2x,@3x相当)")
    ap.add_argument("--out", required=True, help="拡張子なしの出力名")
    a = ap.parse_args()

    cfg = dict(DEFAULTS)
    cfg.update(layout=a.layout, title=a.title, sub=a.sub, ruby=a.ruby, icon=a.icon,
               icon_color=a.icon_color, font=a.font, color=a.color, height=a.height,
               pad=a.pad, tracking=a.tracking)
    svg, dim = build(cfg)
    svg_path = f"{a.out}.svg"
    pathlib.Path(svg_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(svg_path).write_text(svg, encoding="utf-8")

    print(f"\n  {svg_path}  {dim['w']:.0f}x{dim['h']:.0f}  縦横比 {dim['ratio']:.3f}:1")
    print("  ↑ これが主成果物。ヘッダー・ヒーロー・フッターはこれを使う"
          "（任意サイズ・任意DPRで常に鮮明、文字はパス化済み）")

    if a.png_heights:
        print("\n  ラスタが必要な場面用のPNG（透過）:")
        for i, hs in enumerate(a.png_heights.split(",")):
            h = int(hs.strip())
            out = f"{a.out}.png" if i == 0 else f"{a.out}@{h/int(a.png_heights.split(',')[0].strip()):.0f}x.png"
            w, hh = svg_to_png(svg_path, out, h)
            print(f"    {out:28} {w}x{hh}")

if __name__ == "__main__":
    main()
