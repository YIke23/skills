#!/usr/bin/env python3
"""build_sns_icons.py — マスターSVG 1枚から、各SNSアカウント用のアイコンを1枚ずつ書き出す。

同じ1枚を7箇所に上げてはいけない理由は容量ではなく**切り抜き形状**にある。
X・Instagram・note・LINE・YouTube・GitHub(個人)は円に切り、Slack と GitHub(Organization)は
角丸四角に切る。円に収まるまで縮めた絵を角丸の社に上げると小さく見え、角丸のつもりで
端まで使った絵を円の社に上げると欠ける。だから面ごとに縮尺を変えて焼き分ける。

  python3 build_sns_icons.py --svg master.svg --out dist --pad-bg "#1c56d6"
"""
import argparse, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from platforms import PLATFORMS, ORDER, SAFE, CROP_LABEL, resolve, filename
from snslib import (die, warn, read_svg, check_viewbox, outline_text, clean_svg, Renderer,
                    is_full_bleed, render_mark, shrink_to_budget, border_color, contrast_ratio,
                    hex_rgb, ink_mask_opaque, mask_reach)

PAGE_BG = {"ライトUI": (255, 255, 255), "ダークUI": (21, 22, 24)}


def assert_visible(img, label, pad_bg):
    """地色とマークが同色で、真っ平らな1色の板になっていないか確かめる。

    透過の図案に、その図案と同じ色の地色を敷くと、合成後は完全な無地になる。
    ファイルは正常に見えるので、上げてから気づく類の事故になりやすい。
    """
    import numpy as np
    mask, bg, solid = ink_mask_opaque(img)
    if not solid:
        return
    vis = float(mask.mean())
    if vis < 0.01:
        die(f"{label} が地色と同色で塗り潰されています（マークが見えるのは面積の {vis*100:.1f}%）。\n"
            f"        --pad-bg ({pad_bg}) が意匠のマークと同じ色になっていないか確認してください。")


def edge_contrast_note(pad_bg: str) -> list[str]:
    """アバターの地色が、置かれる側のUIの背景に溶けないかを見る。

    SNS特有の論点。favicon はタブの上に置かれるので地色とタブ色の関係だけ見ればよいが、
    アバターは「白いタイムライン」と「黒いタイムライン」の両方に、丸く切り抜かれて
    載る。地色がどちらかに近いと輪郭が消えて、マークだけが宙に浮いて見える。
    """
    rgb = hex_rgb(pad_bg)
    out = []
    for label, bg in PAGE_BG.items():
        c = contrast_ratio(rgb, bg)
        if c < 1.25:
            out.append(f"{label}（{'#ffffff' if label.startswith('ライト') else '#151618'}）と"
                       f"地色のコントラストが {c:.2f}:1 — アイコンの輪郭が背景に溶けます")
    return out


