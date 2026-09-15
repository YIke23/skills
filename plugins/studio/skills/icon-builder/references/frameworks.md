# 設置方法（フレームワーク別）

## 前提: なぜ「置くだけ」では効かないのか

ブラウザは、サイトの `<head>` に書かれた `<link rel="icon" ...>` を見てアイコンを探す。
ファイルを置いただけでは「そこにアイコンがある」と分からない。
ただし `favicon.ico` だけは例外で、サイトのルート（`https://example.com/favicon.ico`）に
置けばブラウザが自動で探しに行く。**この暗黙の挙動に頼るとSVGもmanifestも使えない**ので、
必ずタグを書く。

`build_icons.py` は `--framework` に応じた手順を `dist/INSTALL.md` に出す。
ここはその背景と、判断に迷うところの説明。

## 基本形（素のHTML / Laravel Blade / EJS / WordPress など）

`web/` の中身を公開フォルダの直下に置き、`<head>` に4行:

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
```

**`sizes="32x32"` は飾りではない。** これが無いとChromeがSVGよりICOを選んでしまう
既知の不具合がある。付けると意図どおりSVGが使われる。

もう書かなくてよくなったもの: Windowsタイル用の各種 `msapplication-*`、
Safari pinned tab の `mask-icon`、`rel="shortcut icon"`。
最後のものはそもそも仕様上存在しない関係値で、20年以上コピペで生き延びているだけ。

「公開フォルダ」はフレームワークによって名前が違う。Laravelは `public/`、
Viteも `public/`、WordPressはテーマフォルダかサイトルート、素のHTMLなら `index.html` と同じ階層。

## Next.js（App Router）

Next.jsは「決まった名前のファイルを決まった場所に置くと、タグを自動生成する」仕組みを持つ。
**自分で `<link>` を書かない。**

```
app/favicon.ico          ← web/favicon.ico
app/icon.svg             ← web/icon.svg
app/apple-icon.png       ← web/apple-touch-icon.png   ★リネームが必要
public/icon-192.png
public/icon-512.png
public/icon-mask.png
app/manifest.webmanifest ← web/manifest.webmanifest
```

`app/` 直下ではファイル名が意味を持つので、`apple-touch-icon.png` ではなく
**`apple-icon.png`** にリネームする。ここを間違えると何も起きず、原因も分かりにくい。

`public/` に置いたものはURLがそのままになるので、manifest内のパス（`/icon-192.png` など）と一致する。

## Next.js（Pages Router）/ Nuxt / Vite / Astro

いずれも `public/` に置いて、フレームワークのheadに4行を書く形。書き方だけが違う。

- Pages Router: `pages/_document.tsx` の `<Head>`
- Nuxt: `nuxt.config.ts` の `app.head.link`
- Vite: `index.html` の `<head>`
- Astro: レイアウトの `<head>`

具体的なコードは `dist/INSTALL.md` に出る。

## WordPress

管理画面の「外観 → カスタマイズ → サイト基本情報 → サイトアイコン」は
**512pxのPNGを1枚しか受け付けない。** SVGもmanifestも設定できないので、
SVGの鮮明さを活かしたいなら子テーマの `functions.php` から `wp_head` に出力する。
両方やると二重に出るので、カスタマイザー側は空にしておく。

## サブディレクトリで公開している場合

`https://example.com/blog/` のようにサイトがサブディレクトリにあるなら、
`build_icons.py --base-path /blog` を指定する。manifest内のアイコンURLがそこを向く。
`<link>` のhrefも同様に `/blog/...` にする。

## 確認のしかた

- **ブラウザのキャッシュはfaviconに関して特にしぶとい。** シークレットウィンドウで見る
- iOSのホーム画面追加は `apple-touch-icon.png` を見る。manifestではない
- Androidのホーム画面はmanifestの `purpose: "maskable"` を見る
- タブに出ない場合、まず `<link>` のパスをブラウザで直接開いて404でないか確かめる。
  9割はパスの間違いで、アイコン自体の問題ではない
