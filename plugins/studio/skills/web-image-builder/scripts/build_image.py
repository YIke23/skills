#!/usr/bin/env python3
"""
build_image.py - ブラウザで文字を描き、等倍でPNGに焼く画像ビルダー。

設計方針:
  劣化に弱いもの(文字・ロゴ)はブラウザにベクタで描かせ、
  劣化に強いもの(背景写真)だけをラスタで扱う。
  出力サイズと同じ寸法のビューポートで1回だけスクリーンショットするので、
  拡大・縮小・再圧縮が一切入らない。

使い方:
  python3 build_image.py --preset ogp --title "..." --meta "..." --bg bg.jpg --logo logo.svg --out ogp.png
  python3 build_image.py --size 1920x1080 --layout centered --title "..." --out hero.png
  python3 build_image.py --spec batch.json          # 複数枚まとめて

安全装置:
  1) レンダリング前にフォントのグリフ網羅を検査 -> 描けない文字があれば止める(豆腐防止)
  2) タイトルを自動縮小してボックスに収める(文字切れ防止)
  3) レンダリング後にはみ出しを再検査 -> 残っていれば止める
どれも「黙って壊れた画像を出す」のを防ぐためのもの。警告を無視して出荷しないこと。
"""
from __future__ import annotations
import argparse, base64, json, math, mimetypes, pathlib, subprocess, sys, tempfile

# ---------------------------------------------------------------- presets
# 用途ごとの実寸。SNS側で更に縮小表示されるので、等倍で作るのが最も鮮明。
PRESETS = {
    "ogp":        (1200, 630),   # Open Graph 標準 (Facebook / Slack / LINE)
    "x-card":     (1200, 675),   # X summary_large_image (16:9)
    "linkedin":   (1200, 627),
    "slider":     (1920, 1080),  # サイト内ヒーロー / スライダー
    "slider-wide":(2400, 1000),  # ワイドなヒーロー帯
    "banner":     (1200, 300),   # 横長バナー
    "banner-mpu": (300, 250),    # レクタングル広告
    "leaderboard":(728, 90),     # 細長バナー
    "square":     (1080, 1080),  # Instagram / 汎用SNS
    "story":      (1080, 1920),  # Stories / Reels / LINE VOOM
    "thumbnail":  (1280, 720),   # YouTube サムネイル
}

# レイアウト: キャンバスの縦横比で選ぶ。詳細は references/presets.md
LAYOUTS = ("standard", "centered", "strip")

# 区切り装飾。すべてインラインSVGで描く。
# 「◆」「✦」のような約物を文字として置くとフォント依存になり、
# グリフが無ければ豆腐になる。図形として描けばその事故が起きない。
DIVIDERS = ("none", "line", "dots", "diamond", "star", "rule")


