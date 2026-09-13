#!/usr/bin/env python3
"""preview_sns_icons.py — 書き出したアイコンを「各社が実際に切る形と、いちばん小さく出る寸法」で並べる。

プロフィールページの大きい表示で確認しても意味がない。上げたあとに「誰のアカウントか
分からない」となるのは、必ず一覧表示のほう——GitHubのコミット一覧20px、Slackのメッセージ
一覧20px、Xのタイムライン32px。そこを原寸で、ライトUIとダークUIの両方に並べる。

  python3 preview_sns_icons.py --dist dist --out preview

preview.html（人が見る）と preview.png（Read ツールで自分でも見る）の2つを出す。
"""
import argparse, base64, io, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platforms import ORDER, CROP_LABEL, resolve, filename
from snslib import contrast_ratio, ink_mask_opaque, mask_reach, stroke_at, die

RADIUS = {"circle": "50%", "squircle": "22.37%"}
# 一覧のほかに、実際によく目に入る中くらいの寸法も併記する（最小表示と同じなら省く）
MID = 48
# 拡大表示の横幅。倍率ではなく仕上がり幅を揃えることで、サービスごとに最小表示が
# 違ってもカードの高さが揃い、横に並べて比べられる
ZOOM_W = 120


def b64(img) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def metrics(img, px: int, pad_bg=None):
    """px に縮めたときのコントラストとマークの実寸を測る。

    pad_bg は verify と同じ約束で渡す。プレート型では None（外周から板の色を拾って
    中のマークだけを見る）、図案型では書き出しに使った地色。
    """
    import numpy as np
    from PIL import Image
    small = img.convert("RGB").resize((px, px), Image.LANCZOS)
    mask, bg, solid = ink_mask_opaque(small, tol=40, bg=pad_bg)
    if not solid or mask is None or not mask.any():
        return 1.0, 0.0
    arr = np.array(small).reshape(-1, 3)
    best = max(contrast_ratio(tuple(p), bg) for p in np.unique(arr, axis=0))
    reach = mask_reach(mask)
    return best, (reach[1] * px if reach else 0.0), stroke_at(img, px, pad_bg)


CSS = """
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 -apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;
 background:#f5f5f7;color:#111;padding:28px}
h1{font-size:18px;margin:0 0 6px}
.note{color:#666;font-size:12px;margin:0 0 22px;max-width:860px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,314px);gap:16px;align-items:start}
.card{background:#fff;border:1px solid #e3e3e8;border-radius:14px;padding:16px 18px}
.name{font-weight:700;font-size:15px}
.sub{font-size:11px;color:#8a8a92;margin-bottom:12px}
.sec{font-size:11px;color:#888;letter-spacing:.04em;margin:14px 0 6px}
.strip{display:flex;align-items:flex-end;gap:14px;padding:10px 12px;border-radius:8px;min-height:96px}
.strip.l{background:#fff;border:1px solid #e8e8ee}
.strip.d{background:#151618}
.av{display:block;overflow:hidden;flex:none}
.av img{width:100%;height:100%;display:block}
.zoom img{image-rendering:pixelated}
.cap{font-size:10px;color:#999;text-align:center;margin-top:4px;white-space:nowrap}
.dcap{color:#8a8d91}
.who{font-size:11px;color:#666;margin-top:2px}
.metric{font-size:12px;margin-top:12px;padding-top:10px;border-top:1px solid #eee;color:#444}
.bad{color:#c0392b;font-weight:700}
.warn{color:#b7791f;font-weight:700}
.good{color:#2d7a4f;font-weight:700}
"""


def verdict(c, eff, sw, px):
    if c < 3.0:
        return "bad", f"{c:.1f}:1 塗り潰しに見える"
    if sw < 1.0:
        return "bad", f"線幅 {sw:.2f}px 消える / コントラスト {c:.1f}:1"
    if sw < 1.4:
        return "warn", f"線幅 {sw:.2f}px ぎりぎり / マーク {eff:.0f}px"
    if eff < px * 0.45:
        return "warn", f"{c:.1f}:1 / マーク {eff:.0f}px 小さい"
    return "good", f"{c:.1f}:1 / 線幅 {sw:.2f}px / マーク {eff:.0f}px"


def avatar(data, size, crop, cls=""):
    return (f'<div class="av {cls}" style="width:{size}px;height:{size}px;'
            f'border-radius:{RADIUS[crop]}"><img src="{data}"></div>')


