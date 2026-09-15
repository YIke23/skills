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

**Bauhaus で固定。色は5つしかない。** 赤・黄・青・黒・白。淡い色も中間色も灰色も作らない。
面はベタで塗り、影・グラデーション・角丸を付けない。区切りは罫線と色面が引き受ける。

```css
:root {
  color-scheme: light dark;
  --paper:#FFFFFF; --card:#FFFFFF; --ink:#000000;
  --red:#D42A20;  --yellow:#FFD500; --blue:#0057B8;
  --on-red:#FFFFFF; --on-yellow:#000000; --on-blue:#FFFFFF;
}
/* ダークでも三原色は変えない。明度だけ、黒地で 4.5:1 を通る側へ振る。
 * 黄は元のまま通るので動かさない。赤と青は明るい側に置き、載せる文字が黒に反転する。 */
@media (prefers-color-scheme: dark) {
  :root {
    --paper:#000000; --card:#000000; --ink:#FFFFFF;
    --red:#FF6B57;  --yellow:#FFD500; --blue:#7FB2FF;
    --on-red:#000000; --on-yellow:#000000; --on-blue:#000000;
  }
}
```

色には役割を持たせる。導入ガイドでは、**黄が「ここを見る・ここが変わる」、
赤が「お金と鍵——課金が始まる／秘密を漏らす」、青が補助と行き先（リンク・出典・注記）**。
役割を決めずに三原色を散らすと、警告と手順の区別が付かなくなる。

**黄の面の上は暗い文字のみ。** 明るい文字は 4.5:1 を絶対に通らない。`--on-yellow` を使う。

**SVGに色を直書きしない。** `fill="#D42A20"` と書くとダークモードで別物になる。
クラスを当ててCSS変数で塗る:

```html
<svg viewBox="0 0 240 120" role="img" aria-label="キーの流れ">
  <rect class="box" x="8" y="8" width="90" height="50"/>
  <text class="t" x="53" y="38" text-anchor="middle">ブラウザ</text>
</svg>
```
```css
svg .box   { fill: var(--card);   stroke: var(--ink); stroke-width: 3; }
svg .box-y { fill: var(--yellow); stroke: var(--ink); stroke-width: 3; }
svg .box-r { fill: var(--red);    stroke: var(--ink); stroke-width: 3; }
svg .box-c { fill: var(--blue);   stroke: var(--ink); stroke-width: 3; }
svg .t     { fill: var(--ink);       font-size: 13px; }
svg .t-sub { fill: var(--blue);      font-size: 13px; }
svg .t-y   { fill: var(--on-yellow); font-size: 13px; }
svg .t-r   { fill: var(--on-red);    font-size: 13px; }
svg .t-c   { fill: var(--on-blue);   font-size: 13px; }
```

**面と文字は対で使う。** `.box-y` の上は `.t-y`、`.box-r` の上は `.t-r`、`.box-c` の上は `.t-c`。
地の上の色文字（`.t-sub`）を色面に載せると、その瞬間に 4.5:1 を割る。

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
/* Bauhaus — 色は赤・黄・青・黒・白の5つだけ。影も角丸もグラデーションも使わない。 */
:root{color-scheme:light dark;
--paper:#FFFFFF;--card:#FFFFFF;--ink:#000000;
--red:#D42A20;--yellow:#FFD500;--blue:#0057B8;
--on-red:#FFFFFF;--on-yellow:#000000;--on-blue:#FFFFFF;
--bd:3px;--bd-x:10px}
@media(prefers-color-scheme:dark){:root{
--paper:#000000;--card:#000000;--ink:#FFFFFF;
--red:#FF6B57;--yellow:#FFD500;--blue:#7FB2FF;
--on-red:#000000;--on-yellow:#000000;--on-blue:#000000}}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px 64px;background:var(--paper);color:var(--ink);
font-family:Futura,"Century Gothic","Avenir Next","Hiragino Sans","Noto Sans JP",sans-serif;
line-height:1.8;max-width:720px;margin-inline:auto}
h1{font-size:1.9rem;line-height:1.3;font-weight:900;
border-bottom:var(--bd-x) solid var(--ink);padding-bottom:12px}
h2{font-size:1.3rem;margin-top:48px;background:var(--yellow);color:var(--on-yellow);
display:inline-block;padding:6px 14px;border:var(--bd) solid var(--ink)}
section{margin-top:8px}
table{width:100%;border-collapse:collapse;margin:16px 0}
th,td{border:2px solid var(--ink);padding:8px 10px;text-align:left;font-size:.94rem}
th{background:var(--yellow);color:var(--on-yellow)}
.steps{padding-left:0;list-style:none;counter-reset:s}
.step{counter-increment:s;position:relative;background:var(--card);
border:var(--bd) solid var(--ink);padding:14px 16px 14px 56px;margin:14px 0}
.step::before{content:counter(s);position:absolute;left:0;top:0;
width:40px;height:40px;display:grid;place-items:center;
background:var(--ink);color:var(--paper);font-weight:700}
.step code{background:transparent}
pre{background:var(--card);border:2px solid var(--ink);padding:10px;
overflow-x:auto;font-size:.88rem}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em}
/* 警告は赤。お金が動く・鍵が漏れる、の2つだけに使う。 */
.warn{background:var(--card);border:var(--bd) solid var(--ink);
border-left:var(--bd-x) solid var(--red);padding:12px 14px;margin:16px 0}
.meta{color:var(--blue);font-size:.85rem}
/* 図の色。面（.box-*）と、その面の上に置く文字（.t-*）は必ず対で使う。 */
svg{max-width:100%;height:auto}
svg .box{fill:var(--card);stroke:var(--ink);stroke-width:3}
svg .box-y{fill:var(--yellow);stroke:var(--ink);stroke-width:3}
svg .box-r{fill:var(--red);stroke:var(--ink);stroke-width:3}
svg .box-c{fill:var(--blue);stroke:var(--ink);stroke-width:3}
svg .t{fill:var(--ink);font-size:13px}
svg .t-sub{fill:var(--blue);font-size:13px}
svg .t-y{fill:var(--on-yellow);font-size:13px}
svg .t-r{fill:var(--on-red);font-size:13px}
svg .t-c{fill:var(--on-blue);font-size:13px}
svg .ln{stroke:var(--ink);stroke-width:3;fill:none}
svg .ar{fill:var(--ink)}
a{color:var(--blue);text-decoration:underline;
text-decoration-thickness:2px;text-underline-offset:3px}
:focus-visible{outline:3px solid var(--red);outline-offset:3px}
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
