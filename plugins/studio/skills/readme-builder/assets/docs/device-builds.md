<!--
検証端末へのビルドと更新の専用資料の骨格。モバイルアプリのときだけ作り、README の「関連文書」からリンクする。
scan_repo.py の「モバイルアプリ」を出発点にする（構成・配布経路・版番号の置き場所）。
読者が知りたいのは「最新版を検証端末に入れるには、誰が何をすればよいか」。
署名の証明書・プロファイル・keystore はファイルも値も書かない。置き場所は external-services.md の表へ。
-->

# 検証端末へのビルドと更新

最終確認日: {{YYYY-MM-DD}}


| OS | 配布経路 | 配れる人 | 端末での受け取り方 |
|---|---|---|---|
| iOS | {{TestFlight（内部テスト）}} | {{App Store Connect で App Manager 以上}} | {{TestFlight アプリで招待を承認してインストール}} |
| Android | {{Firebase App Distribution / Google Play 内部テスト}} | {{Firebase プロジェクトの編集者}} | {{招待メールのリンクからインストール}} |

## 端末を登録する（初回だけ）

- iOS: {{TestFlight なら Apple ID の招待だけ。Ad Hoc・Development 配布なら UDID の登録が要る。依頼先: ○○}}
- Android: {{テスターのメールアドレスをグループ「○○」に追加する。依頼先: ○○}}

## ビルドして配る

1. 版番号を上げる。{{ビルド番号は同じ番号で二度配れない。上げる場所: android/app/build.gradle の versionCode、Xcode の CURRENT_PROJECT_VERSION}}
2. ビルドして配布先へ上げる。

```bash
{{eas build --profile preview --platform all / bundle exec fastlane ios beta}}
```

{{自動で配られる場合は、何をきっかけに走るか（例: main へのマージで CI が配布）}}

## 端末で更新する

- iOS: {{TestFlight アプリを開いて「アップデート」}}
- Android: {{App Tester から新しい版をインストール}}

{{アプリの設定画面の版番号が、配ったビルドの番号と一致すれば成功。}}

## 手元の端末に直接入れる（開発中）

<!-- 配布を通さず、USB で自分の端末に入れる手順。開発中の確認に使う。不要なら消す。 -->

```bash
{{pnpm cap:sync && pnpm cap:ios（Xcode で端末を選んで Run）}}
```

