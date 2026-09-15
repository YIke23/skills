# HTML出力の規約

## 見た目は `assets/base.css` で固定

**Soft Slate で固定**。毎回作り直さない。`assets/base.css` の中身を `<style>` に
そのまま貼り、必要な分だけ足す。色は全組み合わせをライト/ダーク両方で測ってあるので、
値を勝手に変えない。変えたくなったら
`python3 ${CLAUDE_SKILL_DIR}/scripts/check_palette.py ${CLAUDE_SKILL_DIR}/assets/base.css`
で測り直してから変える。

**`eli15` や `meeting-deck` の CSS を流用しない。** あちらは Warm Paper で、
長い文章を通して読ませるための組版。導入ガイドは読み物ではなく作業台で、
コンソールとエディタを行き来しながら「今どの手順にいるか」を何度も探し直す
読まれ方をする。淡い地の上に白いカードを置くのは、手順の1つ1つが独立した面になり、
拾い読みでも「3番まで終わった」が目で分かるため。

決まりごとは4つ。

- **1手順 = 1カード**: `.steps > .step`。番号は塗りつぶした円で出す。
  手順の中でいちばん探されるのが番号なので、ここだけはアクセントを使い切ってよい
- **色には役割を持たせる**: `--accent` が「ここを見る・行き先」（リンクと手順番号）、
  `--warn` が「ここでつまずく」、`--danger` が「お金が動く・鍵が漏れる」。
  役割を決めずに散らすと、警告と手順の区別が付かなくなる
- **危険は2つだけ**: `--danger` を使ってよいのは課金が始まるときと秘密が漏れるときだけ。
  ここを増やすと、本当に危ないところで誰も読まなくなる
- **表は横スクロールに逃がす**: 無料枠とプランの比較が必ず入る。
  縮小して全列を入れると、その瞬間に誰も読めない表になる

## `data-*` 属性の契約

`check_guide.py` はこの属性を見ている。属性が無いと検証が素通りする。

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
    <span class="evidence">実画面で確認 ・ 2026-08-30</span>
  </li>

  <li class="step"
      data-evidence="docs"
      data-source="https://docs.example.com/reference/cli"
      data-verified="2026-08-30">
    <pre><code>npx example-cli@2.14 login</code></pre>
    ブラウザが開いて承認を求められる。ターミナルに <code>Logged in</code> と出れば成功。
    <span class="evidence">公式ドキュメントのみ ・ 2026-08-30</span>
  </li>
</ol>
```

守ること:

- `class="step"` が無い `<li>` は手順として検査されない。**UI操作を含む記述は必ず `step` にする**
- `data-evidence` は `console`（実画面を読んだ） / `screenshot`（画像で確認した） /
  `docs`（公式ドキュメントのみ、実画面は未確認）のいずれか。**証拠の等級を隠さない**。
  読者にも見えるように `.evidence` で本文に出す
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
- **外部フォントを読み込まない。** Google Fonts を1行足した時点で、
  配布先やオフラインで書体が黙って崩れる。`base.css` のスタックで足りる
- CSSとJSは同じファイル内に書く。JSは基本的に不要
- `<html lang="ja">`、`<meta name="viewport" …>` を入れる

## 図の色

**SVGに色を直書きしない。** `fill="#2563EB"` と書くとダークモードで別物になる。
クラスを当てて CSS 変数で塗る。使えるのは次の11個。

| クラス | 何を塗るか |
|---|---|
| `.box` | 面。中立。登場人物・要素 |
| `.box-a` | 面。今回の中心。見てほしいところ |
| `.box-w` | 面。問題・注意 |
| `.group` | 囲い。まとまりの境界（塗らず、破線で囲う） |
| `.t` | 地・`.box` の上の文字 |
| `.t-sub` | 補助・単位・注 |
| `.t-em` | 地の上で1語だけ強める |
| `.t-a` `.t-w` | `.box-a` `.box-w` の面の上の文字 |
| `.ln` `.ar` | 線と矢じり |

```html
<svg viewBox="0 0 240 120" role="img" aria-label="キーの流れ">
  <rect class="box" x="8" y="8" width="90" height="50" rx="6"/>
  <text class="t" x="53" y="38" text-anchor="middle">ブラウザ</text>
</svg>
```

**面と文字は対で使う。** `.box-a` の上は `.t-a`、`.box-w` の上は `.t-w`。
地の上の色文字（`.t-sub` `.t-em`）を色面に載せると、その瞬間に 4.5:1 を割る。

**囲いは `.group`。** 何かが何かを含んでいることを示すときは、塗らずに破線で囲う。
外枠を塗ると、内側に置いた面と重なって、どちらが囲いなのか分からなくなる。

`currentColor` と `var(--…)` は使ってよい。検査に引っかかるのは `#rrggbb` と `rgb()` の直書き。

## 骨格

`assets/base.css` を `<style>` に貼ったうえで、本体はこの形にする。
見出しの文言は自由でよい。**変えてはいけないのは `data-section` の値**。

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>はじめての〈サービス名〉</title>
<style>/* ここに assets/base.css の中身をそのまま貼る */</style>
</head>
<body>
<main class="sheet">

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

</main>
</body>
</html>
```
