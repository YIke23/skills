# meeting-deck — iteration-1

対照は素の Claude（スキルなし）。4ケース各1回。

| 構成 | 合格率 | 時間(秒) | トークン |
|---|---|---|---|
| with_skill | 100% | 421 | 122,012 |
| without_skill | 65% | 590 | 125,948 |

| eval | 構成 | 合格 |
|---|---|---|
| progress-with-numbers | with_skill | 12/12 |
| progress-with-numbers | without_skill | 8/12 |
| proposal-with-branching | with_skill | 11/11 |
| proposal-with-branching | without_skill | 6/11 |
| too-many-sections | with_skill | 11/11 |
| too-many-sections | without_skill | 5/11 |
| requirements-doc-wide-tables | with_skill | 12/12 |
| requirements-doc-wide-tables | without_skill | 11/12 |

## 読み取り

- 最も効いたのは「md の h2 が順番どおり全部出ている」（あり 4/4 / なし 1/4）。なし側は見出しを主張文に書き換え（「いまの状況」→「8月は 1,842件中 631件が自動返信で完結した」）、md に無いスライドを足した。プレゼンの定石としては上手いが、章立てを動かさないという要件には反する。
- `check_deck.py` の 4対0 は中立な計測ではない（スキルの同梱物）。ただし中身は形式に依らない実害で、なし側も自前の走査スクリプトで同種の不具合を探していた。
- 「断定に変えていない」系5項目は あり/なし どちらも全通過。この事故はスキルが無くても起きにくく、SKILL.md の該当ルールは想定ほど効いていない可能性がある。
- 節が15あるケースは、検知自体は両方できた。差が出たのはその後で、なし側は6章に束ね、決議事項を自分で決め、会議時間を仮定した。
- 要件書ケースはなし側も 11/12 と強い。元の md がよく書けていると差は縮む。

## このテストが見つけた不具合

`deck.css` の `table{min-width:32rem}` は `rem` がルート16px基準のため 512px にしかならず、紙面1152pxに収まって9列の表が横スクロールせず列だけ潰れていた。`width:max-content` ＋ セルの `max-width:22em` に変更（実測: 9列で 1行 342px → 130px、2列・4列の表は変化なし）。