def build_html(cards):
    parts = [f"<style>{CSS}</style>",
             "<h1>SNSアイコン — 各社が実際に切る形と、いちばん小さく出る寸法</h1>",
             '<p class="note">左が原寸（その画面に出るのとまったく同じ大きさ）、'
             'その右は拡大表示で、縮小で何が消えたかを見るためのもの。'
             '<b>確認するのは一覧表示のほう。</b>プロフィールページの大きい表示で判断すると、'
             '上げてから「誰のアカウントか分からない」に気づくことになる。'
             '角丸と円の違いにも注目——同じ絵でも、角丸の社のほうがマークが大きく載る。</p>',
             '<div class="grid">']
    for c in cards:
        d = c["min_display"]
        zf = max(2, round(ZOOM_W / d))

        def col(size, cap, dark=False, cls=""):
            dc = " dcap" if dark else ""
            return (f'<div>{avatar(c["data"], size, c["crop"], cls)}'
                    f'<div class="cap{dc}">{cap}</div></div>')

        def strip(dark):
            out = [col(d, f"{d}px 原寸", dark), col(d * zf, f"{zf}倍", dark, "zoom")]
            if MID != d:
                out.append(col(MID, f"{MID}px", dark))
            return "".join(out)

        light, darkstrip = strip(False), strip(True)
        k, t = verdict(c["c"], c["eff"], c["sw"], d)
        parts.append(f"""
<div class="card">
  <div class="name">{c['label']}</div>
  <div class="sub">{c['file']} — {c['px']}px / {CROP_LABEL[c['crop']]} / {c['kb']:.0f} KB</div>
  <div class="sec">ライトUI</div>
  <div class="strip l">{light}</div>
  <div class="sec">ダークUI</div>
  <div class="strip d">{darkstrip}</div>
  <div class="who">{c['min_display']}px が出るのは: {c['where']}</div>
  <div class="metric">{c['min_display']}px での見え方 <span class="{k}">{t}</span></div>
</div>""")
    parts.append("</div>")
    return "<!doctype html><meta charset=utf-8>" + "".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dist", required=True, help="build_sns_icons.py の出力ディレクトリ")
    ap.add_argument("--out", default="preview", help="出力の接頭辞")
    a = ap.parse_args()
    from PIL import Image

    dist = pathlib.Path(a.dist)
    rp = dist / "build-report.json"
    meta = json.loads(rp.read_text()) if rp.is_file() else {}
    account = meta.get("github_account", "user")
    pad_bg = None if meta.get("full_bleed") else meta.get("pad_bg")
    built = [f["platform"] for f in meta.get("files", [])] or list(ORDER)

    cards = []
    for n in [x for x in ORDER if x in built]:
        spec = resolve(n, account)
        p = dist / filename(n, spec)
        if not p.is_file():
            p = p.with_suffix(".jpg")
        if not p.is_file():
            continue
        img = Image.open(p)
        c, eff, sw = metrics(img, spec["min_display"], pad_bg)
        cards.append({"label": spec["label"], "file": p.name, "px": spec["px"],
                      "crop": spec["crop"], "min_display": spec["min_display"],
                      "where": spec["min_display_where"], "kb": p.stat().st_size / 1024,
                      "data": b64(img), "c": c, "eff": eff, "sw": sw})
    if not cards:
        die(f"{dist} にアイコンが見つかりません。先に build_sns_icons.py を実行してください。")

    hp = pathlib.Path(f"{a.out}.html")
    hp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_text(build_html(cards), encoding="utf-8")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--force-color-profile=srgb"])
            pg = b.new_page(viewport={"width": min(346 * len(cards) + 60, 1450), "height": 700},
                            device_scale_factor=2)
            pg.goto(hp.resolve().as_uri())
            pg.wait_for_timeout(250)
            pg.screenshot(path=f"{a.out}.png", full_page=True)
            b.close()
        shot = f"{a.out}.png"
    except Exception as e:
        shot = None
        print(f"[preview] PNGの書き出しに失敗しました（HTMLは出ています）: {e}", file=sys.stderr)

    print(f"\n[preview] {hp}  ← 人に見せる")
    if shot:
        print(f"[preview] {shot}  ← Read ツールで自分でも見る")
    for c in cards:
        print(f"  {c['label']:<22} {c['min_display']:>3}px  コントラスト {c['c']:.1f}:1  "
              f"線幅 {c['sw']:.2f}px  マーク実寸 {c['eff']:.0f}px")
    print()


if __name__ == "__main__":
    main()
