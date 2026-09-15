# アプリアイコン（iOS / Android / PWA）

## PWA

追加コストがほぼゼロで、`--targets web,pwa` の出力がそのままPWAのアイコンになる。
`manifest.webmanifest` の `icons` に3件入る。

```json
{
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icon-mask.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

**`purpose` は分ける。** 1つのアイコンに `"any maskable"` と書くのは仕様上は妥当だが、
maskable用は外周に余白を持つ設計なので、マスクがかからない場面（タスクスイッチャー、
インストールプロンプト）でロゴが小さく余白だらけに見える。`purpose` を省略した場合の
既定値は `any` なので、最初の2件に明示は要らない。

安全域は**中央の直径409pxの円**（W3C仕様: 短辺の40%を半径とする中央の円 → 512×0.4×2＝409.6）。
外周10%は端末によって切られる。

## iOS

### 納品形式は2つあり、排他

**(a) アセットカタログ方式（1024×1024 PNG 1枚）** — 今も有効。Xcodeが全バリエーションを自動生成する。
このスキルの `ios/AppIcon-1024.png` がこれにあたる。

**(b) Icon Composer 方式（`.icon`）** — iOS 26以降の Liquid Glass 表現にするなら必須。
前景/背景のレイヤーを持つ単一ファイルを作り、Xcodeプロジェクトに追加する。

**両立しない。** `.icon` を追加すると既存のアセットカタログのアイコンは無視される。
旧OSで従来の見た目を保ちたいならアセットカタログを使い続ける、というのがAppleの案内。

このスキルは `ios/AppIcon-1024.png` と `ios/layers/{foreground,background}.svg` を出す。
Liquid Glass にする場合は後者を Icon Composer に読み込ませる。

**前景レイヤーには地色を入れない。** プレート型の意匠（角丸の四角に白抜き）をそのまま前景に
入れると、システムが背景レイヤーと重ねたときにプレートが二重になる。
`build_icons.py --mark-svg mark.svg` にマークだけのSVGを渡すと、前景レイヤーがそれになる。
渡さずにプレート型を検出した場合は警告が出る。

### レイヤーを作るときのルール（Apple公式）

- **ソースはSVG優先。** テキストはアウトライン化する（SVGはフォントを保持しない）
- **ぼかし・影・スペキュラ・不透明度・透明度の設定を削除する。** システムが動的に適用するので、
  焼き込むと二重になる
- **背景色・グラデーションはレイヤーから削除**し、背景レイヤーは全面不透明で別に用意する
- **前景は輪郭をはっきりさせる。** ぼけた縁だとシステムの描くハイライトと影が汚くなる
- レイヤーは**最大4グループ**まで

### 角丸を自分で付けない

システムが全レイヤーの縁をマスクして最終形状を作る。iOS/iPadOS/macOSには**正方形のレイヤー**を渡す。
先にマスクをかけると「スペキュラハイライトが壊れ、エッジがギザギザになる」とAppleが明記している。
書き出し時にキャンバスのマスクも出力しない。

### アルファチャンネル

ここは2つの文脈を分けて考える必要がある。

- **アプリ本体のアイコン**: 透過は積極的に使ってよい。重なりと透明感で奥行きを出すのが推奨
- **App Store提出用の1024×1024**: **アルファチャンネルがあると弾かれる**
  （`ERROR ITMS-90717: ... can't be transparent nor contain an alpha channel`）

`build_icons.py` は `ios/AppIcon-1024.png` をアルファ無しのRGBで書き出し（減色もしない）、
`verify_icons.py` がアルファチャンネルの有無を検査する。

### ダーク版・ティント版

**必須ではない。** 用意しなければシステムが自動生成する。自前で用意する場合は、
ティント版はグレースケール、ダーク版は透過背景（システム側の背景を透かす）で作り、
**バリアント間で要素を入れ替えない**（同じ形のまま色だけ変える）。

キャンバスサイズはプラットフォームで異なる: iOS/iPadOS/macOS/visionOS は1024×1024、
watchOS は1088×1088、tvOS は800×480。

## Android

### Adaptive icon

- 全レイヤーを **108×108 dp** にする
- **安全域は中央の 66×66 dp の正方形**（外周18dp×4辺がマスクと視覚効果のための領域）
- ロゴは **48〜66 dp**。66dpを超えると、端末のマスク形状によっては欠ける
- ベクター（VectorDrawable）推奨。ラスタならマスクや背景の影を焼き込まない

Androidの安全域は**円の直径ではなく正方形で定義されている**点に注意。
PWAのmaskable（直径409の円）とは別の基準で、混同すると片方で欠ける。

`build_icons.py` は 432px（xxxhdpi相当）でレイヤーを出す。ベクターで作れば密度別PNGは不要で、
密度別が必要なのはAPI 25以下向けの旧アイコンだけ。それも `res/mipmap-*/ic_launcher.png` として出る。

```xml
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
```

### monochrome（テーマアイコン）

仕様上は任意だが、**Android 16 QPR2 以降は用意しなくてもシステムが自動でテーマ化する。**
放置すると意図しない見た目になるので、ブランド上重要なら自前で用意する。

全面塗りのプレート型からシルエットを取ると**ただの四角**になる。その場合は
`--mark-svg` にマークだけのSVGを渡す（monochromeとadaptive前景の両方に使われる）。
monochromeだけ別の意匠にしたいときは `--mono-svg` で個別に上書きできる。
`build_icons.py` は全面塗りを検出して `--mark-svg` が無ければ警告する。

adaptive icon の前景レイヤーも同じ理由で**マークだけ**にする。背景レイヤーは
`--pad-bg` の単色で別に出るので、前景に地色が入ると二重になる。

### Play Store 用アイコン

| 項目 | 値 |
|---|---|
| サイズ | 512×512 |
| 形式 | 32-bit PNG |
| 色空間 | sRGB |
| 最大容量 | 1024 KB |
| 形状 | **フル正方形**（Playが半径30%の角丸と影を動的に適用する） |

**ドロップシャドウと角丸を自分で付けない。** Playが二重にかける。
アートワーク内部の陰影で奥行きを出すのは問題ない。
バッジ、ランキングや価格の表記、Playのカテゴリを示唆するテキストは禁止。

出典: Apple HIG (App icons) / Apple Developer (Icon Composer, asset catalog) /
Android Developers (Adaptive icons, screendensities) / Google Play icon design specifications /
W3C Web Application Manifest / web.dev (maskable icon)
