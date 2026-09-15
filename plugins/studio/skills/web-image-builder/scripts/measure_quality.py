#!/usr/bin/env python3
"""文字の劣化具合を実測する。
  1) エッジ鋭度  : 文字の輪郭が何ピクセルに滲んでいるか。1.00=1px内で立ち上がる理想値。
                   0.50なら2px、0.33なら3pxに滲んでいる。リサイズや再圧縮を経ると下がる。
  2) 字高        : 実際に描かれた文字の高さ(px)と、キャンバス高さに対する比率。
  3) Slack実効字高: 幅360pxに縮小したとき、文字が何pxで表示されるか。
                   日本語は9px未満で判読困難、12px以上で快適。
"""
import sys, numpy as np
from PIL import Image

def gray(p):
    return np.asarray(Image.open(p).convert("L"), dtype=np.float64)

def text_band(a):
    """行ごとのインク量から、最も文字が密集している帯を選ぶ。"""
    d = np.abs(np.diff(a, axis=1))
    energy = (d > 40).sum(axis=1).astype(float)
    H = len(energy)
    k = max(H // 12, 8)
    ker = np.ones(k) / k
    sm = np.convolve(energy, ker, mode="same")
    c = int(np.argmax(sm))
    lo, hi = max(0, c - k), min(H, c + k)
    return lo, hi

def edge_sharpness(a, lo, hi, thr=45):
    """|一階微分|のピーク / その周辺の実コントラスト。1.0で1px立ち上がり。"""
    band = a[lo:hi]
    ratios = []
    for row in band:
        d = np.abs(np.diff(row))
        for x in range(2, len(d) - 2):
            if d[x] < thr:                       continue
            if d[x] < d[x-1] or d[x] < d[x+1]:   continue   # 局所ピークだけ
            w = row[max(0, x-3):x+4]
            contrast = w.max() - w.min()
            if contrast < thr:                   continue
            ratios.append(d[x] / contrast)
    return (float(np.mean(ratios)), len(ratios)) if ratios else (float("nan"), 0)

def glyph_height(a, lo, hi):
    """帯の中でインクのある行の連続区間 = 1行の文字の縦の広がり。"""
    band = a[lo:hi]
    ink = ((np.abs(np.diff(band, axis=1)) > 40).sum(axis=1) > 2)
    runs, cur = [], 0
    for v in ink:
        if v: cur += 1
        elif cur: runs.append(cur); cur = 0
    if cur: runs.append(cur)
    return max(runs) if runs else 0

def report(path, label):
    a = gray(path)
    H, W = a.shape
    lo, hi = text_band(a)
    sharp, n = edge_sharpness(a, lo, hi)
    gh = glyph_height(a, lo, hi)

    # Slack のリンク展開幅(約360px)に縮小したときの実効字高
    im = Image.open(path).convert("L")
    sw = 360
    small = np.asarray(im.resize((sw, max(1, round(H * sw / W))), Image.LANCZOS), dtype=np.float64)
    slo, shi = text_band(small)
    s_sharp, _ = edge_sharpness(small, slo, shi, thr=25)
    s_gh = glyph_height(small, slo, shi)

    print(f"{label:34} {W}x{H:<6} 鋭度{sharp:5.2f}(n={n:5d})  字高{gh:4d}px({gh/H*100:4.1f}%)"
          f"   360px時: 字高{s_gh:3d}px 鋭度{s_sharp:5.2f}")
    return dict(label=label, sharp=sharp, gh=gh, ghp=gh/H*100, s_gh=s_gh, s_sharp=s_sharp)

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p, label = arg.split("::")
        report(p, label)
