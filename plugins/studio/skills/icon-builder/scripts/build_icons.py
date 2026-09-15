#!/usr/bin/env python3
"""build_icons.py — マスターSVG 1枚から、favicon / PWA / iOS / Android の一式を書き出す。

面ごとに要求が正反対なのが、この作業が地味に厄介な理由:
  favicon は透過可・16pxで読めること、apple-touch-icon は透過不可（iOSが黒く塗る）、
  maskable は中央の円しか見えない保証がなく、App Store はアルファチャンネルを拒否する。
マスターは1枚のまま、面ごとに合成ルールだけを変えるのがこのスクリプトの役割。

SNSアカウント用のアイコンは sns-icon-builder が担当する。各社で切り抜かれる形が違い、
社ごとに縮尺を変えて焼き分ける必要があるため、ここでは扱わない。

  python3 build_icons.py --svg master.svg --out dist --name "Mediowl" \
      --pad-bg "#1c56d6" --targets web,pwa,ios,android --framework nextjs-app
"""
import argparse, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from iconlib import (die, warn, read_svg, get_viewbox, outline_text, optimize_svg,
                     Renderer, ink_bbox, is_full_bleed, compose, save_png, optimize_png, hex_rgb)

ALL_TARGETS = ["web", "pwa", "ios", "android"]

FRAMEWORKS = {
"html": ("素のHTML / Laravel Blade / EJS など", """\
1. `web/` の中身をサイトの公開フォルダ（`public/` や `httpdocs/`）の直下にそのまま置く
2. HTMLの `<head>` に貼る:

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
```

`sizes="32x32"` は飾りではない。これが無いと Chrome が SVG より ICO を選んでしまう。"""),

"nextjs-app": ("Next.js (App Router)", """\
Next.js は「決まった名前のファイルを決まった場所に置くと、タグを自動で書いてくれる」仕組み。
自分で `<link>` を書く必要はない。

```
app/favicon.ico          ← web/favicon.ico
app/icon.svg             ← web/icon.svg
app/apple-icon.png       ← web/apple-touch-icon.png
public/icon-192.png      ← web/icon-192.png
public/icon-512.png      ← web/icon-512.png
public/icon-mask.png     ← web/icon-mask.png
app/manifest.webmanifest ← web/manifest.webmanifest
```

注意: `app/` 直下に置くものはファイル名がそのまま意味を持つ。`apple-touch-icon.png` ではなく
**`apple-icon.png`** にリネームすること。"""),

"nextjs-pages": ("Next.js (Pages Router)", """\
1. `web/` の中身を `public/` の直下に置く
2. `pages/_document.tsx`（または `_app.tsx`）の `<Head>` に貼る:

```tsx
<link rel="icon" href="/favicon.ico" sizes="32x32" />
<link rel="icon" href="/icon.svg" type="image/svg+xml" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<link rel="manifest" href="/manifest.webmanifest" />
```"""),

"nuxt": ("Nuxt 3 / 4", """\
1. `web/` の中身を `public/` の直下に置く
2. `nuxt.config.ts`:

```ts
export default defineNuxtConfig({
  app: { head: { link: [
    { rel: 'icon', href: '/favicon.ico', sizes: '32x32' },
    { rel: 'icon', href: '/icon.svg', type: 'image/svg+xml' },
    { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' },
    { rel: 'manifest', href: '/manifest.webmanifest' },
  ] } },
})
```"""),

"vite": ("Vite (React / Vue / Svelte)", """\
1. `web/` の中身を `public/` の直下に置く
2. `index.html` の `<head>` に貼る:

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
```"""),

"astro": ("Astro", """\
1. `web/` の中身を `public/` の直下に置く
2. レイアウトの `<head>` に上の4行を貼る（Astro は `public/` をそのまま配信する）"""),

"laravel": ("Laravel (Blade)", """\
1. `web/` の中身を `public/` の直下に置く
2. `resources/views/layouts/app.blade.php` の `<head>` に貼る:

```blade
<link rel="icon" href="{{ asset('favicon.ico') }}" sizes="32x32">
<link rel="icon" href="{{ asset('icon.svg') }}" type="image/svg+xml">
<link rel="apple-touch-icon" href="{{ asset('apple-touch-icon.png') }}">
<link rel="manifest" href="{{ asset('manifest.webmanifest') }}">
```"""),

"wordpress": ("WordPress", """\
管理画面の「外観 → カスタマイズ → サイト基本情報 → サイトアイコン」は 512px のPNGを1枚しか
受け付けず、SVGもmanifestも設定できない。SVGの鮮明さを活かすなら手動で入れる:

1. `web/` の中身をテーマフォルダ直下（またはサイトルート）に置く
2. 子テーマの `functions.php`:

```php
add_action('wp_head', function () {
  $u = get_stylesheet_directory_uri();
  echo '<link rel="icon" href="'.$u.'/favicon.ico" sizes="32x32">';
  echo '<link rel="icon" href="'.$u.'/icon.svg" type="image/svg+xml">';
  echo '<link rel="apple-touch-icon" href="'.$u.'/apple-touch-icon.png">';
  echo '<link rel="manifest" href="'.$u.'/manifest.webmanifest">';
});
```

既定のサイトアイコン出力と二重にならないよう、カスタマイザー側は空にしておく。"""),
}

