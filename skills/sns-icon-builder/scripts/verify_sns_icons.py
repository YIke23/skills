#!/usr/bin/env python3
"""verify_sns_icons.py — 書き出したアイコンが、各社の制約を実際に満たすか機械的に検査する。

SNSのアイコンで後から効いてくる事故は3つに絞られる:
  1. 円で切られて端が欠ける／角丸の社で小さく見える（切り抜き形状の取り違え）
  2. 一覧表示で潰れて誰のアカウントか分からない（**最小表示は20px。プロフィールの大きい表示では気づけない**）
  3. 容量上限で弾かれる（GitHub と Slack の1MB）

どれも数値で判定できるので、上げる前にここで止める。LINEは1時間に1回しか変更できず、
出し直しが効かない。

  python3 verify_sns_icons.py --dist dist [--strict] [--json result.json]

終了コード: 0=問題なし / 1=警告あり / 2=不適合あり
"""
import argparse, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platforms import PLATFORMS, ORDER, SAFE, CROP_LABEL, resolve, filename
from snslib import (contrast_ratio, hex_rgb, border_color, ink_mask_opaque, mask_reach, stroke_px)

PAGE_BG = {"ライトUI": (255, 255, 255), "ダークUI": (21, 22, 24)}


class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, name, detail):
        self.rows.append({"level": level, "check": name, "detail": detail})

    def ok(self, n, d=""):
        self.add("PASS", n, d)

    def warn(self, n, d):
        self.add("WARN", n, d)

    def fail(self, n, d):
        self.add("FAIL", n, d)

    def worst(self):
        levels = {r["level"] for r in self.rows}
        return 2 if "FAIL" in levels else (1 if "WARN" in levels else 0)


def has_alpha_channel(img) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info


def check_one(rep, dist: pathlib.Path, name: str, spec: dict, pad_bg=None):
    from PIL import Image
    label = spec["label"]
    png = dist / filename(name, spec)
    jpg = png.with_suffix(".jpg")
    p = png if png.is_file() else (jpg if jpg.is_file() else None)
    if p is None:
        rep.fail(label, f"{png.name} がありません")
        return

    img = Image.open(p)
    if img.size != (spec["px"], spec["px"]):
        rep.fail(f"{label} 寸法",
                 f"{img.size[0]}x{img.size[1]} — {spec['px']}x{spec['px']} でなければなりません")
        return

    # ---- 透過。全社が透過の扱いを明記していないので、あるだけで不適合にする
    if has_alpha_channel(img):
        rep.fail(f"{label} 透過", f"アルファチャンネルがあります（mode={img.mode}）— "
                                  "白で合成する社と黒で合成する社があり、見え方が制御できません")

    # ---- 容量
    n = p.stat().st_size
    if n > spec["max_bytes"]:
        rep.fail(f"{label} 容量",
                 f"{n/1024:.0f} KB — 上限 {spec['max_bytes']/1_000_000:.1f}MB を超えています")
    else:
        rep.ok(f"{label} 容量",
               f"{n/1024:.0f} KB / 上限 {spec['max_bytes']/1_000_000:.0f}MB")

    # ---- 切り抜きの安全域
    mask, bg, solid = ink_mask_opaque(img, bg=pad_bg)
    if not solid or mask is None:
        rep.warn(f"{label} 切り抜き",
                 "地色が単色でなく、build-report.json も無いため安全域を判定できません。"
                 "preview の切り抜き表示で目視してください")
        return
    reach = mask_reach(mask)
    if reach is None:
        rep.fail(f"{label} 切り抜き", "地色以外のピクセルがありません — 無地の板になっています")
        return
    r = reach[0] if spec["crop"] == "circle" else reach[1]
    th = SAFE[spec["crop"]]
    shape = CROP_LABEL[spec["crop"]]
    if r >= th["fail"]:
        rep.fail(f"{label} 切り抜き",
                 f"インクが{shape}の外へ {(r-1)*100:.1f}% はみ出しています — 確実に欠けます")
    elif r >= th["warn"]:
        rep.warn(f"{label} 切り抜き",
                 f"インクが{shape}の縁まで {r*100:.0f}% — トリミングUIの誤差で欠ける余地があります")
    elif r < th["build"] * 0.55:
        rep.warn(f"{label} 切り抜き",
                 f"インクが{shape}の {r*100:.0f}% しか使っていません — 一覧表示で小さく見えます")
    else:
        rep.ok(f"{label} 切り抜き", f"{shape} / インクの到達 {r*100:.0f}%")

    # ---- 最小表示での可読性。ここがこのスキルの本題
    d = spec["min_display"]
    small = img.convert("RGB").resize((d, d), Image.LANCZOS)
    smask, sbg, ssolid = ink_mask_opaque(small, tol=40, bg=pad_bg or bg)
    where = spec["min_display_where"]
    if not ssolid or smask is None or not smask.any():
        rep.fail(f"{label} {d}px可読性",
                 f"{d}px（{where}）に縮めると地色だけになります — マークが完全に消えています")
        return
    import numpy as np
    arr = np.array(small).reshape(-1, 3)
    best = max(contrast_ratio(tuple(px), sbg) for px in np.unique(arr, axis=0))
    eff = (mask_reach(smask)[1] if mask_reach(smask) else 0) * d
    sw = stroke_px(smask)
    if best < 3.0:
        rep.fail(f"{label} {d}px可読性",
                 f"地色とのコントラストが {best:.1f}:1 — {where} では塗り潰しに見えます")
    elif sw < 1.0:
        rep.fail(f"{label} {d}px可読性",
                 f"最小線幅が {d}px 換算で約 {sw:.2f}px — {where} で線が消えます")
    elif eff < d * 0.45:
        rep.warn(f"{label} {d}px可読性",
                 f"マークの実寸が {eff:.0f}px しかありません（{where} の {d}px 中）— 小さすぎます")
    else:
        rep.ok(f"{label} {d}px可読性",
               f"{where} {d}px / コントラスト {best:.1f}:1 / 線幅 {sw:.1f}px / マーク {eff:.0f}px")


