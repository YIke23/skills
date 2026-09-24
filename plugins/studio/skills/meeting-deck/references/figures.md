# 図の型

会議資料でよく要る8つの型（横バーは2通り）。**そのまま貼って、文言と数値を差し替えて使う。**
毎回ゼロから座標を決めると時間を溶かすうえ、viewBox を広く取りすぎて文字が縮む事故が出る。

## 目次

| 型 | 伝えたいこと | 見出し |
|---|---|---|
| 1 | 順序・流れ | [横並びのステップ](#1-横並びのステップ) |
| 2 | 比較・対比 | [2カラムの並置](#2-2カラムの並置) |
| 3 | 構造・包含 | [入れ子のボックス](#3-入れ子のボックス) |
| 4 | 量・コストの差 | [横バー](#4-横バー)（4a ラベルが左 / 4b ラベルが上） |
| 5 | 分岐・条件 | [樹形図](#5-樹形図) |
| 6 | 前後の変化 | [before / after](#6-before--after) |
| 7 | 時系列・日程 | [タイムライン](#7-タイムライン) |
| 8 | 登場人物のやりとり | [シーケンス](#8-シーケンス) |

## 共通の約束

**viewBox の幅は 960 で固定する。** 図は紙面の幅いっぱいに伸び縮みし、紙面の幅は
画面の幅で決まる（deck.css は最大幅を置かない）。だから同じ font-size でも、
狭い画面では縮み、広い画面では膨らむ。

| 画面の幅 | 紙面の幅 | 倍率 | 18 | 20 | 22 | 本文 |
|---|---|---|---|---|---|---|
| 800 | 752 | 0.78 | 14.1px | 15.7px | 17.2px | 20px |
| 1280 | 1117 | 1.16 | 20.9px | 23.3px | 25.6px | 20px |
| 1600 | 1360 | 1.42 | 25.5px | 28.3px | 31.2px | 20px |
| 2000 | 1664 | 1.73 | 31.2px | 34.7px | 38.1px | 22.5px |

**font-size は 18 / 20 / 22 の3段だけ使う。** 18 を下回ると 800px の画面で 14px を割り、
22 を超えると 2000px の画面で本文の 1.75 倍を超えて図だけが浮く。
両端とも `check_deck.py` が測る。

| 用途 | font-size |
|---|---|
| 補足・単位・注・枝の条件 | 18 |
| 箱のラベル・数値 | 20 |
| 見出し帯・囲いの名前 | 22 |

viewBox を広げると同じ font-size のまま文字だけが縮む。広い図が要るときは横に伸ばすのではなく、
型を分けるか高さを使う。高さは **420 まで**。超えると 16:9 の画面で図が縦の 6 割を超え、
見出しと一緒に1画面に収まらない。

**`<svg>` に `width` / `height` の属性を付けない。** viewBox だけにする。
属性を付けると、図の大きさがその px で固定されて紙面に合わせて伸び縮みしなくなる。

**文字は箱の中に1行で収める。** 目安は、箱の幅 ÷ font-size − 2 文字（左右の余白の分）。
280 幅の箱に 20 の文字なら 12 字まで。英数字は全角の約 6 割で数える。
収まらないのは、箱に説明を書こうとしているサイン。図の中は名前を置く場所。
はみ出しは `check_deck.py` が文字数から見積もり、`shoot_deck.py` が描画して測る。

**色は属性に直書きせず、クラスで付ける。** `fill="#000000"` はダークモードで
取り残される。使えるのは次の11個だけ。

| クラス | 何を塗るか |
|---|---|
| `.box` | 面。中立。登場人物・工程・要素 |
| `.box-a` | 面。今回の中心。変わるところ・見てほしいところ |
| `.box-w` | 面。問題・注意・期限 |
| `.group` | 囲い。まとまりの境界（塗らず、破線で囲う） |
| `.t` | 地・`.box` の上の文字 |
| `.t-sub` | 補助・単位・注 |
| `.t-em` | 地の上で1語だけ強める |
| `.t-a` `.t-w` | `.box-a` `.box-w` の面の上の文字 |
| `.ln` `.ar` | 線と矢じり |

**面と文字は対で使う。** `.box-a` の上は `.t-a`、`.box-w` の上は `.t-w`。
地の上の色文字（`.t-sub` `.t-em`）を色面に載せると、その瞬間に 4.5:1 を割る。

**面の役割は3つしかない。** 中立（`.box`）、今回の中心（`.box-a`）、問題（`.box-w`）。
**1枚の図で色の付いた面は1種類までにする。** 中立でない面が増えるほど、
「で、どこの話？」になる。色は指し示すためにあるので、指す先は1つでいい。

**囲いは `.group`。** 何かが何かを含んでいることを示すときは、塗らずに破線で囲う。
外枠を塗ると、内側に置いた面と重なって、どちらが囲いなのか分からなくなる。

**矢印に `<marker>` を使わない。** 1ページに図を何枚も置くので、`id` が衝突して
2枚目以降の矢印が消える。`<polygon class="ar">` で直接描く。

**SVG の中で空白を並べて桁を揃えない。** 連続した空白は1つに潰れる。
項目名と値を揃えたいときは、`<text>` を2つに分けて x で揃える（型 2）。

**図は `.pair` や `.card` の中に入れない。** 幅が半分以下になり、文字も半分に縮む。

---

## 1. 横並びのステップ

```html
<figure>
  <svg viewBox="0 0 960 190" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="受付から公開までの3工程">
    <rect class="box"   x="20"  y="30" width="280" height="130"/>
    <text class="t"     x="160" y="84"  font-size="20" text-anchor="middle" font-weight="700">受付</text>
    <text class="t-sub" x="160" y="120" font-size="18" text-anchor="middle">フォームで受け取る</text>

    <path class="ln" d="M302 95 H328"/>
    <polygon class="ar" points="328,88 340,95 328,102"/>

    <rect class="box"   x="340" y="30" width="280" height="130"/>
    <text class="t"     x="480" y="84"  font-size="20" text-anchor="middle" font-weight="700">確認</text>
    <text class="t-sub" x="480" y="120" font-size="18" text-anchor="middle">担当が内容を見る</text>

    <path class="ln" d="M622 95 H648"/>
    <polygon class="ar" points="648,88 660,95 648,102"/>

    <rect class="box-a" x="660" y="30" width="280" height="130"/>
    <text class="t-a"   x="800" y="84"  font-size="20" text-anchor="middle" font-weight="700">公開</text>
    <text class="t-a"   x="800" y="120" font-size="18" text-anchor="middle">本番に反映</text>
  </svg>
  <figcaption>受付から公開までの3工程。色が付いているのが今回変えるところ。</figcaption>
</figure>
```

**要点は、変わる箱だけを `.box-a` にすること。** 全部同じ面だと「で、どこの話？」になる。
4工程を超えるなら、それは1枚の図ではなく節を分ける合図。
箱1つに入るのはラベル 12 字、補足 13 字まで。

## 2. 2カラムの並置

```html
<figure>
  <svg viewBox="0 0 960 280" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="案Aと案Bの比較">
    <rect class="box"   x="20"  y="20" width="440" height="240"/>
    <rect class="box"   x="20"  y="20" width="440" height="52"/>
    <text class="t"     x="240" y="54"  font-size="22" text-anchor="middle" font-weight="700">案A ｜ 自前で作る</text>
    <text class="t-sub" x="46"  y="114" font-size="18">初期費用</text>
    <text class="t"     x="190" y="114" font-size="20">0円</text>
    <text class="t-sub" x="46"  y="156" font-size="18">運用</text>
    <text class="t"     x="190" y="156" font-size="20">月20時間</text>
    <text class="t-sub" x="46"  y="198" font-size="18">開始まで</text>
    <text class="t-w"   x="190" y="198" font-size="20" font-weight="700">3か月</text>
    <text class="t-sub" x="46"  y="238" font-size="18">社内に知見が残る</text>

    <rect class="box"   x="500" y="20" width="440" height="240"/>
    <rect class="box-a" x="500" y="20" width="440" height="52"/>
    <text class="t-a"   x="720" y="54"  font-size="22" text-anchor="middle" font-weight="700">案B ｜ SaaSを使う</text>
    <text class="t-sub" x="526" y="114" font-size="18">初期費用</text>
    <text class="t"     x="670" y="114" font-size="20">40万円</text>
    <text class="t-sub" x="526" y="156" font-size="18">運用</text>
    <text class="t"     x="670" y="156" font-size="20">月2時間</text>
    <text class="t-sub" x="526" y="198" font-size="18">開始まで</text>
    <text class="t"     x="670" y="198" font-size="20" font-weight="700">2週間</text>
    <text class="t-sub" x="526" y="238" font-size="18">仕様変更に追随できない</text>
  </svg>
  <figcaption>案Aと案Bの比較。差が出るのは「開始まで」と「運用」の2行。</figcaption>
</figure>
```

**行の順番を左右で揃える。** 揃っていないと、目が往復して比較そのものができない。
差が出ている行だけ `.t-w` にすると、どこを見ればいいかが一目で決まる。
良い側は色を足さず、太字の `.t` で受ける。両側に色を付けると、どちらが問題なのかが消える。
値の列は x=190 / 670 で揃えてある。項目名は 7 字、値は 12 字まで。

## 3. 入れ子のボックス

```html
<figure>
  <svg viewBox="0 0 960 290" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="社内システムの構成">
    <rect class="group" x="20" y="20" width="920" height="250"/>
    <text class="t-sub" x="44" y="56" font-size="22" font-weight="700">社内システム</text>

    <rect class="box"   x="48"  y="80" width="270" height="164"/>
    <text class="t"     x="183" y="150" font-size="20" text-anchor="middle" font-weight="700">受注</text>
    <text class="t-sub" x="183" y="186" font-size="18" text-anchor="middle">今回は触らない</text>

    <rect class="box-a" x="345" y="80" width="270" height="164"/>
    <text class="t-a"   x="480" y="150" font-size="20" text-anchor="middle" font-weight="700">在庫</text>
    <text class="t-a"   x="480" y="186" font-size="18" text-anchor="middle">ここを入れ替える</text>

    <rect class="box"   x="642" y="80" width="270" height="164"/>
    <text class="t"     x="777" y="150" font-size="20" text-anchor="middle" font-weight="700">配送</text>
    <text class="t-sub" x="777" y="186" font-size="18" text-anchor="middle">APIだけ直す</text>
  </svg>
  <figcaption>社内システムの構成。今回の変更は在庫だけに閉じる。</figcaption>
</figure>
```

**外枠は `.group`（塗らない破線）、中身は `.box`（塗る）。**
外枠を塗ると内側の面と重なり、どちらが囲いなのか分からなくなる。
囲いの名前は `.t-sub` で置く。主役は中の箱であって、囲いではない。

## 4. 横バー

ラベルの長さで2つを使い分ける。**迷ったら 4b（ラベルが上）にする。** 4b はどんな長さの
ラベルでも崩れないが、4a はラベルが 7 字を超えた瞬間にバーと重なる。

### 4a. ラベルが左（全部のラベルが 7 字以内のとき）

```html
<figure>
  <svg viewBox="0 0 960 240" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="工程別の所要時間">
    <text class="t"     x="20"  y="51"  font-size="20">手作業</text>
    <rect class="box"   x="180" y="24"  width="640" height="40"/>
    <text class="t"     x="834" y="51"  font-size="20" font-weight="700">42分</text>

    <text class="t"     x="20"  y="123" font-size="20">半自動</text>
    <rect class="box"   x="180" y="96"  width="274" height="40"/>
    <text class="t"     x="468" y="123" font-size="20" font-weight="700">18分</text>

    <text class="t"     x="20"  y="195" font-size="20">全自動</text>
    <rect class="box-a" x="180" y="168" width="76"  height="40"/>
    <text class="t"     x="270" y="195" font-size="20" font-weight="700">5分</text>

    <text class="t-sub" x="180" y="232" font-size="18">社内計測（2026-09-10、n=20）</text>
  </svg>
  <figcaption>1件あたりの所要時間。全自動は手作業の 1/8。</figcaption>
</figure>
```

ラベルの欄は x=20〜170 の 150 幅。20 の文字で 7 字まで。バーは x=180 から始まり、最長を 640 にする。
バーの右に置く数値は 6 字まで（640 + 14 + 数値で 960 を越えない）。

### 4b. ラベルが上（長いラベル・ラベルの長さがばらつくとき）

```html
<figure>
  <svg viewBox="0 0 960 380" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="月額の見込み">
    <text class="t"     x="20"  y="42"  font-size="20">いまの構成（本番と開発の2つ）</text>
    <rect class="box"   x="20"  y="54"  width="299" height="36"/>
    <text class="t"     x="333" y="80"  font-size="20" font-weight="700">$35</text>

    <text class="t"     x="20"  y="126" font-size="20">1つに減らした場合</text>
    <rect class="box"   x="20"  y="138" width="239" height="36"/>
    <text class="t"     x="273" y="164" font-size="20" font-weight="700">約 $28</text>

    <text class="t"     x="20"  y="210" font-size="20" font-weight="700">今回の提案（新しいアプリを1つ足す）</text>
    <rect class="box-a" x="20"  y="222" width="324" height="36"/>
    <text class="t"     x="358" y="248" font-size="20" font-weight="700">約 $38</text>

    <text class="t"     x="20"  y="294" font-size="20">アプリを5つにした場合（将来）</text>
    <rect class="box"   x="20"  y="306" width="640" height="36"/>
    <text class="t"     x="674" y="332" font-size="20" font-weight="700">約 $75</text>

    <text class="t-sub" x="20"  y="370" font-size="18">料金表から試算（1ドル150円）</text>
  </svg>
  <figcaption>月額の見込み。今回の提案は約 $38 で、5つに増やしても約 $75 に収まる。</figcaption>
</figure>
```

1行 84 の高さに「ラベル → バー」を縦に積む。ラベルはバーと同じ x=20 から始めるので、
どれだけ長くても（920 幅、20 の文字で 46 字まで）バーと重ならない。
バーの最長は 640。右に置く数値は、円換算を併記しても 13 字程度まで入る。
行が5本を超えると高さが 420 を越えるので、そこで表に切り替える。

**どちらの型でも、バーの長さを実数に比例させる。** 42:18:5 なら 640:274:76。
目分量で描くと、図と数字が食い違ったまま会議に出る。**数値には出典を図の中に置く。**
「その数字どこから？」で止まるのを防げる。

## 5. 樹形図

```html
<figure>
  <svg viewBox="0 0 960 270" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="再実行するかどうかの判断">
    <rect class="box" x="330" y="20" width="300" height="70"/>
    <text class="t" x="480" y="63" font-size="20" text-anchor="middle" font-weight="700">失敗を検知</text>

    <path class="ln" d="M480 90 V124 H190 V166"/>
    <path class="ln" d="M480 90 V124 H770 V166"/>
    <polygon class="ar" points="183,166 197,166 190,180"/>
    <polygon class="ar" points="763,166 777,166 770,180"/>
    <text class="t-sub" x="300" y="114" font-size="18" text-anchor="middle">一時的</text>
    <text class="t-sub" x="660" y="114" font-size="18" text-anchor="middle">恒久的</text>

    <rect class="box"   x="40"  y="180" width="300" height="70"/>
    <text class="t"     x="190" y="223" font-size="20" text-anchor="middle">3回まで再実行</text>

    <rect class="box-a" x="620" y="180" width="300" height="70"/>
    <text class="t-a"   x="770" y="223" font-size="20" text-anchor="middle">止めて通知</text>
  </svg>
  <figcaption>失敗を検知したあとの分岐。恒久的な失敗は再実行しない。</figcaption>
</figure>
```

**枝のラベル（「一時的」「恒久的」）を必ず置く。** 条件が書かれていない分岐図は、
見た目は図でも中身は箱の羅列。箱1つに入るのは 13 字まで。

## 6. before / after

```html
<figure>
  <svg viewBox="0 0 960 210" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="承認フローの変更前後">
    <rect class="box"   x="20"  y="30" width="400" height="150"/>
    <text class="t-sub" x="40"  y="66"  font-size="18">いま</text>
    <text class="t"     x="40"  y="108" font-size="20">申請 → 課長 → 部長 → 経理</text>
    <text class="t-w"   x="40"  y="150" font-size="20" font-weight="700">平均 4.2日</text>

    <path class="ln" d="M432 105 H508"/>
    <polygon class="ar" points="508,97 524,105 508,113"/>

    <rect class="box-a" x="540" y="30" width="400" height="150"/>
    <text class="t-a"   x="560" y="66"  font-size="18">変更後</text>
    <text class="t-a"   x="560" y="108" font-size="20">申請 → 部長 → 経理</text>
    <text class="t-a"   x="560" y="150" font-size="20" font-weight="700">平均 1.5日（見込み）</text>
  </svg>
  <figcaption>承認フローの変更前後。課長承認を外し、2.7日短縮する見込み。</figcaption>
</figure>
```

**同じ位置に同じ種類の情報を置く。** 左右で行の意味がずれると、何が変わったのかが読めない。
見込みの数字には「（見込み）」を付ける。実績と並べたまま出すと、会議で必ず突っ込まれる。
箱1つの1行に入るのは 17 字まで。

## 7. タイムライン

```html
<figure>
  <svg viewBox="0 0 960 190" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="導入の日程">
    <path class="ln" d="M60 100 H900"/>
    <polygon class="ar" points="900,92 916,100 900,108"/>

    <circle class="box"   cx="140" cy="100" r="14"/>
    <text class="t"       x="140" y="64"  font-size="20" text-anchor="middle" font-weight="700">10月</text>
    <text class="t-sub"   x="140" y="148" font-size="18" text-anchor="middle">試験導入</text>

    <circle class="box"   cx="420" cy="100" r="14"/>
    <text class="t"       x="420" y="64"  font-size="20" text-anchor="middle" font-weight="700">12月</text>
    <text class="t-sub"   x="420" y="148" font-size="18" text-anchor="middle">2部署へ拡大</text>

    <circle class="box-a" cx="700" cy="100" r="18"/>
    <text class="t-em"    x="700" y="64"  font-size="20" text-anchor="middle" font-weight="700">2月</text>
    <text class="t"       x="700" y="148" font-size="18" text-anchor="middle" font-weight="700">全社展開</text>
  </svg>
  <figcaption>導入の日程。2月の全社展開が、今日決めたい判断の期限。</figcaption>
</figure>
```

**節目は3〜4個まで。** それ以上あるのは日程表であって図ではないので、表にする。
節目の説明は 1つあたり 13 字まで（隣の節目の文字とぶつからない幅）。

## 8. シーケンス

```html
<figure>
  <svg viewBox="0 0 960 270" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="通知が届くまでのやりとり">
    <rect class="box" x="60"  y="20" width="200" height="52"/>
    <text class="t"   x="160" y="53" font-size="20" text-anchor="middle" font-weight="700">利用者</text>
    <rect class="box" x="380" y="20" width="200" height="52"/>
    <text class="t"   x="480" y="53" font-size="20" text-anchor="middle" font-weight="700">アプリ</text>
    <rect class="box" x="700" y="20" width="200" height="52"/>
    <text class="t"   x="800" y="53" font-size="20" text-anchor="middle" font-weight="700">通知基盤</text>

    <path class="ln" d="M160 72 V250" stroke-dasharray="6 6"/>
    <path class="ln" d="M480 72 V250" stroke-dasharray="6 6"/>
    <path class="ln" d="M800 72 V250" stroke-dasharray="6 6"/>

    <path class="ln" d="M160 118 H466"/>
    <polygon class="ar" points="466,111 480,118 466,125"/>
    <text class="t-sub" x="320" y="106" font-size="18" text-anchor="middle">申請する</text>

    <path class="ln" d="M480 176 H786"/>
    <polygon class="ar" points="786,169 800,176 786,183"/>
    <text class="t-sub" x="640" y="164" font-size="18" text-anchor="middle">送信を依頼</text>

    <path class="ln" d="M800 232 H174"/>
    <polygon class="ar" points="174,225 160,232 174,239"/>
    <text class="t-sub" x="480" y="220" font-size="18" text-anchor="middle">メールが届く</text>
  </svg>
  <figcaption>通知が届くまでのやりとり。アプリは依頼するだけで、送信は通知基盤が持つ。</figcaption>
</figure>
```

**登場人物は3つまで、やりとりは4本まで。** 超えたら、その節は図1枚で説明できる粒度を
超えている。節を割るか、詳細を補足に逃がす。矢印の上の説明は、隣り合う2人の間なら 15 字まで。

---

## 型が決まらないとき

内容の形と型が噛み合っていないだけのことが多い。もう一度この対応で引き直す。

| 節が言っていること | 型 |
|---|---|
| AのあとにB、そのあとC | 1 横並びのステップ |
| AとBのどちらを選ぶか | 2 2カラムの並置 |
| Aの中にBとCがある | 3 入れ子のボックス |
| AはBの何倍 / どれだけ多い | 4 横バー（ラベルが長ければ 4b） |
| Aなら X、Bなら Y | 5 樹形図 |
| 今はA、変えるとB | 6 before / after |
| いつ何が起きるか | 7 タイムライン |
| 誰が誰に何を渡すか | 8 シーケンス |

どれにも当てはまらないなら、**その節は図にしない。** 無理に図にすると、本文の箇条書きを
四角で囲んだだけのものが出てくる。それは図ではなく、読む量が増えただけの飾り。
数字が主役なら `.stats`、項目の対照が主役なら表で見せる。