def divider_svg(style: str, u: float, color: str, align: str) -> str:
    """区切り装飾を返す。u はキャンバスのスケール基準 sqrt(W*H)。

    装飾は縮小表示で最初に消える要素なので、意味を運ばせてはいけない。
    間を作る・視線を止める、以上の仕事はさせないこと。
    """
    if style in ("none", ""):
        return ""
    w = u * 0.30
    h = max(u * 0.030, 8)
    cy = h / 2
    mid = w / 2
    stroke = max(u * 0.0022, 1)
    if style == "rule":
        return (f'<div class="divider"><svg width="{u*0.13:.1f}" height="{max(u*0.007,3):.1f}" '
                f'viewBox="0 0 100 6"><rect width="100" height="6" rx="3" fill="{color}"/></svg></div>')
    if style == "line":
        return (f'<div class="divider"><svg width="{w:.1f}" height="{h:.1f}" '
                f'viewBox="0 0 {w:.1f} {h:.1f}"><defs><linearGradient id="dg">'
                f'<stop offset="0" stop-color="{color}" stop-opacity="0"/>'
                f'<stop offset=".5" stop-color="{color}" stop-opacity="1"/>'
                f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
                f'<rect y="{cy-stroke/2:.2f}" width="{w:.1f}" height="{stroke:.2f}" fill="url(#dg)"/>'
                f'</svg></div>')
    r = max(u * 0.0045, 2)
    if style == "dots":
        gap = r * 5
        cs = "".join(f'<circle cx="{mid + i*gap:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{color}"/>'
                     for i in (-1, 0, 1))
        return (f'<div class="divider"><svg width="{w:.1f}" height="{h:.1f}" '
                f'viewBox="0 0 {w:.1f} {h:.1f}">{cs}</svg></div>')
    # diamond / star は左右の線 + 中央の飾り
    orn_w = u * 0.030
    lw = (w - orn_w * 2.2) / 2
    lines = (f'<rect x="0" y="{cy-stroke/2:.2f}" width="{lw:.1f}" height="{stroke:.2f}" '
             f'fill="{color}" opacity=".55"/>'
             f'<rect x="{w-lw:.1f}" y="{cy-stroke/2:.2f}" width="{lw:.1f}" height="{stroke:.2f}" '
             f'fill="{color}" opacity=".55"/>')
    if style == "diamond":
        d = orn_w * 0.42
        orn = (f'<path d="M{mid:.2f} {cy-d:.2f} L{mid+d:.2f} {cy:.2f} '
               f'L{mid:.2f} {cy+d:.2f} L{mid-d:.2f} {cy:.2f} Z" fill="{color}"/>')
    else:  # star
        o, i2 = orn_w * 0.5, orn_w * 0.16
        orn = (f'<path d="M{mid:.2f} {cy-o:.2f} L{mid+i2:.2f} {cy-i2:.2f} L{mid+o:.2f} {cy:.2f} '
               f'L{mid+i2:.2f} {cy+i2:.2f} L{mid:.2f} {cy+o:.2f} L{mid-i2:.2f} {cy+i2:.2f} '
               f'L{mid-o:.2f} {cy:.2f} L{mid-i2:.2f} {cy-i2:.2f} Z" fill="{color}"/>')
    return (f'<div class="divider"><svg width="{w:.1f}" height="{h:.1f}" '
            f'viewBox="0 0 {w:.1f} {h:.1f}">{lines}{orn}</svg></div>')

# フォント探索順。上にあるものが優先。自社フォントは --font で割り込ませる。
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansJP-Bold.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def title_coef(U: float) -> float:
    """キャンバスが小さいほどタイトルは相対的に大きくないと読めない。
    300x250のバナーとOGPで同じ比率にすると、小さい方が文字が細く沈む。"""
    if U >= 800:  return 0.075
    if U >= 500:  return 0.090
    return 0.110


