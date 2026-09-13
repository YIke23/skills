#!/usr/bin/env python3
"""verify_icons.py — 書き出したアイコン一式が、各面の制約を実際に満たすか機械的に検査する。

「16pxで潰れる」「apple-touch-iconが黒くなる」「Androidでロゴが欠ける」
「App Storeでアルファチャンネルを拒否される」は、どれも納品後に発覚すると痛い。
どれも数値で判定できるので、ここで止める。

  python3 verify_icons.py --dist dist [--strict] [--json result.json]

終了コード: 0=問題なし / 1=警告あり / 2=不適合あり
"""
import argparse, json, math, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from iconlib import contrast_ratio, hex_rgb, border_bg

# 実測に基づく実務的な目安。規格ではないので、超えたら「意匠を疑え」の合図として使う。
SIZE_BUDGET = {                      # (適正上限, 警告ライン) bytes
    "web/icon.svg":            (1_500,   3_000),
    "web/favicon.ico":         (3_500,   5_000),
    "web/apple-touch-icon.png":(5_000,  15_000),
    "web/icon-192.png":        (5_000,  15_000),
    "web/icon-512.png":        (15_000, 30_000),
    "web/icon-mask.png":       (15_000, 30_000),
}
TAB_BG = {"light": (255, 255, 255), "dark": (32, 33, 36)}

class Report:
    def __init__(self):
        self.rows = []
    def add(self, level, name, detail):
        self.rows.append({"level": level, "check": name, "detail": detail})
    def ok(self, n, d=""):   self.add("PASS", n, d)
    def warn(self, n, d):    self.add("WARN", n, d)
    def fail(self, n, d):    self.add("FAIL", n, d)
    def worst(self):
        levels = {r["level"] for r in self.rows}
        return 2 if "FAIL" in levels else (1 if "WARN" in levels else 0)

def load(p):
    from PIL import Image
    return Image.open(p)

def ink_mask(img, bg=None, tol=28):
    """地色と違うピクセルを True にする。不透明画像でもマークの範囲が取れる。

    bg を渡さない場合は画像の外周から地色を推定する。全面塗りのプレートは
    地色側に回るので、切り抜き判定の対象が「中のマーク」だけになる。
    """
    import numpy as np
    arr = np.array(img.convert("RGBA")).astype(int)
    alpha = arr[..., 3]
    if bg is None:
        return alpha > 40
    ref = np.array(hex_rgb(bg) if isinstance(bg, str) else bg)
    d = np.abs(arr[..., :3] - ref).sum(axis=-1)
    return (alpha > 40) & (d > tol)


def ink_of(img, rep=None, label=""):
    """外周から地色を推定してインクを取る。地色が単色でなければ (mask, False) を返す。"""
    bg, cover = border_bg(img)
    if cover < 0.70:
        if rep:
            rep.warn(label, "地色が単色でないため、切り抜きの安全域を自動判定できません。"
                            "preview_icons.py の円形/角丸プレビューで目視してください")
        return ink_mask(img, None), False
    return ink_mask(img, bg), True

def frac_outside_circle(mask, r_frac):
    import numpy as np
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cy = cx = (w - 1) / 2
    rr = np.hypot(xx - cx, yy - cy)
    out = mask & (rr > r_frac * w)
    tot = mask.sum()
    return (out.sum() / tot) if tot else 0.0

def frac_outside_square(mask, side_frac):
    import numpy as np
    h, w = mask.shape
    m = int(round(w * (1 - side_frac) / 2))
    inner = np.zeros_like(mask)
    inner[m:h - m, m:w - m] = True
    out = mask & ~inner
    tot = mask.sum()
    return (out.sum() / tot) if tot else 0.0

def has_alpha(img) -> bool:
    """半透明ピクセルが実在するか。パレットPNGでも tRNS が無ければ透過は無い。"""
    if img.mode in ("RGB", "L"):
        return False
    if img.mode == "P" and "transparency" not in img.info:
        return False
    import numpy as np
    return bool((np.array(img.convert("RGBA"))[..., 3] < 255).any())


def has_alpha_channel(img) -> bool:
    """アルファチャンネルそのものを持つか。App Store はこの有無で弾く。"""
    return img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info

def render_svg(svg_text, px, scheme="light"):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from iconlib import Renderer
    with Renderer(svg_text, color_scheme=scheme) as r:
        return r.render(px)