def build_manifest(a) -> dict:
    base = a.base_path.rstrip("/")
    return {
        "name": a.name,
        "short_name": a.short_name or a.name,
        "start_url": a.start_url,
        "display": "standalone",
        "background_color": a.bg_color,
        "theme_color": a.theme_color,
        "icons": [
            {"src": f"{base}/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": f"{base}/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": f"{base}/icon-mask.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
    }

def rounded(img, radius_frac: float):
    from PIL import Image, ImageDraw
    n = img.size[0]
    m = Image.new("L", (n * 4, n * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, n * 4 - 1, n * 4 - 1],
                                        radius=int(n * 4 * radius_frac), fill=255)
    m = m.resize((n, n), Image.LANCZOS)
    out = img.copy()
    out.putalpha(m)
    return out

def silhouette(img, color=(255, 255, 255)):
    from PIL import Image
    a = img.getchannel("A")
    s = Image.new("RGBA", img.size, (*color, 0))
    s.putalpha(a)
    px = s.load()
    solid = Image.new("RGBA", img.size, (*color, 255))
    solid.putalpha(a)
    return solid

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg", required=True, help="マスターSVG（viewBox は正方形、512推奨）")
    ap.add_argument("--out", required=True, help="出力ディレクトリ")
    ap.add_argument("--name", required=True, help="manifest の name")
    ap.add_argument("--short-name", default="", help="manifest の short_name（12文字以内推奨）")
    ap.add_argument("--targets", default="web,pwa", help=f"{','.join(ALL_TARGETS)} から選ぶ")
    ap.add_argument("--framework", default="html", choices=sorted(FRAMEWORKS), help="設置手順の出し分け")
    ap.add_argument("--font", default=None, help="SVG内の <text> をアウトライン化するフォント")
    ap.add_argument("--mark-svg", default=None,
                    help="プレート(地色)を除いたマークだけのSVG。プレート型の意匠では必須。"
                         "iOSの前景レイヤー・Androidのadaptive前景/monochromeに使う")
    ap.add_argument("--mono-svg", default=None,
                    help="Android monochrome を別意匠にしたいときだけ指定（既定は --mark-svg）")
    ap.add_argument("--pad-bg", default="#ffffff", help="透過が使えない面の地色")
    ap.add_argument("--theme-color", default=None, help="manifest theme_color（既定 --pad-bg）")
    ap.add_argument("--bg-color", default="#ffffff", help="manifest background_color（起動画面の地色）")
    ap.add_argument("--base-path", default="/", help="manifest 内のアイコンURLの接頭辞")
    ap.add_argument("--start-url", default="/", help="manifest の start_url")
    ap.add_argument("--ico-sizes", default="32", help="favicon.ico に詰めるサイズ。例 16,32,48")
    ap.add_argument("--apple-pad", type=float, default=0.10, help="apple-touch-icon の余白率")
    ap.add_argument("--maskable-scale", default="auto",
                    help="auto=安全円に必ず収める / 1.0=全面バッジ意匠として扱う / 任意の比率")
    ap.add_argument("--android-logo-dp", type=float, default=60.0, help="108dp中のロゴ寸法(48〜66)")
    ap.add_argument("--legacy-radius", type=float, default=0.20, help="Android旧アイコンの角丸率")
    a = ap.parse_args()

    targets = [t.strip() for t in a.targets.split(",") if t.strip()]
    for t in targets:
        if t not in ALL_TARGETS:
            die(f"--targets に不明な値: {t}（使えるのは {', '.join(ALL_TARGETS)}）")
    if "pwa" in targets and "web" not in targets:
        targets.append("web")
    a.theme_color = a.theme_color or a.pad_bg
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    svg = optimize_svg(outline_text(read_svg(a.svg), a.font))
    get_viewbox(svg)
    mark_svg = optimize_svg(outline_text(read_svg(a.mark_svg), a.font)) if a.mark_svg else None
    mono_src = a.mono_svg or a.mark_svg
    if "<image" in svg:
        die("マスターSVGに <image>（ラスタ埋め込み）があります。SVGにする意味が消えるので、"
            "図形かパスで描き直してください。")

    report = {"files": [], "source": str(a.svg), "targets": targets,
              "pad_bg": a.pad_bg, "maskable_scale": a.maskable_scale}

    def emit(img, rel, opaque=False, bg=None, meta=None, optimize=True):
        p = save_png(img, out / rel, opaque=opaque, bg=bg or a.pad_bg)
        # App Store と Play Store の提出アセットは減色しない。パレットPNGは
        # 「アルファチャンネル無しのRGB」であることを審査側に示せず、弾かれる余地が残る。
        size = optimize_png(p) if optimize else p.stat().st_size
        rec = {"path": rel, "px": img.size[0], "bytes": size, "opaque": opaque}
        if meta: rec.update(meta)
        report["files"].append(rec)
        print(f"  {rel:<46} {img.size[0]:>5}px  {size/1024:6.1f} KB")
        return p

    def assert_visible(img, rel):
        """地色とマークが同色で、真っ平らな1色の板になっていないか確かめる。

        透過の図案に、その図案と同じ色の地色を敷くと、合成後は完全な無地になる。
        ファイルは正常に見えるので、納品してから気づく類の事故になりやすい。
        """
        from iconlib import border_bg
        import numpy as np
        bg, cov = border_bg(img)
        if cov < 0.70:
            return
        arr = np.array(img.convert("RGB")).astype(int)
        vis = (np.abs(arr - np.array(bg)).sum(-1) > 28).mean()
        if vis < 0.01:
            die(f"{rel} が地色と同色で塗り潰されています（マークが見えるのは面積の {vis*100:.1f}%）。\n"
                f"        --pad-bg ({a.pad_bg}) が意匠のマークと同じ色になっていないか確認してください。")

    with Renderer(svg, color_scheme="light") as r:
        probe = r.render(512)
        bbox = ink_bbox(probe)
        if bbox is None:
            die("SVGを描画したら空でした。fill が透明、またはviewBoxの外に図形があります。")
        full_bleed = is_full_bleed(probe)
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        print(f"\n[build_icons] 意匠: {'全面塗り（バッジ型）' if full_bleed else '透過（図案型）'}"
              f" / インク占有 {bw*100:.0f}%x{bh*100:.0f}%\n")

        def fit_circle(diam_frac: float) -> float:
            """インクの外接円が直径 diam_frac の円に収まる占有率を返す。"""
            import math
            return min(diam_frac / math.hypot(bw, bh) * max(bw, bh), 1.0)

        if a.maskable_scale == "auto":
            # 全面塗りのプレートは「マスクされる前提で設計されたもの」なので全面のまま出す。
            # 欠けて困るのは中のマークだけで、それは verify が安全円で見る。
            mask_frac = 1.0 if full_bleed else fit_circle(0.80)
            mask_mode = "auto-fullbleed" if full_bleed else "auto-fit"
        else:
            mask_frac, mask_mode = float(a.maskable_scale), "manual"
        report["maskable_frac"] = round(mask_frac, 4)
        report["maskable_mode"] = mask_mode
        report["full_bleed"] = full_bleed

        # ---------------------------------------------------------- web
        if "web" in targets:
            (out / "web").mkdir(exist_ok=True)
            svg_p = out / "web" / "icon.svg"
            svg_p.write_text(svg, encoding="utf-8")
            report["files"].append({"path": "web/icon.svg", "px": None,
                                    "bytes": svg_p.stat().st_size, "opaque": False})
            print(f"  {'web/icon.svg':<46} {'vector':>7}  {svg_p.stat().st_size/1024:6.1f} KB")

            ico_sizes = sorted({int(s) for s in a.ico_sizes.split(",")})
            frames = [r.render(s) for s in ico_sizes]
            frames[0].save(out / "web" / "favicon.ico", format="ICO",
                           sizes=[(s, s) for s in ico_sizes])
            report["files"].append({"path": "web/favicon.ico", "px": ico_sizes[-1],
                                    "bytes": (out / "web" / "favicon.ico").stat().st_size,
                                    "opaque": False, "ico_sizes": ico_sizes})
            print(f"  {'web/favicon.ico':<46} {','.join(map(str,ico_sizes)):>7}  "
                  f"{(out/'web'/'favicon.ico').stat().st_size/1024:6.1f} KB")

            ap_frac = 1.0 if full_bleed else 1.0 - 2 * a.apple_pad
            ati = compose(r, 180, ap_frac, a.pad_bg, None if full_bleed else bbox)
            assert_visible(ati, "web/apple-touch-icon.png")
            emit(ati, "web/apple-touch-icon.png", opaque=True, meta={"role": "apple-touch-icon"})

        if "pwa" in targets:
            for px in (192, 512):
                emit(compose(r, px, 1.0, None), f"web/icon-{px}.png",
                     meta={"role": f"pwa-any-{px}"})
            emit(compose(r, 512, mask_frac, a.pad_bg, bbox),
                 "web/icon-mask.png", opaque=True,
                 meta={"role": "maskable", "safe_frac": round(mask_frac, 4), "mode": mask_mode})
            mf = out / "web" / "manifest.webmanifest"
            mf.write_text(json.dumps(build_manifest(a), ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
            report["files"].append({"path": "web/manifest.webmanifest", "px": None,
                                    "bytes": mf.stat().st_size, "opaque": False})
            print(f"  {'web/manifest.webmanifest':<46} {'json':>7}  {mf.stat().st_size/1024:6.1f} KB")

        # ---------------------------------------------------------- iOS
        if "ios" in targets:
            frac = 1.0 if full_bleed else 0.80
            emit(compose(r, 1024, frac, a.pad_bg, None if full_bleed else bbox),
                 "ios/AppIcon-1024.png", opaque=True, meta={"role": "appstore", "no_alpha": True},
                 optimize=False)
            (out / "ios" / "layers").mkdir(parents=True, exist_ok=True)
            if mark_svg:
                (out / "ios" / "layers" / "foreground.svg").write_text(mark_svg, encoding="utf-8")
            else:
                (out / "ios" / "layers" / "foreground.svg").write_text(svg, encoding="utf-8")
                if full_bleed:
                    warn("iOSの前景レイヤーに地色（プレート）が入ったままです。Appleはレイヤーから"
                         "背景色を外すよう求めており、そのままだと重ねたときに二重になります。"
                         "--mark-svg でマークだけのSVGを渡してください。")
            (out / "ios" / "layers" / "background.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
                f'<rect width="512" height="512" fill="{a.pad_bg}"/></svg>\n', encoding="utf-8")

        # ---------------------------------------------------------- Android
        if "android" in targets:
            res = out / "android" / "res"
            fg_frac = a.android_logo_dp / 108.0
            if mark_svg:
                r.use(mark_svg)
                mark_bbox = ink_bbox(r.render(512))
                if mark_bbox is None:
                    die("--mark-svg を描画したら空でした。")
            else:
                mark_bbox = bbox
                if full_bleed:
                    warn("Androidの前景レイヤーに地色（プレート）が入ったままです。背景レイヤーと"
                         "二重になるので、--mark-svg でマークだけのSVGを渡してください。")
            emit(compose(r, 432, fg_frac, None, mark_bbox),
                 "android/res/drawable/ic_launcher_foreground.png",
                 meta={"role": "adaptive-fg", "safe_frac": 66 / 108})
            from PIL import Image
            emit(Image.new("RGBA", (432, 432), (*hex_rgb(a.pad_bg), 255)),
                 "android/res/drawable/ic_launcher_background.png", meta={"role": "adaptive-bg"})
            if mono_src:
                r.use(optimize_svg(outline_text(read_svg(mono_src), a.font)))
                mb = ink_bbox(r.render(512))
                mono = silhouette(compose(r, 432, fg_frac, None, mb))
            else:
                mono = silhouette(compose(r, 432, fg_frac, None, bbox))
                if full_bleed:
                    warn("全面塗りの意匠からmonochromeを作ると、ただの四角になります。"
                         "--mark-svg で地色を除いたSVGを渡してください。")
            r.use(svg)
            emit(mono, "android/res/drawable/ic_launcher_monochrome.png", meta={"role": "monochrome"})
            (res / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
            (res / "mipmap-anydpi-v26" / "ic_launcher.xml").write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '    <background android:drawable="@drawable/ic_launcher_background" />\n'
                '    <foreground android:drawable="@drawable/ic_launcher_foreground" />\n'
                '    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />\n'
                '</adaptive-icon>\n', encoding="utf-8")
            r.use(svg)
            for dens, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
                lg = compose(r, px, 1.0 if full_bleed else 0.80, a.pad_bg, None if full_bleed else bbox)
                emit(rounded(lg, a.legacy_radius), f"android/res/mipmap-{dens}/ic_launcher.png",
                     meta={"role": f"legacy-{dens}"})
            emit(compose(r, 512, 1.0 if full_bleed else 0.88, a.pad_bg, None if full_bleed else bbox),
                 "android/play-store-512.png", meta={"role": "play-store"}, optimize=False)

    label, steps = FRAMEWORKS[a.framework]
    (out / "INSTALL.md").write_text(
        f"# 設置手順（{label}）\n\n{steps}\n\n"
        "## 確認\n\n"
        "- ブラウザのタブに出るまでキャッシュが残ることがある。シークレットウィンドウで確認する\n"
        "- iOSのホーム画面追加は `apple-touch-icon.png` を見る。manifest ではない\n"
        "- Androidのホーム画面は manifest の `purpose: maskable` を見る\n",
        encoding="utf-8")
    (out / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    total = sum(f["bytes"] for f in report["files"] if f["path"].startswith("web/"))
    print(f"\n[build_icons] web一式の合計: {total/1024:.1f} KB")
    print(f"[build_icons] 設置手順: {out/'INSTALL.md'}")
    print(f"[build_icons] 次は必ず verify_icons.py に通すこと: "
          f"python3 scripts/verify_icons.py --dist {out}\n")

if __name__ == "__main__":
    main()