def die(msg: str) -> "None":
    print(f"\n[build_image] エラー: {msg}\n", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- font
def resolve_font(explicit: str | None) -> str:
    if explicit:
        p = pathlib.Path(explicit).expanduser()
        if not p.is_file():
            die(f"--font に指定されたファイルが見つかりません: {p}")
        return str(p)
    for c in FONT_CANDIDATES:
        if pathlib.Path(c).is_file():
            return c
    # fontconfig に最後の望みを託す
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", "sans-serif:lang=ja"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if out and pathlib.Path(out).is_file():
            return out
    except Exception:
        pass
    die("日本語を描けるフォントが見つかりません。--font でTTF/OTF/TTCのパスを指定してください。\n"
        "        フォント無しで進めると文字が □ になった画像が黙って出来上がるため、ここで停止します。")


def missing_glyphs(font_path: str, text: str) -> list[str]:
    """フォントが text の全文字を持っているか調べ、持っていない文字を返す。

    これが今回一番効く安全装置。PIL や matplotlib のデフォルトフォントは
    CJKグリフを持たないため、気づかないまま □□□ の画像が出来る事故が起きる。
    描く前に検査すれば、その事故は原理的に起きない。
    """
    try:
        from fontTools.ttLib import TTFont, TTCollection
    except ImportError:
        print("[build_image] 注意: fontTools が無いためグリフ検査をスキップしました "
              "(pip install fonttools 推奨)", file=sys.stderr)
        return []
    try:
        if font_path.lower().endswith((".ttc", ".otc")):
            faces = list(TTCollection(font_path).fonts)
        else:
            faces = [TTFont(font_path, fontNumber=0)]
    except Exception as e:
        print(f"[build_image] 注意: フォント解析に失敗しグリフ検査をスキップ ({e})", file=sys.stderr)
        return []
    covered: set[int] = set()
    for f in faces:                      # TTCは同一書体の言語別バリアントなので和集合で判定
        try:
            for table in f["cmap"].tables:
                covered |= set(table.cmap.keys())
        except Exception:
            continue
    import unicodedata
    # ゼロ幅スペースや制御文字はフォントに無くても描画に支障がない。
    # これを検出対象に含めると、改行位置調整のテクニックが誤って弾かれる。
    def ignorable(ch: str) -> bool:
        return unicodedata.category(ch) in ("Cf", "Cc", "Zl", "Zp") or ch in "\n\r\t\u200b\u2060\ufeff"
    return sorted({ch for ch in text if not ignorable(ch) and ord(ch) not in covered})


# ---------------------------------------------------------------- assets
def data_uri(path: str) -> str:
    p = pathlib.Path(path).expanduser()
    if not p.is_file():
        die(f"ファイルが見つかりません: {p}")
    mime = mimetypes.guess_type(str(p))[0]
    if p.suffix.lower() in (".ttc", ".otc"):
        mime = "font/collection"
    elif p.suffix.lower() in (".ttf",):
        mime = "font/ttf"
    elif p.suffix.lower() in (".otf",):
        mime = "font/otf"
    mime = mime or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def esc_multiline(s: str) -> str:
    """改行を <br> に変換する。

    日本語は単語の区切りが無いため、ブラウザはほぼ任意の位置で折り返す。
    「無料診断は / じめました」のような語中改行を避けたいときは、
    タイトルに改行文字を入れて明示的に指定するのが唯一確実な方法。
    空白を入れるだけでは text-wrap:balance が別の位置を選ぶので効かない。
    """
    return esc(s).replace("\r\n", "\n").replace("\n", "<br>")


# ---------------------------------------------------------------- html
def build_html(cfg: dict) -> str:
    W, H = cfg["width"], cfg["height"]
    U = math.sqrt(W * H)          # キャンバス面積から出す単一のスケール基準。
                                  # これ1本で 300x250 から 1080x1920 まで比率が崩れない。
    layout = cfg["layout"]
    pad     = round(U * (0.045 if layout == "strip" else 0.075))
    meta_px = round(U * 0.029)
    logo_px = round(U * 0.044)
    badge_px= round(U * 0.024)
    cta_px  = max(round(U * 0.038), 11)
    coef    = title_coef(U) * (1.35 if layout == "centered" else 1.0)
    t_max   = cfg.get("title_max") or round(U * coef)
    t_min   = cfg.get("title_min") or round(U * coef * 0.40)

    bg_layer = ""
    if cfg.get("bg"):
        bg_layer = f"background-image:url({data_uri(cfg['bg'])});background-size:cover;background-position:{cfg.get('bg_position','center')};"
    else:
        bg_layer = f"background:{cfg.get('bg_color','#0b1524')};"

    ov = cfg.get("overlay", 0.82)
    accent = cfg.get("accent", "#4da3ff")
    fg     = cfg.get("fg", "#ffffff")
    meta_c = cfg.get("meta_color", accent)

    # オーバーレイ: 背景写真の上でも文字のコントラストを確保するための膜。
    # 文字側を太くするより、背景を沈めるほうが可読性が上がって崩れにくい。
    if layout == "centered":
        overlay = (f"radial-gradient(ellipse at center,rgba(5,12,26,{ov}) 0%,"
                   f"rgba(5,12,26,{max(ov-0.25,0):.2f}) 100%)")
        align, just, text_align = "center", "center", "center"
    elif layout == "strip":
        overlay = f"linear-gradient(90deg,rgba(5,12,26,{ov}) 0%,rgba(5,12,26,{max(ov-0.35,0):.2f}) 100%)"
        align, just, text_align = "center", "flex-start", "left"
    else:
        overlay = (f"linear-gradient(100deg,rgba(5,12,26,{ov}) 0%,"
                   f"rgba(5,12,26,{max(ov-0.22,0):.2f}) 55%,"
                   f"rgba(5,12,26,{max(ov-0.5,0):.2f}) 100%)")
        align, just, text_align = "flex-start", "space-between", "left"

    logo_html = f'<img class="logo" src="{data_uri(cfg["logo"])}" alt="">' if cfg.get("logo") else ""
    badge_html = f'<div class="badge">{esc(cfg["badge"])}</div>' if cfg.get("badge") else ""
    meta_html  = f'<div class="meta">{esc(cfg["meta"])}</div>' if cfg.get("meta") else ""
    cta_html   = f'<div class="cta">{esc(cfg["cta"])}</div>' if cfg.get("cta") else ""
    sub_html   = f'<div class="sub" id="sub">{esc(cfg["sub"])}</div>' if cfg.get("sub") else ""
    # 中身の無い箱を出すと、飾りのバーだけが浮いたり不要な余白が残る。
    # 要素があるときだけ組み立てる。
    bar_html   = '<div class="bar"></div>' if cfg.get("meta") else ""
    head_html  = f'<div class="head">{logo_html}{badge_html}</div>' if (logo_html or badge_html) else ""
    footmain   = f'<div class="footmain">{meta_html}{bar_html}</div>' if meta_html else ""
    foot_html  = f'<div class="foot">{footmain}{cta_html}</div>' if (footmain or cta_html) else ""
    div_html   = divider_svg(cfg.get("divider", "none"), U, accent, layout)
    titlebox   = (f'<div class="titlebox"><div class="titlegroup">'
                  f'<h1 id="title">{esc_multiline(cfg["title"])}</h1>{sub_html}</div></div>')
    font_face  = (f'@font-face{{font-family:BrandFont;src:url({data_uri(cfg["font"])});'
                  f'font-weight:{cfg.get("weight",700)};font-display:block}}')

    if layout == "strip":
        body = f"""<div class="card">
  <div class="left">{logo_html}</div>
  <div class="mid">{titlebox}{meta_html}</div>
  <div class="right">{cta_html}</div>
</div>"""
    else:
        body = f"""<div class="card">
  {head_html}
  {div_html}
  {titlebox}
  {foot_html}
</div>"""

    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>
{font_face}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#000}}
.card{{position:relative;width:{W}px;height:{H}px;padding:{pad}px;
  display:flex;{'flex-direction:row;gap:'+str(pad)+'px;' if layout=='strip' else 'flex-direction:column;'}
  {'gap:'+str(round(pad*0.85))+'px;' if layout=='centered' else ''}
  align-items:{align};justify-content:{just};text-align:{text_align};
  {bg_layer}
  font-family:BrandFont,"Noto Sans CJK JP","Hiragino Sans","Yu Gothic",sans-serif;
  color:{fg};-webkit-font-smoothing:antialiased;text-rendering:geometricPrecision}}
.card::before{{content:"";position:absolute;inset:0;background:{overlay}}}
.card>*{{position:relative;z-index:1}}
.logo{{height:{logo_px}px;width:auto;display:block;flex:none}}
.head{{display:flex;align-items:center;gap:{round(pad*0.4)}px;flex:none}}
.badge{{font-size:{badge_px}px;font-weight:700;letter-spacing:.10em;
  padding:{round(badge_px*0.45)}px {round(badge_px*0.9)}px;border-radius:{round(badge_px*0.35)}px;
  background:{accent};color:#04101f;white-space:nowrap}}
/* fit を機械的に効かせるには、文字ボックスの高さが「中身に依存しない」ことが必須。
   centered は height を割合で固定し(親が固定寸法なので確定値になる)、
   それ以外は flex:1 で残り全部を取らせる。どちらも中身では伸び縮みしない。 */
.titlebox{{{'flex:0 0 auto;height:62%;' if layout=='centered' else 'flex:1 1 auto;'}
  min-height:0;width:100%;display:flex;align-items:center;
  {'justify-content:center;' if layout=='centered' else ''}overflow:hidden}}
h1{{font-size:{t_max}px;font-weight:{cfg.get('weight',700)};line-height:1.30;
  letter-spacing:.005em;text-wrap:balance;overflow-wrap:break-word;
  line-break:strict;word-break:normal;width:100%;
  max-height:100%;text-shadow:0 {round(U*0.002)}px {round(U*0.012)}px rgba(0,0,0,.45)}}
.divider{{flex:none;line-height:0;margin:{round(pad*0.30)}px 0;
  {'align-self:center;' if layout=='centered' else 'align-self:flex-start;'}}}
.titlegroup{{width:100%;display:flex;flex-direction:column;gap:{round(U*0.018)}px;
  {'align-items:center;' if layout=='centered' else 'align-items:flex-start;'}}}
.sub{{font-size:{round(U*0.030)}px;font-weight:600;color:{fg};opacity:.88;line-height:1.5}}
.foot{{flex:none;display:flex;flex-direction:row;align-items:flex-end;
  justify-content:{'center' if layout=='centered' else 'space-between'};
  gap:{round(pad*0.5)}px;width:100%}}
.footmain{{display:flex;flex-direction:column;gap:{round(pad*0.28)}px;
  {'align-items:center;' if layout=='centered' else 'align-items:flex-start;'}}}
.meta{{font-size:{meta_px}px;font-weight:700;color:{meta_c};letter-spacing:.02em}}
.bar{{width:{round(U*0.13)}px;height:{max(round(U*0.007),3)}px;background:{accent};
  border-radius:{max(round(U*0.004),2)}px}}
.left,.right{{flex:none;display:flex;align-items:center}}
.mid{{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;justify-content:center;
  gap:{round(pad*0.2)}px;height:100%}}
.mid .titlebox{{align-items:center}}
.cta{{font-size:{cta_px}px;font-weight:700;color:#04101f;background:{accent};
  padding:{round(cta_px*0.62)}px {round(cta_px*1.25)}px;border-radius:{round(cta_px*0.42)}px;
  white-space:nowrap}}
{cfg.get('extra_css','')}
</style></head><body>
{body}
<script>
// タイトルを二分探索でボックスに収める。
// 手で改行位置やフォントサイズを決めると、タイトルの長さが変わった瞬間に
// はみ出すか間延びする。収まる最大サイズを機械的に探すほうが確実。
window.__fit = function(maxPx, minPx) {{
  const h1  = document.getElementById('title');
  const grp = h1.parentElement;            // 見出し + サブコピーのまとまり
  const box = grp.parentElement;           // 高さが中身に依存しない外箱
  const sub = document.getElementById('sub');
  const fits = () => grp.scrollHeight <= box.clientHeight + 1 &&
                     grp.scrollWidth  <= box.clientWidth  + 1;
  let lo = minPx, hi = maxPx, best = minPx;
  while (lo <= hi) {{
    const mid = Math.floor((lo + hi) / 2);
    h1.style.fontSize = mid + 'px';
    if (sub) sub.style.fontSize = Math.round(mid * 0.42) + 'px';
    if (fits()) {{ best = mid; lo = mid + 1; }} else {{ hi = mid - 1; }}
  }}
  h1.style.fontSize = best + 'px';
  if (sub) sub.style.fontSize = Math.round(best * 0.42) + 'px';
  return {{ size: best, min: minPx, max: maxPx, overflow: !fits() }};
}};
</script></body></html>"""


# ---------------------------------------------------------------- render
def render(cfg: dict) -> dict:
    from playwright.sync_api import sync_playwright
    W, H = cfg["width"], cfg["height"]
    html = build_html(cfg)
    U = math.sqrt(W * H)
    coef  = title_coef(U) * (1.35 if cfg["layout"] == "centered" else 1.0)
    t_max = cfg.get("title_max") or round(U * coef)
    t_min = cfg.get("title_min") or round(U * coef * 0.40)

    with tempfile.TemporaryDirectory() as td:
        page_path = pathlib.Path(td) / "page.html"
        page_path.write_text(html, encoding="utf-8")
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--force-color-profile=srgb",
                                        "--disable-lcd-text"])   # サブピクセルを切って色滲みを防ぐ
            pg = b.new_page(viewport={"width": W, "height": H},
                            device_scale_factor=cfg.get("scale", 1))
            pg.goto(page_path.resolve().as_uri())
            pg.wait_for_timeout(150)
            try:
                pg.evaluate("document.fonts.ready")
            except Exception:
                pass
            pg.wait_for_timeout(250)
            fit = pg.evaluate(f"window.__fit({t_max}, {t_min})")
            pg.wait_for_timeout(120)
            pathlib.Path(cfg["out"]).parent.mkdir(parents=True, exist_ok=True)
            pg.screenshot(path=cfg["out"], type="png")   # PNG固定。JPEG/WebPは文字のエッジが荒れる
            b.close()
    return fit


def run_one(cfg: dict) -> dict:
    cfg["font"] = resolve_font(cfg.get("font"))
    probe = " ".join(str(cfg.get(k, "")) for k in ("title", "meta", "badge", "cta", "sub"))
    miss = missing_glyphs(cfg["font"], probe)
    if miss:
        die("指定フォントに以下の文字のグリフがありません。このまま描くと □ になります:\n"
            f"        {' '.join(miss)}\n"
            f"        font: {cfg['font']}\n"
            "        日本語対応フォントを --font で指定するか、文字を差し替えてください。")
    missing_assets = [n for n, k in (("ロゴ", "logo"), ("背景画像", "bg")) if not cfg.get(k)]
    if missing_assets:
        print(f"[build_image] 注意: {' と '.join(missing_assets)} が指定されていません。"
              f"このスキルでは必須素材です。\n"
              f"        意図した省略でなければ、素材を用意するか生成してから作り直すこと。",
              file=sys.stderr)
    fit = render(cfg)
    status = "ok"
    if fit.get("overflow"):
        status = "overflow"
    elif fit["size"] <= fit["min"]:
        status = "shrunk-to-min"
    sc = cfg.get("scale", 1)
    return {"out": cfg["out"], "size": f"{cfg['width']*sc}x{cfg['height']*sc}",
            "title_px": fit["size"], "status": status}


# ---------------------------------------------------------------- cli
def parse_size(preset: str | None, size: str | None) -> tuple[int, int]:
    if size:
        try:
            w, h = size.lower().split("x")
            return int(w), int(h)
        except Exception:
            die(f"--size は 1200x630 の形式で指定してください (受け取った値: {size})")
    if preset:
        if preset not in PRESETS:
            die(f"未知のプリセット '{preset}'。使えるのは: {', '.join(PRESETS)}")
        return PRESETS[preset]
    return PRESETS["ogp"]


def auto_layout(w: int, h: int) -> str:
    r = w / h
    if r >= 3.0:   return "strip"      # 極端に横長な帯はロゴ|文字|CTA の一列が読みやすい
    if r <= 1.30:  return "centered"   # 正方形に近いもの・縦長は中央揃えが安定
    return "standard"


def main() -> None:
    ap = argparse.ArgumentParser(description="ブラウザで文字を描き等倍でPNGに焼く画像ビルダー")
    ap.add_argument("--spec", help="複数枚をまとめて作るJSONファイル (references/recipes.md 参照)")
    ap.add_argument("--preset", choices=sorted(PRESETS), help=f"用途プリセット (既定: ogp)")
    ap.add_argument("--size", help="任意サイズ 例: 1600x900 (--preset より優先)")
    ap.add_argument("--layout", choices=LAYOUTS, help="既定は縦横比から自動選択")
    ap.add_argument("--title"); ap.add_argument("--meta", default="")
    ap.add_argument("--badge", default=""); ap.add_argument("--cta", default="")
    ap.add_argument("--sub", default="", help="見出しの直下に置くサブコピー(--meta は下端の情報行)")
    ap.add_argument("--divider", choices=DIVIDERS, default="none",
                    help="見出しの上に置く区切り装飾。全てSVG図形で描くのでフォント非依存")
    ap.add_argument("--bg", help="背景画像。出力より大きいものを渡すと cover で縮小される")
    ap.add_argument("--bg-color", default="#0b1524", help="背景画像を使わない場合の単色/グラデCSS")
    ap.add_argument("--bg-position", default="center")
    ap.add_argument("--logo", help="ロゴ。SVG推奨(PNGは拡大でボケる)")
    ap.add_argument("--font", help="TTF/OTF/TTCのパス。自社フォントはここで指定")
    ap.add_argument("--weight", type=int, default=700)
    ap.add_argument("--accent", default="#4da3ff"); ap.add_argument("--fg", default="#ffffff")
    ap.add_argument("--meta-color")
    ap.add_argument("--overlay", type=float, default=0.82,
                    help="背景を沈める膜の濃さ 0-1 (既定 0.82)")
    ap.add_argument("--title-max", type=int); ap.add_argument("--title-min", type=int)
    ap.add_argument("--extra-css", help="追記するCSSファイル。ブランド調整はここで")
    ap.add_argument("--scale", type=int, default=1,
                    help="1のままで良い。2は印刷等で実寸の2倍が必要なときだけ")
    ap.add_argument("--out", default="output.png")
    a = ap.parse_args()

    extra_css = pathlib.Path(a.extra_css).read_text(encoding="utf-8") if a.extra_css else ""

    if a.spec:
        spec = json.loads(pathlib.Path(a.spec).read_text(encoding="utf-8"))
        shared = spec.get("shared", {})
        results = []
        for i, item in enumerate(spec["images"]):
            cfg = {**shared, **item}
            w, h = parse_size(cfg.get("preset"), cfg.get("size"))
            cfg.update(width=w, height=h,
                       layout=cfg.get("layout") or auto_layout(w, h),
                       out=cfg.get("out") or f"image_{i+1}.png",
                       extra_css=cfg.get("extra_css", extra_css))
            cfg.setdefault("overlay", 0.82); cfg.setdefault("accent", "#4da3ff")
            cfg.setdefault("divider", "none")
            if not cfg.get("title"):
                die(f"images[{i}] に title がありません")
            results.append(run_one(cfg))
    else:
        if not a.title:
            die("--title は必須です (または --spec でまとめて指定)")
        w, h = parse_size(a.preset, a.size)
        cfg = dict(width=w, height=h, layout=a.layout or auto_layout(w, h),
                   title=a.title, meta=a.meta, badge=a.badge, cta=a.cta, sub=a.sub,
                   divider=a.divider,
                   bg=a.bg, bg_color=a.bg_color, bg_position=a.bg_position,
                   logo=a.logo, font=a.font, weight=a.weight,
                   accent=a.accent, fg=a.fg, meta_color=a.meta_color or a.accent,
                   overlay=a.overlay, title_max=a.title_max, title_min=a.title_min,
                   extra_css=extra_css, scale=a.scale, out=a.out)
        results = [run_one(cfg)]

    print(f"\n{'出力':34} {'寸法':12} {'タイトル':>8}  判定")
    for r in results:
        note = {"ok": "OK",
                "overflow": "はみ出し! レイアウト/文字数を見直してください",
                "shrunk-to-min": "最小サイズまで縮小。文字数を削るか --title-min を下げる"}[r["status"]]
        print(f"{r['out']:34} {r['size']:12} {r['title_px']:>6}px  {note}")
    if any(r["status"] != "ok" for r in results):
        sys.exit(2)


if __name__ == "__main__":
    main()
