#!/usr/bin/env python3
"""paas-onboarding が生成したガイドHTMLを機械検証する。

    python3 check_guide.py guide.html --domain supabase.com
    python3 check_guide.py guide.html --domain stripe.com,stripe.dev --scope hello

終了コード: 0=問題なし / 1=警告あり / 2=不適合
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

# --- 判定に使うパターン -------------------------------------------------

# UI操作を指している表現。これが本文にあるなら、出典付きの手順ブロックの中でなければならない。
UI_LANG = re.compile(
    r"(クリック|タップ|押下|左メニュー|右メニュー|サイドバー|ナビゲーションバー|"
    r"タブを(?:開|選|押)|ダッシュボード上|画面(?:右上|左上|右下|左下)|コンソールを開)"
)

# クリック経路。矢印1個は語彙表や階層説明でも使うので、2個以上の連鎖だけを経路とみなす。
CLICK_PATH = re.compile(r"[^\s<>→]+\s*→\s*[^\s<>→]+\s*→")


def looks_like_ui(text: str) -> bool:
    return bool(UI_LANG.search(text) or CLICK_PATH.search(text))

# 将来必ず嘘になる書き方。
STALE_CLAIMS = re.compile(
    r"(最新の(?:UI|画面|コンソール|バージョン)|現在のUI|今のコンソール|"
    r"変わっていません|変更されていません|はずです|と思われます)"
)

# 出典として弱いドメイン（UI手順には使えない）。
WEAK_SOURCES = (
    "qiita.com", "zenn.dev", "note.com", "medium.com", "stackoverflow.com",
    "reddit.com", "dev.to", "hatenablog.com", "youtube.com", "twitter.com", "x.com",
)

EVIDENCE_LEVELS = ("console", "screenshot", "docs")

# 画面から拾ってしまいがちな秘密情報。プレースホルダは除外する。
SECRETS = (
    ("Stripe秘密鍵", re.compile(r"\b[sr]k_(live|test)_[A-Za-z0-9]{16,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("Google APIキー", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("AWSアクセスキー", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHubトークン", re.compile(r"\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("秘密鍵ブロック", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
PLACEHOLDER = re.compile(r"(x{6,}|X{6,}|\.\.\.|…|YOUR|your_|<[^>]*>|\*{4,})")

REQUIRED_SECTIONS = ["what", "vocab", "keys", "recovery", "further"]
SCOPE_SECTIONS = {
    "overview": [],
    "hello": ["hello"],
    "production": ["hello", "pricing", "envsep", "pitfalls"],
}

STEP_RE = re.compile(
    r"<li\b(?=[^>]*\bclass=\"[^\"]*\bstep\b)([^>]*)>(.*?)</li>", re.S | re.I
)
ATTR_RE = re.compile(r"([\w-]+)\s*=\s*\"([^\"]*)\"")
TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    @property
    def code(self) -> int:
        if self.fails:
            return 2
        return 1 if self.warns else 0


def strip_tags(html: str) -> str:
    return TAG_RE.sub(" ", html)


def attrs_of(raw: str) -> dict[str, str]:
    return {k.lower(): v for k, v in ATTR_RE.findall(raw)}


def label(step_text: str, index: int) -> str:
    head = " ".join(strip_tags(step_text).split())[:40]
    return f"手順{index}「{head}…」"


# --- 個別の検査 ---------------------------------------------------------

def check_self_contained(html: str, r: Report) -> None:
    """外部CDN・外部アセットへの依存を検出する（<a href> は対象外）。"""
    for tag, attr in (("script", "src"), ("link", "href"), ("img", "src")):
        pattern = re.compile(rf"<{tag}\b[^>]*\b{attr}\s*=\s*\"(https?:)?//[^\"]+\"", re.I)
        for m in pattern.finditer(html):
            r.fail(f"外部アセットを参照している（<{tag}>）: {m.group(0)[:80]}")
    if re.search(r"@import\s+url\(\s*[\"']?(https?:)?//", html, re.I):
        r.fail("CSSが外部を @import している")


def check_dark_mode(html: str, r: Report) -> None:
    if "color-scheme" not in html:
        r.warn("`color-scheme: light dark` の宣言が無い")
    for m in re.finditer(r'(fill|stroke)\s*=\s*"(#[0-9a-fA-F]{3,8}|rgba?\([^"]*\))"', html):
        r.fail(f"SVGに色を直書きしている（クラス+CSS変数にする）: {m.group(0)}")


def check_sections(html: str, scope: str, r: Report) -> None:
    found = set(re.findall(r'\bdata-section\s*=\s*"([^"]+)"', html))
    required = list(REQUIRED_SECTIONS) + SCOPE_SECTIONS.get(scope, [])
    for name in required:
        if name not in found:
            r.fail(f'必須セクションが無い: data-section="{name}"')
    unknown = found - set(REQUIRED_SECTIONS) - {s for v in SCOPE_SECTIONS.values() for s in v}
    for name in sorted(unknown):
        r.warn(f'未定義のセクション名: data-section="{name}"')


def check_steps(html: str, domains: list[str], today: str, r: Report) -> list[tuple[str, str]]:
    steps = STEP_RE.findall(html)
    if not steps:
        return []

    for i, (raw_attrs, body) in enumerate(steps, 1):
        a = attrs_of(raw_attrs)
        name = label(body, i)

        source = a.get("data-source", "").strip()
        verified = a.get("data-verified", "").strip()

        if not source:
            r.fail(f"{name}: data-source が無い（出典なしの手順は出せない）")
        else:
            host = (urlparse(source).hostname or "").lower()
            if not source.startswith("https://"):
                r.fail(f"{name}: data-source が https:// でない → {source}")
            elif any(host == w or host.endswith("." + w) for w in WEAK_SOURCES):
                r.fail(f"{name}: UI手順の出典に個人記事/フォーラムを使っている → {host}")
            elif domains and not any(host == d or host.endswith("." + d) for d in domains):
                r.fail(f"{name}: 公式ドメイン外を出典にしている → {host}")

        evidence = a.get("data-evidence", "").strip()
        if not evidence:
            r.fail(f"{name}: data-evidence が無い（console / screenshot / docs のどれか）")
        elif evidence not in EVIDENCE_LEVELS:
            r.fail(f"{name}: data-evidence の値が不正 → {evidence}")

        if not verified:
            r.fail(f"{name}: data-verified（取得日）が無い")
        elif not DATE_RE.match(verified):
            r.fail(f"{name}: data-verified の書式が YYYY-MM-DD でない → {verified}")
        else:
            gap = abs((date.fromisoformat(verified) - date.fromisoformat(today)).days)
            if gap > 1:
                r.fail(f"{name}: 取得日が今日({today})から{gap}日ずれている → {verified}。"
                       "記憶で書いていないか確認する")

        text = strip_tags(body)
        has_link = re.search(r'href\s*=\s*"https://', body, re.I) is not None
        has_cmd = re.search(r"<code\b|<pre\b", body, re.I) is not None

        if looks_like_ui(text) and not (has_link or has_cmd):
            r.fail(f"{name}: クリック経路だけで、直リンクURLもコマンドも無い")
        if looks_like_ui(text) and "「" not in text:
            r.warn(f"{name}: 画面ラベルを「」で引用していない（引用だと分かる形にする）")

    return steps


def check_ui_outside_steps(html: str, steps: list[tuple[str, str]], r: Report) -> None:
    """UI操作の記述が、出典付きの手順ブロックの外に書かれていないか。"""
    body = html
    for _, inner in steps:
        body = body.replace(inner, " ", 1)
    body = re.sub(r"<(pre|code|script|style)\b.*?</\1>", " ", body, flags=re.S | re.I)
    # 語彙表（階層説明で矢印を使う）と復旧セクション（一般的な案内が許される）は対象外
    for name in ("recovery", "vocab"):
        body = re.sub(rf'<section\b[^>]*data-section="{name}".*?</section>', " ", body,
                      flags=re.S | re.I)

    text = strip_tags(body)
    hits = sorted({m.start() for p in (UI_LANG, CLICK_PATH) for m in p.finditer(text)})
    reported: list[int] = []
    for pos in hits:
        if any(abs(pos - q) < 60 for q in reported):
            continue
        reported.append(pos)
        around = " ".join(text[max(0, pos - 30): pos + 40].split())
        r.fail(f'UI操作を手順ブロックの外に書いている（<li class="step"> に入れる）: …{around}…')


def check_secrets(html: str, r: Report) -> None:
    """画面から拾った鍵やトークンが混入していないか。"""
    for name, pattern in SECRETS:
        for m in pattern.finditer(html):
            hit = m.group(0)
            if PLACEHOLDER.search(hit):
                continue
            r.fail(f"{name}らしき文字列が混入している → {hit[:12]}…（値は書かない。"
                   "実物ならローテーションを勧める）")


def check_language(html: str, r: Report) -> None:
    text = strip_tags(re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I))
    for m in STALE_CLAIMS.finditer(text):
        around = " ".join(text[max(0, m.start() - 25): m.start() + 30].split())
        r.warn(f"将来必ず嘘になる書き方（日付で書く）: …{around}…")


# --- 実行 ---------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="PaaS導入ガイドHTMLの検証")
    p.add_argument("path", type=Path)
    p.add_argument("--domain", default="",
                   help="公式ドメイン（カンマ区切り）。例: supabase.com,supabase.io")
    p.add_argument("--scope", default="hello", choices=sorted(SCOPE_SECTIONS))
    p.add_argument("--date", default=date.today().isoformat(),
                   help="取得日として許容する日付（既定: 今日）")
    args = p.parse_args()

    if not args.path.is_file():
        print(f"ファイルが無い: {args.path}", file=sys.stderr)
        return 2

    html = args.path.read_text(encoding="utf-8", errors="replace")
    domains = [d.strip().lower() for d in args.domain.split(",") if d.strip()]
    if not domains:
        print("警告: --domain 未指定のため、出典ドメインの検査は行わない\n")

    r = Report()
    check_self_contained(html, r)
    check_dark_mode(html, r)
    check_sections(html, args.scope, r)
    steps = check_steps(html, domains, args.date, r)
    check_ui_outside_steps(html, steps, r)
    check_secrets(html, r)
    check_language(html, r)

    levels = [attrs_of(a).get("data-evidence", "") for a, _ in steps]
    live = sum(1 for v in levels if v in ("console", "screenshot"))
    if steps and live == 0:
        r.warn("実画面を一度も確認していない（全手順が docs 由来）。"
               "その旨をガイド冒頭に明記しているか確認する")
    elif steps and live < len(steps):
        print(f"証拠: 実画面 {live} 件 / docs のみ {len(steps) - live} 件\n")

    if not steps and args.scope != "overview":
        r.warn('<li class="step"> が1つも無い（手順を含むスコープなのに手順が未検証）')

    print(f"検査: {args.path.name}  手順 {len(steps)} 件  scope={args.scope}  基準日={args.date}")
    print("-" * 60)
    for m in r.fails:
        print(f"[不適合] {m}")
    for m in r.warns:
        print(f"[警告]   {m}")
    if not r.fails and not r.warns:
        print("問題なし")
    print("-" * 60)
    print(f"不適合 {len(r.fails)} / 警告 {len(r.warns)}")
    return r.code


if __name__ == "__main__":
    sys.exit(main())
