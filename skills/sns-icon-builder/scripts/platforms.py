#!/usr/bin/env python3
"""platforms.py — 各SNSの仕様表。build / preview / verify / UPLOAD.md の唯一の出所。

ここに書く数値は「各社の公式ヘルプに書かれている値」と「実UIを見ないと分からない値」の
2種類が混ざる。混ぜたまま使うと、後で更新するときにどれを裏取りすべきか分からなくなるので、
`source` で分けている:

  "doc"   … 公式ヘルプに明記がある。更新時は出典URLを引き直す
  "ui"    … 公式には書かれておらず、実際の画面を見て決めた値（最小表示・切り抜き形状）
  "guess" … 公式が非公開で、実務上の相場から置いた値（Instagram の推奨寸法だけ）

`min_display` は「そのサービスで一番小さく出る場所」の実測値で、公式仕様ではない。
これがこのスキルの中心にある数値なので、`ui` と明示したうえで根拠の画面を併記する。
"""

# crop: "circle" = 円形に切られる / "squircle" = 角丸四角に切られる
PLATFORMS = {
    "x": {
        "label": "X (Twitter)",
        "px": 400,
        "max_bytes": 2_000_000,
        "formats": ["PNG", "JPEG", "GIF"],
        "crop": "circle",
        "min_display": 32,
        "min_display_where": "タイムラインの返信ツリー",
        "source": "doc",
        "upload": "設定 → プロフィール → 「プロフィールを編集」→ 円形のアイコンをクリック",
        "gotcha": "アップロード時に円形のトリミングUIが出る。ここで拡大すると端が切れるので、"
                  "枠いっぱいのまま確定する",
    },
    "youtube": {
        "label": "YouTube",
        "px": 800,
        "max_bytes": 15_000_000,
        "formats": ["PNG", "JPEG", "GIF", "BMP"],
        "crop": "circle",
        "min_display": 48,
        "min_display_where": "動画下のコメント欄",
        "source": "doc",
        "upload": "YouTube Studio → カスタマイズ → ブランディング → 写真",
        "gotcha": "**アニメーションGIFは不可**（静止GIFは可）。反映に数分〜数十分かかる",
    },
    "instagram": {
        "label": "Instagram",
        "px": 1080,
        "max_bytes": 8_000_000,
        "formats": ["PNG", "JPEG"],
        "crop": "circle",
        "min_display": 32,
        "min_display_where": "フィード投稿のヘッダー",
        "source": "guess",
        "upload": "プロフィール → プロフィールを編集 → 写真を変更（アプリ／Webどちらでも可）",
        "gotcha": "公式が推奨寸法を公開していない。表示は320px程度なので1080で入れて"
                  "向こうの圧縮に任せる。小さく入れると再圧縮で潰れる",
    },
    "note": {
        "label": "note",
        "px": 330,
        "max_bytes": 10_000_000,
        "formats": ["PNG", "JPEG", "GIF"],
        "crop": "circle",
        "min_display": 40,
        "min_display_where": "記事一覧のクリエイター名の横",
        "source": "doc",
        "upload": "アカウント設定 → プロフィール → アイコン画像",
        "gotcha": "公式の推奨が330pxと小さい。大きく入れても縮められるので、推奨どおり330で出す",
    },
    "line": {
        "label": "LINE公式アカウント",
        "px": 640,
        "max_bytes": 3_000_000,
        "formats": ["PNG", "JPEG"],
        "crop": "circle",
        "min_display": 48,
        "min_display_where": "トークリスト",
        "source": "doc",
        "upload": "LINE Official Account Manager → 設定 → アカウント設定 → プロフィール画像",
        "gotcha": "**変更は1時間に1回まで。** 出し直しが効かないので、上げる前に必ず確認を取る",
    },
    "github": {
        "label": "GitHub",
        "px": 500,
        "max_bytes": 1_000_000,
        "formats": ["PNG", "JPEG", "GIF"],
        "crop": "circle",          # --github-account org を渡すと squircle に変わる
        "min_display": 20,
        "min_display_where": "コミット一覧・blame の行頭",
        "source": "doc",
        "upload": "Settings → Profile → Profile picture（Organization は "
                  "Organization settings → Profile → Profile picture）",
        "gotcha": "**容量上限が全社で最も厳しい1MB。** 個人アカウントは円、Organization は角丸四角で、"
                  "切り抜き形状が違う。`--github-account org` を渡すと角丸版で出る",
    },
    "slack": {
        "label": "Slack",
        "px": 512,
        "max_bytes": 1_000_000,
        "formats": ["PNG", "JPEG", "GIF", "BMP"],
        "crop": "squircle",
        "min_display": 20,
        "min_display_where": "メッセージ一覧のコンパクト表示",
        "source": "doc",
        "upload": "プロフィール → プロフィールを編集 → 画像をアップロードする",
        "gotcha": "512〜1024pxしか受け付けない（下限がある唯一のサービス）。"
                  "表示は円ではなく角丸四角なので、円前提で詰めると余白が目立つ",
    },
}

ORDER = ["x", "youtube", "instagram", "note", "line", "github", "slack"]

# 切り抜き形状ごとの安全域。canvas の半辺を 1.0 としたときの、インクが収まってよい距離。
#   circle   … 内接円の内側。0.92 は「直径の92%」で、各社のトリミングUIの誤差ぶんを見ている
#   squircle … 角丸四角。Slack / GitHub Organization の角丸率はおおむね 22% で、
#              中央90%の正方形に収めれば角に当たらない
SAFE = {
    "circle":   {"build": 0.92, "warn": 0.96, "fail": 1.00},
    "squircle": {"build": 0.90, "warn": 0.94, "fail": 1.00},
}

CROP_LABEL = {"circle": "円", "squircle": "角丸四角"}


def resolve(name: str, github_account: str = "user") -> dict:
    """サービス名から仕様を引く。GitHub だけはアカウント種別で切り抜き形状が変わる。"""
    spec = dict(PLATFORMS[name])
    if name == "github" and github_account == "org":
        spec["crop"] = "squircle"
        spec["label"] = "GitHub (Organization)"
    return spec


def filename(name: str, spec: dict) -> str:
    """`x-400.png` のように、サービス名がそのままファイル名になる。

    上げ先を間違えるのが一番多い事故なので、ディレクトリで分けずにファイル名で分ける。
    """
    return f"{name}-{spec['px']}.png"
