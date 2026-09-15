# 図の型

会議資料でよく要る8つの型。**そのまま貼って、文言と数値を差し替えて使う。**
毎回ゼロから座標を決めると時間を溶かすうえ、viewBox を広く取りすぎて文字が縮む事故が出る。

## 目次

| 型 | 伝えたいこと | 見出し |
|---|---|---|
| 1 | 順序・流れ | [横並びのステップ](#1-横並びのステップ) |
| 2 | 比較・対比 | [2カラムの並置](#2-2カラムの並置) |
| 3 | 構造・包含 | [入れ子のボックス](#3-入れ子のボックス) |
| 4 | 量・コストの差 | [横バー](#4-横バー) |
| 5 | 分岐・条件 | [樹形図](#5-樹形図) |
| 6 | 前後の変化 | [before / after](#6-before--after) |
| 7 | 時系列・日程 | [タイムライン](#7-タイムライン) |
| 8 | 登場人物のやりとり | [シーケンス](#8-シーケンス) |

## 共通の約束

**viewBox の幅は 960 で固定する。** 紙面が 1152px なので 1.2 倍に引き伸ばされ、
font-size 15 が 18px、17 が 20.4px で出る。ここを勝手に広げると、同じ font-size のまま
文字だけが縮む。広い図が要るときは横に伸ばすのではなく、型を分けるか高さを使う。

| 用途 | font-size | 投影時 |
|---|---|---|
| 箱のラベル | 17 | 20.4px |
| 補足・単位・注 | 15 | 18px |
| 見出し帯の中 | 19 | 22.8px |

**色は属性に直書きせず、クラスで付ける。** `fill="#14213D"` はダークモードで
取り残される。使えるクラスは `.box` `.box-b` `.box-a` `.t` `.t-sub` `.t-a`
`.t-hot` `.t-cool` `.ln` `.ar`。

**琥珀（`.box-a`）の上の文字は必ず `.t-a`。** 明るい文字を載せると 4.5:1 を絶対に通らない。

**矢印に `<marker>` を使わない。** 1ページに図を何枚も置くので、`id` が衝突して
2枚目以降の矢印が消える。`<polygon class="ar">` で直接描く。

---

## 1. 横並びのステップ

```html
<figure>
  <svg viewBox="0 0 960 180" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="受付から公開までの3工程">
    <rect class="box"   x="20"  y="30" width="280" height="120"/>
    <text class="t"     x="160" y="80"  font-size="17" text-anchor="middle" font-weight="700">受付</text>
    <text class="t-sub" x="160" y="110" font-size="15" text-anchor="middle">フォームで受け取る</text>

    <path class="ln" d="M302 90 H328"/>
    <polygon class="ar" points="328,83 340,90 328,97"/>

    <rect class="box"   x="340" y="30" width="280" height="120"/>
    <text class="t"     x="480" y="80"  font-size="17" text-anchor="middle" font-weight="700">確認</text>
    <text class="t-sub" x="480" y="110" font-size="15" text-anchor="middle">担当が内容を見る</text>

    <path class="ln" d="M622 90 H648"/>
    <polygon class="ar" points="648,83 660,90 648,97"/>

    <rect class="box-a" x="660" y="30" width="280" height="120"/>
    <text class="t-a"   x="800" y="80"  font-size="17" text-anchor="middle" font-weight="700">公開</text>
    <text class="t-a"   x="800" y="110" font-size="15" text-anchor="middle">本番に反映</text>
  </svg>
  <figcaption>受付から公開までの3工程。琥珀が今回変えるところ。</figcaption>
</figure>
```

**要点は、変わる箱だけを琥珀にすること。** 全部同じ色だと「で、どこの話？」になる。
4工程を超えるなら、それは1枚の図ではなく節を分ける合図。

## 2. 2カラムの並置

```html
<figure>
  <svg viewBox="0 0 960 260" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="案Aと案Bの比較">
    <rect class="box"   x="20"  y="20" width="440" height="220"/>
    <rect class="box-b" x="20"  y="20" width="440" height="46"/>
    <text class="t"     x="240" y="51" font-size="19" text-anchor="middle" font-weight="800">案A ｜ 自前で作る</text>
    <text class="t"     x="46"  y="108" font-size="17">初期費用   0円</text>
    <text class="t"     x="46"  y="146" font-size="17">運用      月20時間</text>
    <text class="t-hot" x="46"  y="184" font-size="17">開始まで   3か月</text>
    <text class="t-sub" x="46"  y="214" font-size="15">社内に知見が残る</text>

    <rect class="box"   x="500" y="20" width="440" height="220"/>
    <rect class="box-a" x="500" y="20" width="440" height="46"/>
    <text class="t-a"   x="720" y="51" font-size="19" text-anchor="middle" font-weight="800">案B ｜ SaaSを使う</text>
    <text class="t"     x="526" y="108" font-size="17">初期費用   40万円</text>
    <text class="t"     x="526" y="146" font-size="17">運用      月2時間</text>
    <text class="t-cool" x="526" y="184" font-size="17">開始まで   2週間</text>
    <text class="t-sub" x="526" y="214" font-size="15">仕様変更に追随できない</text>
  </svg>
  <figcaption>案Aと案Bの比較。差が出るのは「開始まで」と「運用」の2行。</figcaption>
</figure>
```

**行の順番を左右で揃える。** 揃っていないと、目が往復して比較そのものができない。
差が出ている行だけ `.t-hot` / `.t-cool` で色を変えると、どこを見ればいいかが一目で決まる。

## 3. 入れ子のボックス

```html
<figure>
  <svg viewBox="0 0 960 280" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="社内システムの構成">
    <rect class="box-b" x="20" y="20" width="920" height="240"/>
    <text class="t" x="44" y="52" font-size="19" font-weight="800">社内システム</text>

    <rect class="box" x="48"  y="74" width="270" height="160"/>
    <text class="t"     x="183" y="120" font-size="17" text-anchor="middle" font-weight="700">受注</text>
    <text class="t-sub" x="183" y="152" font-size="15" text-anchor="middle">今回は触らない</text>

    <rect class="box-a" x="345" y="74" width="270" height="160"/>
    <text class="t-a"   x="480" y="120" font-size="17" text-anchor="middle" font-weight="700">在庫</text>
    <text class="t-a"   x="480" y="152" font-size="15" text-anchor="middle">ここを入れ替える</text>

    <rect class="box" x="642" y="74" width="270" height="160"/>
    <text class="t"     x="777" y="120" font-size="17" text-anchor="middle" font-weight="700">配送</text>
    <text class="t-sub" x="777" y="152" font-size="15" text-anchor="middle">APIだけ直す</text>
  </svg>
  <figcaption>社内システムの構成。今回の変更は在庫だけに閉じる。</figcaption>
</figure>
```

**外枠は `.box-b`（沈めた帯）、中身は `.box`。** 同じ色で重ねると入れ子に見えない。

## 4. 横バー

```html
<figure>
  <svg viewBox="0 0 960 220" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="工程別の所要時間">
    <text class="t"     x="20" y="44"  font-size="17">手作業</text>
    <rect class="box"   x="180" y="24" width="700" height="40"/>
    <text class="t"     x="896" y="51" font-size="17" font-weight="700">42分</text>

    <text class="t"     x="20" y="116" font-size="17">半自動</text>
    <rect class="box"   x="180" y="96" width="300" height="40"/>
    <text class="t"     x="496" y="123" font-size="17" font-weight="700">18分</text>

    <text class="t"     x="20" y="188" font-size="17">全自動</text>
    <rect class="box-a" x="180" y="168" width="83" height="40"/>
    <text class="t"     x="279" y="195" font-size="17" font-weight="700">5分</text>

    <text class="t-sub" x="180" y="215" font-size="15">社内計測（2026-09-10、n=20）</text>
  </svg>
  <figcaption>1件あたりの所要時間。全自動は手作業の 1/8。</figcaption>
</figure>
```

**バーの長さを実数に比例させる。** 42:18:5 なら 700:300:83。目分量で描くと、
図と数字が食い違ったまま会議に出る。**数値には出典を図の中に置く。**
「その数字どこから？」で止まるのを防げる。

## 5. 樹形図

```html
<figure>
  <svg viewBox="0 0 960 260" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="再実行するかどうかの判断">
    <rect class="box-b" x="330" y="20" width="300" height="70"/>
    <text class="t" x="480" y="62" font-size="17" text-anchor="middle" font-weight="700">失敗を検知</text>

    <path class="ln" d="M480 90 V120 H190 V158"/>
    <path class="ln" d="M480 90 V120 H770 V158"/>
    <polygon class="ar" points="183,158 197,158 190,172"/>
    <polygon class="ar" points="763,158 777,158 770,172"/>
    <text class="t-sub" x="300" y="112" font-size="15" text-anchor="middle">一時的</text>
    <text class="t-sub" x="660" y="112" font-size="15" text-anchor="middle">恒久的</text>

    <rect class="box"   x="40"  y="172" width="300" height="70"/>
    <text class="t"     x="190" y="214" font-size="17" text-anchor="middle">3回まで再実行</text>

    <rect class="box-a" x="620" y="172" width="300" height="70"/>
    <text class="t-a"   x="770" y="214" font-size="17" text-anchor="middle">止めて通知</text>
  </svg>
  <figcaption>失敗を検知したあとの分岐。恒久的な失敗は再実行しない。</figcaption>
</figure>
```

**枝のラベル（「一時的」「恒久的」）を必ず置く。** 条件が書かれていない分岐図は、
見た目は図でも中身は箱の羅列。

## 6. before / after

```html
<figure>
  <svg viewBox="0 0 960 200" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="承認フローの変更前後">
    <rect class="box"   x="20"  y="30" width="400" height="140"/>
    <text class="t-sub" x="40"  y="62"  font-size="15">いま</text>
    <text class="t"     x="40"  y="100" font-size="17">申請 → 課長 → 部長 → 経理</text>
    <text class="t-hot" x="40"  y="140" font-size="17" font-weight="700">平均 4.2日</text>

    <path class="ln" d="M432 100 H508"/>
    <polygon class="ar" points="508,92 524,100 508,108"/>

    <rect class="box-a" x="540" y="30" width="400" height="140"/>
    <text class="t-a"   x="560" y="62"  font-size="15">変更後</text>
    <text class="t-a"   x="560" y="100" font-size="17">申請 → 部長 → 経理</text>
    <text class="t-a"   x="560" y="140" font-size="17" font-weight="700">平均 1.5日（見込み）</text>
  </svg>
  <figcaption>承認フローの変更前後。課長承認を外し、2.7日短縮する見込み。</figcaption>
</figure>
```

**同じ位置に同じ種類の情報を置く。** 左右で行の意味がずれると、何が変わったのかが読めない。
見込みの数字には「（見込み）」を付ける。実績と並べたまま出すと、会議で必ず突っ込まれる。

## 7. タイムライン

```html
<figure>
  <svg viewBox="0 0 960 180" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="導入の日程">
    <path class="ln" d="M60 96 H900"/>
    <polygon class="ar" points="900,88 916,96 900,104"/>

    <circle class="box"   cx="140" cy="96" r="14"/>
    <text class="t"       x="140" y="62"  font-size="17" text-anchor="middle" font-weight="700">10月</text>
    <text class="t-sub"   x="140" y="140" font-size="15" text-anchor="middle">試験導入</text>

    <circle class="box"   cx="420" cy="96" r="14"/>
    <text class="t"       x="420" y="62"  font-size="17" text-anchor="middle" font-weight="700">12月</text>
    <text class="t-sub"   x="420" y="140" font-size="15" text-anchor="middle">2部署へ拡大</text>

    <circle class="box-a" cx="700" cy="96" r="18"/>
    <text class="t-hot"   x="700" y="62"  font-size="17" text-anchor="middle" font-weight="800">2月</text>
    <text class="t"       x="700" y="140" font-size="15" text-anchor="middle" font-weight="700">全社展開</text>
  </svg>
  <figcaption>導入の日程。2月の全社展開が、今日決めたい判断の期限。</figcaption>
</figure>
```

**節目は3〜4個まで。** それ以上あるのは日程表であって図ではないので、表にする。

## 8. シーケンス

```html
<figure>
  <svg viewBox="0 0 960 260" xmlns="http://www.w3.org/2000/svg" role="img"
       aria-label="通知が届くまでのやりとり">
    <rect class="box-b" x="60"  y="20" width="200" height="50"/>
    <text class="t"     x="160" y="52" font-size="17" text-anchor="middle" font-weight="700">利用者</text>
    <rect class="box-b" x="380" y="20" width="200" height="50"/>
    <text class="t"     x="480" y="52" font-size="17" text-anchor="middle" font-weight="700">アプリ</text>
    <rect class="box-b" x="700" y="20" width="200" height="50"/>
    <text class="t"     x="800" y="52" font-size="17" text-anchor="middle" font-weight="700">通知基盤</text>

    <path class="ln" d="M160 70 V240" stroke-dasharray="6 6"/>
    <path class="ln" d="M480 70 V240" stroke-dasharray="6 6"/>
    <path class="ln" d="M800 70 V240" stroke-dasharray="6 6"/>

    <path class="ln" d="M160 112 H466"/>
    <polygon class="ar" points="466,105 480,112 466,119"/>
    <text class="t-sub" x="320" y="102" font-size="15" text-anchor="middle">申請する</text>

    <path class="ln" d="M480 168 H786"/>
    <polygon class="ar" points="786,161 800,168 786,175"/>
    <text class="t-sub" x="640" y="158" font-size="15" text-anchor="middle">送信を依頼</text>

    <path class="ln" d="M800 220 H174"/>
    <polygon class="ar" points="174,213 160,220 174,227"/>
    <text class="t-sub" x="480" y="210" font-size="15" text-anchor="middle">メールが届く</text>
  </svg>
  <figcaption>通知が届くまでのやりとり。アプリは依頼するだけで、送信は通知基盤が持つ。</figcaption>
</figure>
```

**登場人物は3つまで、やりとりは4本まで。** 超えたら、その節は図1枚で説明できる粒度を
超えている。節を割るか、詳細を補足に逃がす。

---

## 型が決まらないとき

内容の形と型が噛み合っていないだけのことが多い。もう一度この対応で引き直す。

| 節が言っていること | 型 |
|---|---|
| AのあとにB、そのあとC | 1 横並びのステップ |
| AとBのどちらを選ぶか | 2 2カラムの並置 |
| Aの中にBとCがある | 3 入れ子のボックス |
| AはBの何倍 / どれだけ多い | 4 横バー |
| Aなら X、Bなら Y | 5 樹形図 |
| 今はA、変えるとB | 6 before / after |
| いつ何が起きるか | 7 タイムライン |
| 誰が誰に何を渡すか | 8 シーケンス |

どれにも当てはまらないなら、**その節は図にしない。** 無理に図にすると、本文の箇条書きを
四角で囲んだだけのものが出てくる。それは図ではなく、読む量が増えただけの飾り。
数字が主役なら `.stats`、項目の対照が主役なら表で見せる。
