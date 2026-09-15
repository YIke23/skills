#!/usr/bin/env python3
"""preview_icons.py — 候補SVGを「実際に使われる寸法と切り抜き」で並べて見せる。

アイコンの良し悪しは 512px のプレビューでは判断できない。判断できるのは
タブの16px、ホーム画面の角丸、Androidランチャーの円形マスク。それを一枚にまとめる。

  python3 preview_icons.py --svg a.svg b.svg c.svg --out preview --labels "A案,B案,C案"

preview.html（人が見る）と preview.png（あなたがReadで見る）の2つを出す。
"""
import argparse, base64, io, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from iconlib import Renderer, read_svg, outline_text, optimize_svg, contrast_ratio, die

SIZES = [16, 32, 48, 64]

def b64(img):
    buf = io.BytesIO(); img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def max_contrast(img, bg):
    import numpy as np
    from PIL import Image
    flat = Image.new("RGB", img.size, bg); flat.paste(img, mask=img.getchannel("A"))
    arr = np.array(flat).reshape(-1, 3)
    uniq = np.unique(arr, axis=0)
    return max(contrast_ratio(tuple(p), bg) for p in uniq)

def card(label, svg, font):
    svg = optimize_svg(outline_text(svg, font))
    data = {"label": label}
    with Renderer(svg, "light") as r:
        small = {s: b64(r.render(s)) for s in SIZES}
        raw16 = r.render(16)
        data["home"] = b64(r.render(180))
        data["big"] = b64(r.render(256))
    with Renderer(svg, "dark") as r:
        small_d = {s: b64(r.render(s)) for s in SIZES}
        raw16d = r.render(16)
    data["light"], data["dark"] = small, small_d
    data["c_light"] = max_contrast(raw16, (255, 255, 255))
    data["c_dark"] = max_contrast(raw16d, (32, 33, 36))
    return data

CSS = """
:root{color-scheme:light dark;--pad:#dddddd}
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 -apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;
 background:#f5f5f7;color:#111;padding:28px}
h1{font-size:18px;margin:0 0 6px}
.note{color:#666;font-size:12px;margin:0 0 22px}
.grid{display:flex;gap:18px;flex-wrap:wrap}
.card{background:#fff;border:1px solid #e3e3e8;border-radius:14px;padding:16px 18px;width:322px}
.name{font-weight:700;font-size:15px;margin-bottom:12px}
.sec{font-size:11px;color:#888;letter-spacing:.04em;margin:14px 0 6px;text-transform:uppercase}
.strip{display:flex;align-items:center;gap:12px;padding:8px 10px;border-radius:8px}
.strip.l{background:#fff;border:1px solid #e8e8ee}
.strip.d{background:#202124}
.strip img{display:block}
.zoom{image-rendering:pixelated;border:1px solid rgba(128,128,128,.35)}
.row{display:flex;gap:14px;align-items:flex-end}
.cap{font-size:10px;color:#999;text-align:center;margin-top:3px}
.masks{display:flex;gap:14px;align-items:center;margin-top:4px}
.sq{width:72px;height:72px;border-radius:22.37%;overflow:hidden;background:var(--pad)}
.ci{width:72px;height:72px;border-radius:50%;overflow:hidden;background:var(--pad)}
.sq img,.ci img{width:100%;height:100%;display:block}
.metric{font-size:12px;margin-top:12px;padding-top:10px;border-top:1px solid #eee;color:#444}
.bad{color:#c0392b;font-weight:700}
.warn{color:#b7791f;font-weight:700}
.good{color:#2d7a4f;font-weight:700}
"""

def verdict(v):
    if v < 3.0: return "bad", f"{v:.1f}:1 見えない"
    if v < 4.5: return "warn", f"{v:.1f}:1 薄い"
    return "good", f"{v:.1f}:1"

def build_html(cards, pad_bg="#dddddd"):
    parts = [f"<style>{CSS}</style><style>:root{{--pad:{pad_bg}}}</style>",
             "<h1>アイコン候補 — 実際に使われる寸法と切り抜き</h1>",
             '<p class="note">上段は原寸（タブに出るのとまったく同じ大きさ）。'
             'その右は4倍拡大で、縮小でどこが潰れたかを見るためのもの。'
             '16pxで意味が読み取れない案は、どれだけ大きい版が綺麗でも採用できない。'
             '下段の角丸/円形の地色は --pad-bg で指定した色。</p>',
             '<div class="grid">']
    for c in cards:
        row_l = "".join(f'<div><img src="{c["light"][s]}" width="{s}"><div class="cap">{s}</div></div>'
                        for s in SIZES)
        row_d = "".join(f'<div><img src="{c["dark"][s]}" width="{s}"><div class="cap">{s}</div></div>'
                        for s in SIZES)
        zl = f'<img class="zoom" src="{c["light"][16]}" width="64">'
        zd = f'<img class="zoom" src="{c["dark"][16]}" width="64">'
        kl, tl = verdict(c["c_light"]); kd, td = verdict(c["c_dark"])
        parts.append(f"""
<div class="card">
  <div class="name">{c['label']}</div>
  <div class="sec">明るいタブ（原寸 / 16pxを4倍）</div>
  <div class="strip l"><div class="row">{row_l}</div>{zl}</div>
  <div class="sec">暗いタブ（原寸 / 16pxを4倍）</div>
  <div class="strip d"><div class="row">{row_d}</div>{zd}</div>
  <div class="sec">ホーム画面のマスク</div>
  <div class="masks">
    <div><div class="sq"><img src="{c['home']}"></div><div class="cap">iOS 角丸</div></div>
    <div><div class="ci"><img src="{c['home']}"></div><div class="cap">Android 円形</div></div>
    <div><img src="{c['big']}" width="72" height="72"><div class="cap">原画</div></div>
  </div>
  <div class="metric">16pxコントラスト 明:<span class="{kl}">{tl}</span> /
   暗:<span class="{kd}">{td}</span></div>
</div>""")
    parts.append("</div>")
    return "<!doctype html><meta charset=utf-8>" + "".join(parts)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg", nargs="+", required=True)
    ap.add_argument("--labels", default="", help="カンマ区切り。省略時はファイル名")
    ap.add_argument("--out", default="preview", help="出力の接頭辞")
    ap.add_argument("--font", default=None)
    ap.add_argument("--pad-bg", default="#dddddd",
                    help="透過の意匠を角丸/円形で見るときの地色。build_icons.py と同じ値を渡す")
    a = ap.parse_args()
    labels = [x.strip() for x in a.labels.split(",")] if a.labels else []
    cards = []
    for i, p in enumerate(a.svg):
        lab = labels[i] if i < len(labels) else pathlib.Path(p).stem
        cards.append(card(lab, read_svg(p), a.font))
    html = build_html(cards, a.pad_bg)
    hp = pathlib.Path(f"{a.out}.html"); hp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--force-color-profile=srgb"])
        pg = b.new_page(viewport={"width": min(360 * len(cards) + 60, 1420), "height": 640},
                        device_scale_factor=2)
        pg.goto(hp.resolve().as_uri()); pg.wait_for_timeout(250)
        pg.screenshot(path=f"{a.out}.png", full_page=True)
        b.close()
    print(f"\n[preview_icons] {hp}  ← 人に見せる")
    print(f"[preview_icons] {a.out}.png  ← Read ツールで自分でも見る")
    for c in cards:
        print(f"  {c['label']:<16} 16pxコントラスト 明 {c['c_light']:.1f}:1 / 暗 {c['c_dark']:.1f}:1")
    print()

if __name__ == "__main__":
    main()