def check_edge(rep, dist: pathlib.Path, rows, pad_bg=None):
    """地色が、置かれる側のUIの背景に溶けていないか。

    favicon と違ってアバターは切り抜かれて背景の上に載る。地色が白に近いと、
    ライトUIのタイムラインで輪郭が消えてマークだけが宙に浮く。ダークUIでも同じ。
    """
    from PIL import Image
    if not rows:
        return
    p = dist / rows[0]
    if not p.is_file():
        return
    if pad_bg:
        bg = hex_rgb(pad_bg)
    else:
        bg, cover = border_color(Image.open(p))
        if cover < 0.70:
            rep.warn("地色とUI背景", "地色が単色でないため判定できません。preview で目視してください")
            return
    for label, page in PAGE_BG.items():
        c = contrast_ratio(bg, page)
        if c < 1.25:
            rep.warn(f"地色とUI背景/{label}",
                     f"コントラスト {c:.2f}:1 — アイコンの輪郭が背景に溶け、マークだけが浮いて見えます")
        else:
            rep.ok(f"地色とUI背景/{label}", f"コントラスト {c:.2f}:1")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dist", required=True)
    ap.add_argument("--strict", action="store_true", help="警告も不適合として扱う")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    dist = pathlib.Path(a.dist)
    rep = Report()

    rp = dist / "build-report.json"
    meta = json.loads(rp.read_text()) if rp.is_file() else {}
    account = meta.get("github_account", "user")
    # プレート型（キャンバスを塗り切っている意匠）では、板そのものは切られる前提で描かれて
    # いるので、外周から板の色を拾って「中のマーク」だけをインクとして数える。図案型では
    # インクが縁まで届いていて外周から推定できないので、書き出しに使った地色をそのまま渡す。
    pad_bg = None if meta.get("full_bleed") else meta.get("pad_bg")
    built = {f["platform"] for f in meta.get("files", [])} or set(ORDER)

    names = [n for n in ORDER if n in built]
    if not names:
        rep.fail("入力", f"{dist} にアイコンが見つかりません")
    files = []
    for n in names:
        spec = resolve(n, account)
        check_one(rep, dist, n, spec, pad_bg)
        files.append(filename(n, spec))
    check_edge(rep, dist, files, pad_bg)

    if not (dist / "UPLOAD.md").is_file():
        rep.warn("UPLOAD.md", "上げ方の説明がありません。build_sns_icons.py で作り直してください")

    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    rep.rows.sort(key=lambda r: order[r["level"]])
    mark = {"PASS": "  OK ", "WARN": " WARN", "FAIL": " FAIL"}
    print()
    for r in rep.rows:
        print(f"{mark[r['level']]}  {r['check']:<34} {r['detail']}")
    n_f = sum(1 for r in rep.rows if r["level"] == "FAIL")
    n_w = sum(1 for r in rep.rows if r["level"] == "WARN")
    print(f"\n[verify] 不適合 {n_f} / 警告 {n_w} / 合格 {len(rep.rows)-n_f-n_w}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(
            {"fail": n_f, "warn": n_w, "rows": rep.rows}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    code = rep.worst()
    if a.strict and code == 1:
        code = 2
    if code == 0:
        print("[verify] 全社の制約を満たしています。\n")
    else:
        print("[verify] 上の項目を直してから上げてください。"
              "LINEは1時間に1回しか変更できないので、出し直しが効きません。\n")
    sys.exit(code)


if __name__ == "__main__":
    main()
