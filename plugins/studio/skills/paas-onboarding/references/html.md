# HTML出力の規約

## まず確認すること

**`eli15` スキルが同じ環境にあるなら、その HTML 規約と `assets/base.css` を流用する。**
見た目の定義を二重に持つと、片方だけ直したときに静かにズレる。
このファイルの骨格は、`eli15` が無い環境のためのフォールバック。

流用する場合も、下の **`data-*` 属性の契約だけは必ず守る**。
`check_guide.py` はこの属性を見ているので、属性が無いと検証が素通りする。

## `data-*` 属性の契約

### セクション

```html
<section data-section="vocab">
  <h2>覚える言葉</h2>
  …
</section>
```

`data-section` の値は `what` / `vocab` / `pricing` / `hello` / `keys` /
`envsep` / `pitfalls` / `recovery` / `further` のいずれか。
勝手な名前を付けると検証が警告を出す。

### 手順

```html
<ol class="steps">
  <li class="step"
      data-evidence="console"
      data-source="https://console.example.com/project/_/settings/api"
      data-verified="2026-08-30">
    <a href="https://console.example.com/project/_/settings/api">API設定ページ</a> を開く。
    「Project API keys」という見出しの下に2種類のキーが並んでいれば正しい画面。
  </li>

  <li class="step"
      data-evidence="docs"
      data-source="https://docs.example.com/reference/cli"
      data-verified="2026-08-30">
    <pre><code>npx example-cli@2.14 login</code></pre>
    ブラウザが開いて承認を求められる。ターミナルに <code>Logged in</code> と出れば成功。
  </li>
</ol>
```

守ること:

- `class="step"` が無い `<li>` は手順として検査されない。**UI操作を含む記述は必ず `step` にする**
- `data-evidence` は `console`（実画面を読んだ） / `screenshot`（画像で確認した） /
  `docs`（公式ドキュメントのみ、実画面は未確認）のいずれか。**証拠の等級を隠さない**
- 実画面で確定させた場合でも、クリック経路をそのまま書かない。
  鮮度は稼げても寿命は稼げていないので、URLとコマンドに書き直す
- `data-source` は **公式ドメインのhttps URL**。個人記事は不適合
- `data-verified` は **今日の日付**。過去日は「記憶で書いた疑い」として不適合になる
- クリック経路だけの手順は不適合。直リンク（`<a href>`）かコマンド（`<code>`/`<pre>`）を必ず添える
- 画面上の文字列は「」で引用する。引用だと分かる形にしておくと、
  読者が画面内検索でそのまま探せる

`recovery` セクションの中だけは、手順ブロック外のUI記述が許される
（「コンソール右上の検索を使う」のような一般的な案内のため）。

## 単一ファイルの制約

- **外部CDNを参照しない。** `<script src>` `<link href>` `<img src>` に外部URLを書かない。
  検証スクリプトが不適合にする。図が要るなら **インラインSVG**
- CSSとJSは同じファイル内に書く。JSは基本的に不要
- `<html lang="ja">`、`<meta name="viewport" …>` を入れる

## 色とダークモード

```css
:root {
  color-scheme: light dark;
  --bg: #fffdf5;  --fg: #12100c;  --line: #12100c;
  --accent: #ffd23f;  --danger: #ff5c5c;  --muted: #6b6558;
  --card: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14120e;  --fg: #f5f1e6;  --line: #f5f1e6;
    --accent: #ffcf33;  --danger: #ff7a7a;  --muted: #a8a091;
    --card: #1f1c16;
  }
}
```

**SVGに色を直書きしない。** `fill="#ff5c5c"` と書くとダークモードで別物になる。
クラスを当ててCSS変数で塗る:

```html
<svg viewBox="0 0 240 120" role="img" aria-label="キーの流れ">
  <rect class="box" x="8" y="8" width="90" height="50" rx="4"/>
  <text class="label" x="53" y="38" text-anchor="middle">ブラウザ</text>
</svg>
```
```css
svg .box   { fill: var(--card); stroke: var(--line); stroke-width: 3; }
svg .label { fill: var(--fg); font-size: 13px; }
```

`currentColor` と `var(--…)` は使ってよい。検査に引っかかるのは `#rrggbb` と `rgb()` の直書き。

## フォールバック骨格

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>はじめての〈サービス名〉</title>
<style>
:root{color-scheme:light dark;--bg:#fffdf5;--fg:#12100c;--line:#12100c;
--accent:#ffd23f;--danger:#ff5c5c;--muted:#6b6558;--card:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#14120e;--fg:#f5f1e6;--line:#f5f1e6;
--accent:#ffcf33;--danger:#ff7a7a;--muted:#a8a091;--card:#1f1c16}}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px 64px;background:var(--bg);color:var(--fg);
font-family:system-ui,"Hiragino Sans","Noto Sans JP",sans-serif;
line-height:1.8;max-width:720px;margin-inline:auto}
h1{font-size:1.9rem;line-height:1.35;border-bottom:5px solid var(--line);padding-bottom:12px}
h2{font-size:1.3rem;margin-top:48px;background:var(--accent);color:#12100c;
display:inline-block;padding:4px 12px;border:3px solid var(--line);
box-shadow:4px 4px 0 var(--line)}
section{margin-top:8px}
table{width:100%;border-collapse:collapse;margin:16px 0}
th,td{border:2px solid var(--line);padding:8px 10px;text-align:left;font-size:.94rem}
th{background:var(--accent);color:#12100c}
.steps{padding-left:0;list-style:none;counter-reset:s}
.step{counter-increment:s;position:relative;background:var(--card);
border:3px solid var(--line);box-shadow:5px 5px 0 var(--line);
padding:14px 16px 14px 52px;margin:14px 0;border-radius:2px}
.step::before{content:counter(s);position:absolute;left:-3px;top:-3px;
width:36px;height:36px;display:grid;place-items:center;
background:var(--line);color:var(--bg);font-weight:700}
.step code{background:transparent}
pre{background:var(--card);border:2px solid var(--line);padding:10px;
overflow-x:auto;font-size:.88rem}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em}
.warn{border-left:8px solid var(--danger);background:var(--card);
border:3px solid var(--line);padding:12px 14px;margin:16px 0}
.meta{color:var(--muted);font-size:.85rem}
a{color:inherit;text-decoration-thickness:2px;text-underline-offset:3px}
</style>
</head>
<body>

<h1>はじめての〈サービス名〉</h1>
<p class="meta">2026-08-30 時点。手順のうち〈n〉件は実際のコンソール画面で確認し、
〈m〉件は公式ドキュメントのみで確認している（各手順に表示）。
画面が違ったら最後のセクションを見てほしい。</p>

<section data-section="what"><h2>何を任せられるのか</h2></section>
<section data-section="vocab"><h2>先に覚える言葉</h2></section>
<section data-section="pricing"><h2>お金の増え方</h2></section>
<section data-section="hello"><h2>動かすまで</h2>
  <ol class="steps"></ol>
</section>
<section data-section="keys"><h2>キーの置き場所</h2></section>
<section data-section="envsep"><h2>開発と本番を分ける</h2></section>
<section data-section="pitfalls"><h2>最初の一週間で踏む地雷</h2></section>
<section data-section="recovery"><h2>画面が違ったら</h2></section>
<section data-section="further"><h2>もっと知りたい人へ</h2></section>

</body>
</html>
```

見出しの文言は骨格の通りでなくてよい。**変えてはいけないのは `data-section` の値**。
