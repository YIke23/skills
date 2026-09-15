# バッチ、背景生成、ブランド適用

## 複数枚をまとめて作る（`--spec`）

同じキャンペーンを複数サイズに展開するとき、1枚ずつコマンドを打つとパラメータがずれる。
`shared` に共通設定を書き、`images` で差分だけ上書きする。

```json
{
  "shared": {
    "bg": "assets/bg.jpg",
    "logo": "assets/logo.svg",
    "font": "assets/BrandSans-Bold.otf",
    "accent": "#4da3ff",
    "meta": "Mediowl Tech Blog",
    "overlay": 0.82,
    "divider": "rule"
  },
  "images": [
    { "preset": "ogp",    "title": "見積り精度を上げる3つの型", "out": "out/ogp.png" },
    { "preset": "square", "title": "見積り精度を上げる3つの型", "out": "out/ig.png" },
    { "preset": "story",  "title": "見積り精度を上げる3つの型", "out": "out/story.png" },
    { "preset": "banner", "title": "無料相談はこちらから", "cta": "申し込む",
      "out": "out/banner.png" }
  ]
}
```

```bash
python3 scripts/build_image.py --spec spec.json
```

判定は1枚ごとに表示される。1枚でも `overflow` があれば exit code 2 で落ちるので、
CIやMakefileに組み込んでも壊れた画像が通り抜けない。

記事一覧からOGPを一括生成する場合は、記事データ（CSV、JSON、CMSのAPI）から
この `spec.json` を生成するスクリプトを別途書き、`--spec` に渡すのが素直。

## 背景を画像生成AIで作るときのプロンプト指針

**必ず「文字を入れない」と明示する。** 生成された文字は修正できず、こちらで描く文字と競合する。

指定すべきこと:

- **文字を入れない**（"no text, no letters, no typography, no watermark"）
- **出力寸法より大きく、近い比率で**。OGP(1.905:1)に最も近い標準比率は16:9。
  16:9 で 2048×1152 以上を出し、`cover` で縮小クロップさせる。**拡大は絶対に避ける**
- **片側を空ける**か、**全体を暗め・低コントラストに**する。
  文字を乗せる前提なので、主題が中央に密集した絵は使いにくい。
  「左半分は暗く空いている」「中央に被写体を置かない」のように構図を指定する
- 質感・色調・雰囲気はブランドに合わせて指定する。ここは生成モデルが得意な領域

生成後、`--overlay` で背景を沈める濃さを調整する。既定 0.82 で大抵読めるが、
明るい背景なら 0.88 前後まで上げる。逆に背景を見せたいなら 0.7 程度まで下げ、
必ず縮小表示（`presets.md` の比率）を想定して可読性を確認する。

## 日本語の改行位置を制御する

日本語は単語の区切りが無いので、ブラウザは禁則以外のほぼ任意の位置で折り返す。
その結果「無料診断は／じめました」のように語中で切れることがある。
短いキャッチコピーほど目立つので、意味の切れ目で改行したいときは**改行文字を明示する**。

```bash
python3 scripts/build_image.py --preset square --title $'無料診断\nはじめました' ...
```

`spec.json` なら JSON の `\n` がそのまま使える。

```json
{ "preset": "square", "title": "無料診断\nはじめました", "out": "out/ig.png" }
```

空白を入れるだけでは効かない。`text-wrap:balance` が行長を揃えるために別の位置を選ぶため、
空白は行中に残ったまま意図しない場所で折り返される。実測で確認済み。

改行を明示した場合も自動縮小は効くので、長すぎれば文字サイズが下がる。
`shrunk-to-min` が出たら改行の入れ方か文字数を見直すサイン。

## ブランドに寄せる

### フォント

`--font` に自社フォントのTTF/OTF/TTCを渡す。埋め込まれるので、実行環境にインストールされていなくても良い。
`--weight` で太さを合わせる（既定700）。

ライセンスの確認を忘れないこと。フォントを base64 で画像生成用HTMLに埋め込む行為は
Webフォント配信ではなく画像生成の一工程だが、埋め込み配布を禁じるライセンスもある。
生成物（PNG）の利用に制限が及ぶことは通常ないが、フォントファイル自体をリポジトリに
コミットする場合は再配布条項を確認する。

### 色とレイアウトの微調整

まず `--accent` `--fg` `--bg-color` `--meta-color` `--overlay` で足りるか試す。
足りなければ `--extra-css` にCSSファイルを渡す。既定のテンプレートの後ろに追記されるので、
セレクタを上書きするだけで済む。

```css
/* brand.css */
h1        { letter-spacing: .02em; line-height: 1.24; }
.meta     { font-weight: 500; opacity: .95; }
.badge    { border-radius: 2px; letter-spacing: .18em; }
.bar      { width: 200px; height: 8px; }
.card::before { background: linear-gradient(90deg, rgba(12,20,40,.92), rgba(12,20,40,.55)); }
```

```bash
python3 scripts/build_image.py --preset ogp --title "..." --extra-css brand.css --out ogp.png
```

案件ごとに固定の設定が固まったら、`shared` にまとめた `spec.json` をリポジトリに置き、
タイトルだけ差し替えて回すのが運用として一番壊れにくい。

### テンプレート自体を増やす

3つのレイアウト（`standard` / `centered` / `strip`）で足りない構成が必要になったら、
`scripts/build_image.py` の `build_html()` に分岐を追加する。追加するときの約束事:

- 文字ボックス（`.titlebox`）の高さは**中身に依存させない**。
  自動縮小は「ボックスの高さは固定、文字サイズを探す」という前提で動くので、
  中身で高さが変わると探索が循環して壊れる。
  固定寸法の親に対する `height: N%` か `flex: 1 1 auto` のどちらかにする。
- 寸法は `U = sqrt(W*H)` を基準に比率で書く。
  この1本で 300×250 から 1080×1920 まで比率が崩れない。ピクセル決め打ちを混ぜないこと。