def build_upload_md(out: pathlib.Path, rows: list[dict], github_account: str) -> pathlib.Path:
    lines = ["# SNSアイコンの上げ方", "",
             "ファイル名がそのまま上げ先です。`x-400.png` は X、`slack-512.png` は Slack。",
             "**1枚を使い回さないこと。** 切り抜かれる形が社ごとに違うため、寸法は同じでも"
             "マークの大きさが違います。", ""]
    for r in rows:
        spec = r["spec"]
        lines += [f"## {spec['label']}", "",
                  f"- **ファイル**: `{r['file']}`（{r['px']}×{r['px']} / "
                  f"{r['bytes']/1024:.0f} KB / 上限 {spec['max_bytes']/1_000_000:.0f}MB）",
                  f"- **置き場所**: {spec['upload']}",
                  f"- **表示形状**: {CROP_LABEL[spec['crop']]}"
                  f"（いちばん小さく出るのは {spec['min_display']}px、{spec['min_display_where']}）",
                  f"- **注意**: {spec['gotcha']}", ""]
    lines += ["## 上げたあとに見るところ", "",
              "- 一覧画面（タイムライン・トークリスト・コミット一覧）まで戻って、"
              "**小さい表示で意味が読み取れるか**を見る。プロフィールページの大きい表示では分からない",
              "- ライトUIとダークUIの両方で見る。アバターは切り抜かれて背景の上に載るので、"
              "地色が背景に近いと輪郭が消える",
              "- LINEは1時間に1回しか変えられない。最後に回すか、先に他社で見え方を確かめる", ""]
    if github_account == "org":
        lines += ["> GitHub は Organization 用（角丸四角）で書き出しています。"
                  "個人アカウントに上げるなら `--github-account user` で焼き直してください。", ""]
    p = out / "UPLOAD.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg", required=True, help="マスターSVG（viewBox は正方形、512推奨）")
    ap.add_argument("--out", required=True, help="出力ディレクトリ")
    ap.add_argument("--pad-bg", default="#ffffff",
                    help="アイコンの地色。SNSは全社が透過の扱いを明記していないので必ず塗る")
    ap.add_argument("--platforms", default=",".join(ORDER),
                    help=f"書き出すサービス。{', '.join(ORDER)} から選ぶ")
    ap.add_argument("--github-account", default="user", choices=["user", "org"],
                    help="GitHub の切り抜き形状。個人=円 / Organization=角丸四角")
    ap.add_argument("--font", default=None, help="SVG内の <text> をアウトライン化するフォント")
    a = ap.parse_args()

    names = [n.strip() for n in a.platforms.split(",") if n.strip()]
    for n in names:
        if n not in PLATFORMS:
            die(f"--platforms に不明な値: {n}（使えるのは {', '.join(ORDER)}）")
    names = [n for n in ORDER if n in names]

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    svg = clean_svg(outline_text(read_svg(a.svg), a.font))
    check_viewbox(svg)
    if "<image" in svg:
        die("マスターSVGに <image>（ラスタ埋め込み）があります。各社の寸法に焼き直すと"
            "拡大されてボケるので、図形かパスで描き直してください。")

    rows, report = [], {"source": str(a.svg), "pad_bg": a.pad_bg,
                        "github_account": a.github_account, "files": []}

    with Renderer(svg, color_scheme="light") as r:
        probe = r.render(1024)
        if probe.getchannel("A").getbbox() is None:
            die("SVGを描画したら空でした。fill が透明か、viewBox の外に図形があります。")
        full_bleed = is_full_bleed(probe)
        report["full_bleed"] = full_bleed
        print(f"\n[build] 意匠: {'全面塗り（プレート型）' if full_bleed else '透過（図案型）'}"
              f" / 地色 {a.pad_bg}\n")

        for n in names:
            spec = resolve(n, a.github_account)
            safe = SAFE[spec["crop"]]["build"]
            img = render_mark(r, spec["crop"], spec["px"], a.pad_bg, full_bleed, safe)
            assert_visible(img, filename(n, spec), a.pad_bg)
            p, how = shrink_to_budget(img, out / filename(n, spec), spec["max_bytes"])
            n_bytes = p.stat().st_size
            if how == "over":
                warn(f"{p.name} が {spec['label']} の上限 "
                     f"{spec['max_bytes']/1_000_000:.0f}MB に収まりませんでした。意匠を疑ってください")
            mask, _, solid = ink_mask_opaque(img)
            reach = mask_reach(mask) if solid and mask is not None else None
            # 円方向の到達は「欠けないか」、縦横方向の到達は「どれだけ大きく載ったか」を表す。
            # 同じ意匠でも角丸の社のほうが後者が大きくなり、それが焼き分ける理由そのもの。
            r_circle, r_square = reach if reach else (1.0, 1.0)
            rec = {"platform": n, "file": p.name, "px": spec["px"], "bytes": n_bytes,
                   "crop": spec["crop"], "encoded": how,
                   "reach_circle": round(r_circle, 4), "reach_square": round(r_square, 4),
                   "mark_px_at_min_display": round(r_square * spec["min_display"], 1),
                   "spec": spec}
            rows.append(rec)
            report["files"].append({k: v for k, v in rec.items() if k != "spec"})
            print(f"  {p.name:<22} {spec['px']:>5}px  {n_bytes/1024:7.1f} KB  "
                  f"{CROP_LABEL[spec['crop']]:<4}  最小表示 {spec['min_display']:>2}px中 "
                  f"マーク {rec['mark_px_at_min_display']:>4.1f}px"
                  + ("" if how == "png" else f"  [{how}]"))

    for msg in edge_contrast_note(a.pad_bg):
        warn(msg)

    up = build_upload_md(out, rows, a.github_account)
    (out / "build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n[build] 上げ方: {up}")
    print(f"[build] 次は必ず verify に通すこと: "
          f"python3 scripts/verify_sns_icons.py --dist {out}\n")


if __name__ == "__main__":
    main()
