# sns-icon-builder — iteration-2

対照は分割前の icon-builder（`--targets social` で 1024px を1枚だけ出す版）。

| 構成 | 合格率 | 時間(秒) | トークン |
|---|---|---|---|
| with_skill | 100% | 82 | 80705 |
| old_skill | 52% | 294 | 119290 |

| eval | 構成 | 合格 |
|---|---|---|
| subset-four-services | with_skill | 4/4 |
| subset-four-services | old_skill | 3/4 |
| github-org-and-slack | with_skill | 5/5 |
| github-org-and-slack | old_skill | 2/5 |
| all-seven-thin-design | with_skill | 5/5 |
| all-seven-thin-design | old_skill | 2/5 |