def legibility(svg_text, rep):
    """16px で実際に描いて、見えるか / 細すぎないかを測る。

    16x16 は 256 ピクセルしかない。ここで生き残らない意匠は、どれだけ大きい版が
    綺麗でもタブの中では見えない。
    """
    import numpy as np
    from PIL import Image, ImageFilter
    for scheme, bg in (("light", TAB_BG["light"]), ("dark", TAB_BG["dark"])):
        img = render_svg(svg_text, 16, scheme)
        flat = Image.new("RGB", img.size, bg)
        flat.paste(img, mask=img.getchannel("A"))
        arr = np.array(flat).reshape(-1, 3)
        ratios = np.array([contrast_ratio(tuple(p), bg) for p in arr])
        best, strong = ratios.max(), float((ratios >= 3.0).mean())
        tag = "明るいタブ" if scheme == "light" else "暗いタブ"
        if best < 3.0:
            rep.fail(f"16px可読性/{tag}",
                     f"最大コントラスト {best:.1f}:1 — 背景に溶けて見えません（WCAG非文字の下限は3:1）")
        elif best < 4.5:
            rep.warn(f"16px可読性/{tag}", f"最大コントラスト {best:.1f}:1 — 薄い。地色を濃くするか反転版を用意")
        elif strong < 0.06:
            rep.warn(f"16px可読性/{tag}",
                     f"はっきり見えるピクセルが {strong*100:.1f}% しかない — 線が細いか要素が小さすぎる")
        else:
            rep.ok(f"16px可読性/{tag}", f"最大 {best:.1f}:1 / 有効面積 {strong*100:.0f}%")

    big = render_svg(svg_text, 64, "light")
    m = Image.fromarray((np.array(big.getchannel("A")) > 120).astype("uint8") * 255)
    total = np.array(m).sum() / 255
    if total:
        rounds, cur = 0, m
        while rounds < 12:
            cur = cur.filter(ImageFilter.MinFilter(3))
            rounds += 1
            if np.array(cur).sum() / 255 < total * 0.15:
                break
        thickness_16 = (rounds * 2) / 4.0     # 64px上の太さ → 16px換算
        if thickness_16 < 0.75:
            rep.fail("最小線幅", f"16px換算で約 {thickness_16:.2f}px — 縮小で消えます。"
                                 "512キャンバスなら線・要素を32単位以上に")
        elif thickness_16 < 1.0:
            rep.warn("最小線幅", f"16px換算で約 {thickness_16:.2f}px — ぎりぎり。1px（=512上で32）を目標に")
        else:
            rep.ok("最小線幅", f"16px換算で約 {thickness_16:.2f}px")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dist", required=True)
    ap.add_argument("--strict", action="store_true", help="警告も不適合として扱う")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    dist = pathlib.Path(a.dist)
    rep = Report()
    rp = dist / "build-report.json"
    meta = json.loads(rp.read_text()) if rp.is_file() else {}
    pad_bg = meta.get("pad_bg", "#ffffff")

    def need(rel, px=None, opaque=None, no_alpha=False):
        p = dist / rel
        if not p.is_file():
            rep.fail(rel, "ファイルがありません")
            return None
        img = load(p)
        if px and img.size != (px, px):
            rep.fail(rel, f"寸法が {img.size[0]}x{img.size[1]} — {px}x{px} でなければなりません")
            return img
        if no_alpha and has_alpha_channel(img):
            rep.fail(rel, f"アルファチャンネルがあります（mode={img.mode}）— App Store は透過を拒否します")
            return img
        if opaque and has_alpha(img):
            rep.fail(rel, "半透明/透過ピクセルがあります — iOSはここを黒く塗ります")
            return img
        return img

    # ---------------------------------------------------------------- SVG
    sp = dist / "web" / "icon.svg"
    svg_text = None
    if sp.is_file():
        svg_text = sp.read_text(encoding="utf-8")
        probs = []
        if "viewBox" not in svg_text: probs.append("viewBox が無い（寸法が決まらず表示されない）")
        if "<text" in svg_text:       probs.append("<text> が残っている（閲覧者の端末でフォントが解決されない）")
        if "<image" in svg_text:      probs.append("<image> でラスタが埋まっている")
        if "<script" in svg_text:     probs.append("<script> がある（favicon文脈では実行されない）")
        if re.search(r'(href|src)\s*=\s*["\']https?://', svg_text):
            probs.append("外部リソースを参照している（読み込まれない）")
        if probs:
            for x in probs: rep.fail("web/icon.svg", x)
        else:
            rep.ok("web/icon.svg", "viewBox あり / 自己完結")
        if "prefers-color-scheme" not in svg_text:
            rep.warn("web/icon.svg", "ダークモード指定が無い。暗いタブでも読めるか下の可読性チェックで確認")
    else:
        rep.fail("web/icon.svg", "ファイルがありません")

    # ---------------------------------------------------------------- PNG群
    need("web/apple-touch-icon.png", 180, opaque=True)
    need("web/icon-192.png", 192)
    need("web/icon-512.png", 512)
    mask = need("web/icon-mask.png", 512, opaque=True)
    if mask is not None and mask.size == (512, 512):
        m, solid = ink_of(mask, rep, "maskable 安全域")
        out_safe = frac_outside_circle(m, 0.40)
        out_clip = frac_outside_circle(m, 0.50)
        # 地色を特定できていないときは、プレート全体をインクとして数えてしまうので断定しない
        hard = rep.fail if solid else rep.warn
        if out_clip > 0.001:
            hard("maskable 安全域", f"インクの {out_clip*100:.1f}% が直径512の円の外 — "
                                    "円形マスクの端末で確実に欠けます")
        elif out_safe > 0.02:
            rep.warn("maskable 安全域", f"インクの {out_safe*100:.1f}% が保証域（直径409の円）の外 — "
                                        "ランチャーの形によっては欠けます")
        else:
            rep.ok("maskable 安全域", f"保証域（直径409の円）の外は {out_safe*100:.1f}%")

    ico = dist / "web" / "favicon.ico"
    if ico.is_file():
        try:
            sizes = sorted(load(ico).info.get("sizes", []))
            rep.ok("web/favicon.ico", f"収録サイズ {', '.join(f'{w}x{h}' for w, h in sizes)}")
        except Exception as e:
            rep.fail("web/favicon.ico", f"読めません: {e}")
    else:
        rep.fail("web/favicon.ico", "ファイルがありません")

    # ---------------------------------------------------------------- manifest
    mp = dist / "web" / "manifest.webmanifest"
    if mp.is_file():
        try:
            mj = json.loads(mp.read_text())
        except Exception as e:
            rep.fail("manifest", f"JSONとして壊れています: {e}"); mj = None
        if mj:
            icons = mj.get("icons", [])
            missing = [i["src"] for i in icons
                       if not (dist / "web" / pathlib.Path(i["src"]).name).is_file()]
            if missing:
                rep.fail("manifest", f"参照先が存在しません: {', '.join(missing)}")
            elif not any("maskable" in (i.get("purpose") or "") for i in icons):
                rep.warn("manifest", "maskable のアイコンがありません。Androidのホーム画面で余白だらけになります")
            elif any(set((i.get("purpose") or "any").split()) >= {"any", "maskable"} for i in icons):
                rep.warn("manifest", "1つのアイコンに any と maskable を兼任させています。"
                                     "maskableは余白込みなので、any として使うとロゴが小さく見えます")
            else:
                rep.ok("manifest", f"アイコン {len(icons)} 件 / maskable 分離済み")
            for k in ("name", "start_url"):
                if not mj.get(k): rep.warn("manifest", f"{k} が空です")

    # ---------------------------------------------------------------- 面ごと
    ios = dist / "ios" / "AppIcon-1024.png"
    if ios.is_file():
        need("ios/AppIcon-1024.png", 1024, no_alpha=True)
        if not has_alpha_channel(load(ios)):
            rep.ok("ios/AppIcon-1024.png", "1024x1024 / アルファ無し（App Store 提出可）")

    fg = dist / "android" / "res" / "drawable" / "ic_launcher_foreground.png"
    if fg.is_file():
        img = need("android/res/drawable/ic_launcher_foreground.png", 432)
        if img is not None and img.size == (432, 432):
            m = ink_mask(img)
            o = frac_outside_square(m, 66 / 108)
            if o > 0.02:
                rep.fail("Android 安全域", f"前景のインクの {o*100:.1f}% が 66dp の安全域の外 — "
                                            "端末のマスク形状によっては欠けます")
            else:
                rep.ok("Android 安全域", "前景は 66dp の安全域に収まっています")
    for rel, px in (("android/play-store-512.png", 512),):
        if (dist / rel).is_file(): need(rel, px)

    # ---------------------------------------------------------------- 容量
    for rel, (good, limit) in SIZE_BUDGET.items():
        p = dist / rel
        if not p.is_file(): continue
        n = p.stat().st_size
        if n > limit:
            rep.warn("容量/" + rel, f"{n/1024:.1f} KB — 目安 {limit/1024:.0f} KB 超。"
                                     "パス数過多・ラスタ埋め込み・写真的な意匠を疑う")
        elif n > good:
            rep.ok("容量/" + rel, f"{n/1024:.1f} KB（許容範囲）")
        else:
            rep.ok("容量/" + rel, f"{n/1024:.1f} KB")
    web_total = sum(p.stat().st_size for p in (dist / "web").glob("*") if p.is_file())
    if web_total:
        lvl = rep.warn if web_total > 60_000 else rep.ok
        lvl("web一式の合計", f"{web_total/1024:.1f} KB" + (" — 60KB超。意匠がアイコン向きでない可能性" if web_total > 60_000 else ""))

    # ---------------------------------------------------------------- 可読性
    if svg_text:
        legibility(svg_text, rep)

    # ---------------------------------------------------------------- 出力
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    rep.rows.sort(key=lambda r: order[r["level"]])
    mark = {"PASS": "  OK ", "WARN": " WARN", "FAIL": " FAIL"}
    print()
    for r in rep.rows:
        print(f"{mark[r['level']]}  {r['check']:<32} {r['detail']}")
    n_f = sum(1 for r in rep.rows if r["level"] == "FAIL")
    n_w = sum(1 for r in rep.rows if r["level"] == "WARN")
    print(f"\n[verify_icons] 不適合 {n_f} / 警告 {n_w} / 合格 {len(rep.rows)-n_f-n_w}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(
            {"fail": n_f, "warn": n_w, "rows": rep.rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    code = rep.worst()
    if a.strict and code == 1: code = 2
    if code == 0: print("[verify_icons] 全ての面の制約を満たしています。\n")
    else: print("[verify_icons] 上の項目を直してから納品してください。\n")
    sys.exit(code)

if __name__ == "__main__":
    main()
