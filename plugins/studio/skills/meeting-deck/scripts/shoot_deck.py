#!/usr/bin/env python3
"""会議資料HTMLを、複数の画面の幅で実際に描画し、撮影して測る。

    uv run --python 3.12 --no-project --with playwright python shoot_deck.py deck.html --out DIR
    python3 shoot_deck.py deck.html --out DIR          # playwright が入っているなら
    python3 shoot_deck.py deck.html --widths 800,1280,1600,2000 --dark

check_deck.py はHTMLを読むだけで、描画はしない。だから見出しの改行の崩れ、
紙面の余白、図と本文の大きさの釣り合いは「不適合 0」のまま通ってしまう。
この道具はそれを埋める。やることは2つ。

1. 撮る — 画面の幅ごとに1枚ずつ、ページ全体のスクリーンショットを書き出す。
   測れないもの（見た目の釣り合い、図の読みやすさ）は、これを目で見て判断する。
2. 測る — ブラウザが実際に描いた位置と大きさで、次を確かめる。
   - 図中の文字の描画後の px（狭い幅で 14px、広い幅で本文の 1.75 倍）
   - 図中の文字が箱や図の端を越えていないか、バーや箱と重なっていないか
   - ページが横にはみ出していないか（表の .scroll の中は除く）
   - 左右の余白が deck.css の --gutter どおりか
   - 見出しの最後の行が1〜2字だけになっていないか
   - 図が画面の縦に収まるか

ブラウザは、入っている Google Chrome を優先して使う（ダウンロードが要らない）。
無ければ playwright の Chromium を使う。どちらも無いときは終了コード 3 で止まる。
そのときは Claude の Browser ペインなど、別の手段で撮る。

終了コード: 0=問題なし / 1=警告あり / 2=不適合 / 3=ブラウザを起動できない
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

WIDTHS = (800, 1600, 2000)
LEGIBLE_MIN = 14.0     # 図中の文字の下限（描画後の px）
TOO_BIG = 1.75         # 図中の文字が本文の何倍を超えたら「図だけ浮く」とみなすか
INNER_PAD = 6.0        # 箱の中の文字が枠から空ける余白（viewBox の単位）
FIG_SHARE = 0.65       # 図の高さが画面の高さの何割を超えたら1画面に収まらないとみなすか

# ブラウザの中で測る。座標はすべて画面の px（getBoundingClientRect）で揃える。
# 図形の座標を SVG の単位で追うと transform を解かなければならないが、
# 描画後の矩形なら入れ子の <g> があっても同じ物差しで比べられる。
MEASURE = r"""
({pad, figShare}) => {
  const out = {texts: [], overflow: [], headings: [], figures: [], gutter: null, body: 0};
  const vw = document.documentElement.clientWidth, vh = innerHeight;
  out.body = parseFloat(getComputedStyle(document.body).fontSize);

  const deck = document.querySelector('.deck');
  if (deck) {
    const cs = getComputedStyle(deck);
    out.gutter = [parseFloat(cs.paddingLeft), parseFloat(cs.paddingRight)];
  }

  // 横のはみ出し。表の .scroll と索引 .rail は横スクロールする前提なので除く。
  if (document.documentElement.scrollWidth > vw + 1) {
    for (const el of document.querySelectorAll('.deck *')) {
      if (el.closest('.scroll, .rail, svg')) continue;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && r.width > 0) {
        out.overflow.push({tag: el.tagName.toLowerCase(), cls: el.className || '',
                           right: Math.round(r.right), text: (el.textContent || '').trim().slice(0, 24)});
        if (out.overflow.length >= 5) break;
      }
    }
    if (!out.overflow.length) out.overflow.push({tag: 'html', cls: '', right: document.documentElement.scrollWidth, text: ''});
  }

  // 見出しの最後の行。1〜2字だけが次の行に落ちると、そこだけ別の語に見える。
  for (const h of document.querySelectorAll('h1, h2')) {
    const range = document.createRange();
    range.selectNodeContents(h);
    const n = h.querySelector('.n');
    if (n) range.setStartAfter(n);
    const rects = [...range.getClientRects()].filter(r => r.width > 0);
    const lines = [];
    for (const r of rects) {
      const last = lines[lines.length - 1];
      if (last && Math.abs(last.top - r.top) < r.height / 2) {
        last.left = Math.min(last.left, r.left); last.right = Math.max(last.right, r.right);
      } else lines.push({top: r.top, left: r.left, right: r.right});
    }
    const fs = parseFloat(getComputedStyle(h).fontSize);
    if (lines.length > 1) {
      const w = lines[lines.length - 1].right - lines[lines.length - 1].left;
      out.headings.push({text: h.textContent.trim().slice(0, 30), lines: lines.length, lastChars: w / fs});
    }
  }

  document.querySelectorAll('svg').forEach((svg, si) => {
    const sr = svg.getBoundingClientRect();
    const vb = svg.viewBox && svg.viewBox.baseVal;
    const scale = vb && vb.width ? sr.width / vb.width : 1;
    out.figures.push({i: si + 1, height: sr.height, share: sr.height / vh,
                      tall: sr.height > vh * figShare, width: sr.width,
                      inBox: !!svg.closest('.pair, .card')});
    const shapes = [...svg.querySelectorAll('rect, circle, ellipse')].map(el => ({
      r: el.getBoundingClientRect(), tag: el.tagName.toLowerCase(),
      group: el.classList.contains('group')})).filter(s => s.r.width > 0 && s.r.height > 0);
    svg.querySelectorAll('text').forEach(t => {
      const s = (t.textContent || '').trim();
      if (!s) return;
      const r = t.getBoundingClientRect();
      const fs = parseFloat(getComputedStyle(t).fontSize) * scale;
      const anchorX = t.getAttribute('text-anchor') === 'middle' ? (r.left + r.right) / 2
                    : t.getAttribute('text-anchor') === 'end' ? r.right : r.left;
      const cy = (r.top + r.bottom) / 2;
      const holders = shapes.filter(sh => sh.r.left <= anchorX && anchorX <= sh.r.right
                                         && sh.r.top <= cy && cy <= sh.r.bottom);
      const solid = holders.filter(h => !h.group);
      const pool = solid.length ? solid : holders;
      const holder = pool.sort((a, b) => a.r.width * a.r.height - b.r.width * b.r.height)[0];
      let problem = null;
      if (holder) {
        const p = pad * scale;
        const over = Math.max(holder.r.left + p - r.left, r.right - (holder.r.right - p));
        if (over > 0.5) problem = {kind: 'box', over: over / scale, boxW: holder.r.width / scale};
      } else {
        const over = Math.max(sr.left - r.left, r.right - sr.right);
        if (over > 0.5) problem = {kind: 'edge', over: over / scale};
        else {
          for (const sh of shapes) {
            if (sh.group) continue;
            const v = Math.min(r.bottom, sh.r.bottom) - Math.max(r.top, sh.r.top);
            const h = Math.min(r.right, sh.r.right) - Math.max(r.left, sh.r.left);
            if (v > r.height * 0.3 && h > 0.5) { problem = {kind: 'hit', over: h / scale, tag: sh.tag}; break; }
          }
        }
      }
      out.texts.push({fig: si + 1, text: s.slice(0, 24), px: fs, problem});
    });
  });
  return out;
}
"""


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []

    def fail(self, m: str) -> None:
        if m not in self.fails:
            self.fails.append(m)

    def warn(self, m: str) -> None:
        if m not in self.warns:
            self.warns.append(m)


def expected_gutter(width: float) -> float:
    return max(24.0, 0.12 * width - 72.0)


def launch(p):
    errors = []
    for kw in ({"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(**kw)
        except Exception as e:  # noqa: BLE001 — どちらで落ちたかを最後にまとめて出す
            errors.append(f"{kw or 'chromium'}: {str(e).splitlines()[0]}")
    raise RuntimeError(" / ".join(errors))


def main() -> int:
    ap = argparse.ArgumentParser(description="会議資料を複数の画面の幅で撮影して測る")
    ap.add_argument("path", type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="スクリーンショットの置き場所（既定は一時ディレクトリ）")
    ap.add_argument("--widths", default=",".join(map(str, WIDTHS)))
    ap.add_argument("--dark", action="store_true", help="ダークモードでも撮る")
    args = ap.parse_args()

    src = args.path.resolve()
    if not src.is_file():
        print(f"ファイルが無い: {src}", file=sys.stderr)
        return 2
    widths = [int(w) for w in args.widths.split(",") if w.strip()]
    out = (args.out or Path(tempfile.gettempdir()) / "meeting-deck-shots" / src.stem).resolve()
    out.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright が無い。次で動かす:\n"
              "  uv run --python 3.12 --no-project --with playwright python "
              f"{Path(__file__).name} {args.path}", file=sys.stderr)
        return 3

    r = Report()
    shots: list[Path] = []
    results: dict[int, dict] = {}
    try:
        with sync_playwright() as p:
            try:
                browser = launch(p)
            except RuntimeError as e:
                print(f"ブラウザを起動できない（{e}）。Browser ペインなど別の手段で撮る",
                      file=sys.stderr)
                return 3
            schemes = ["light", "dark"] if args.dark else ["light"]
            for scheme in schemes:
                for w in widths:
                    h = max(600, round(w * 9 / 16))
                    page = browser.new_page(viewport={"width": w, "height": h},
                                            color_scheme=scheme, reduced_motion="reduce")
                    page.goto(src.as_uri())
                    page.wait_for_timeout(150)
                    shot = out / (f"{src.stem}-{w}" + ("-dark" if scheme == "dark" else "") + ".png")
                    page.screenshot(path=str(shot), full_page=True)
                    shots.append(shot)
                    if scheme == "light":
                        results[w] = page.evaluate(MEASURE, {"pad": INNER_PAD, "figShare": FIG_SHARE})
                    page.close()
            browser.close()
    except Exception as e:  # noqa: BLE001
        print(f"描画に失敗した: {e}", file=sys.stderr)
        return 3

    narrow, wide = min(widths), max(widths)
    small: dict[int, list] = {}
    big: dict[int, list] = {}
    probs: dict[tuple, tuple] = {}
    for w in widths:
        m = results[w]
        if m["gutter"] is None:
            r.fail(".deck が無い。skeleton.html の骨格を使う")
        else:
            exp = expected_gutter(w)
            if any(abs(g - exp) > 1.0 for g in m["gutter"]):
                r.fail(f"画面 {w}px: 左右の余白が {m['gutter'][0]:.0f} / {m['gutter'][1]:.0f}px"
                       f"（deck.css どおりなら {exp:.0f}px）。余白を書き換えている")
        for o in m["overflow"]:
            r.fail(f"画面 {w}px: ページが横にはみ出す（<{o['tag']}> {o['cls']} の右端が "
                   f"{o['right']}px、「{o['text']}」）。幅の決め打ちか、折り返せない長い語がある")
        for hd in m["headings"]:
            if hd["lastChars"] < 2.5:
                r.warn(f"画面 {w}px: 見出し「{hd['text']}」の最後の行が約 {hd['lastChars']:.0f} 字だけになる。"
                       "言い回しを詰めるか、区切りのいい所で読点を入れる")
        for f in m["figures"]:
            if f["inBox"]:
                r.warn(f"図{f['i']}: .pair / .card の中にあり、幅が {f['width']:.0f}px しかない。"
                       "図は紙面の幅いっぱいに置く")
            if w == 1600 and f["tall"]:
                r.warn(f"図{f['i']}: 画面 1600px で高さ {f['height']:.0f}px、画面の縦の {f['share']:.0%}。"
                       "見出しと一緒に1画面に収まらない")
        for t in m["texts"]:
            key = (t["fig"], t["text"])
            if w == narrow and t["px"] < LEGIBLE_MIN:
                small.setdefault(t["fig"], []).append((t["px"], t["text"]))
            if w == wide and t["px"] > m["body"] * TOO_BIG:
                big.setdefault(t["fig"], []).append((t["px"], t["text"], m["body"]))
            if t["problem"]:
                probs.setdefault(key, (t["problem"], []))[1].append(w)

    # 1文字ずつ・幅ごとに並べると数十行になって読まれないので、図ごとにまとめる。
    for fig, hits in sorted(small.items()):
        px, head = min(hits)
        r.fail(f"図{fig}: {len(hits)} 件の文字が画面 {narrow}px で {LEGIBLE_MIN:g}px を割る"
               f"（最小 {px:.1f}px「{head}」）。font-size を 18 以上にする")
    for fig, hits in sorted(big.items()):
        px, head, body = max(hits)
        r.warn(f"図{fig}: {len(hits)} 件の文字が画面 {wide}px で本文（{body:g}px）の {TOO_BIG:g} 倍を超える"
               f"（最大 {px:.0f}px「{head}」）。図だけが浮く")
    for (fig, head), (pb, ws) in probs.items():
        at = "・".join(map(str, ws)) + "px"
        where = f"図{fig}「{head}」"
        if pb["kind"] == "box":
            r.fail(f"{where}: 箱からはみ出す（約 {pb['over']:.0f} 単位、箱の幅 {pb['boxW']:.0f}、画面 {at}）")
        elif pb["kind"] == "edge":
            r.fail(f"{where}: 図の端を越えて切れる（約 {pb['over']:.0f} 単位、画面 {at}）")
        else:
            r.fail(f"{where}: <{pb['tag']}> と重なる（約 {pb['over']:.0f} 単位、画面 {at}）。"
                   "長いラベルはバーの上に置く（figures.md 4b）")

    print(f"撮影: {src.name}  画面の幅 {' / '.join(map(str, widths))}px")
    for w in widths:
        m = results[w]
        px = [t["px"] for t in m["texts"]]
        span = f"図中の文字 {min(px):.1f}〜{max(px):.1f}px" if px else "図なし"
        print(f"  {w}px: 余白 {expected_gutter(w):.0f}px / 本文 {m['body']:g}px / {span}")
    print("-" * 68)
    for m in r.fails:
        print(f"[不適合] {m}")
    for m in r.warns:
        print(f"[警告]   {m}")
    if not r.fails and not r.warns:
        print("測れる範囲では問題なし。スクリーンショットを目で見る")
    print("-" * 68)
    print(f"不適合 {len(r.fails)} / 警告 {len(r.warns)}")
    print("スクリーンショット:")
    for s in shots:
        print(f"  {s}")
    return 2 if r.fails else (1 if r.warns else 0)


if __name__ == "__main__":
    sys.exit(main())
