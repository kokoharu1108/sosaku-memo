# 創作メモ帳（創作補助アプリ）

個人用の創作補助メモアプリ。旅行・イベントで体験したこと、学んだこと、思いついたアイデアをその場でメモし、後でシナリオやイラストの資料として引き出す。完全に個人利用で、共有・共同編集は想定しない。

- 元の仕様書: `docs/創作補助アプリ仕様書.txt`、画面遷移図: `docs/画面遷移図.jpg`（仕様は利用者の要望で多くの点が変わっている。現在の仕様は本ファイルと `docs/HISTORY.md` を優先する）
- これまでの要望と対応の経緯: `docs/HISTORY.md`（「なぜこうなっているか」を知りたいときに読む）

## 利用者と進め方

- 利用者は日本語話者。返答・UI文言・コメントはすべて日本語。専門用語は避け、平易に説明する。
- 主な利用端末は **Android スマホ（Chrome、ホーム画面に追加したPWA）**。PCでも使う。操作性はスマホ優先。
- 不具合・要望は数件まとめて報告される。1件ずつ直し、報告にない不具合も見つけたら一緒に直して報告する。
- 変更のたびに、何をどう直したかを利用者向けに短くまとめる（ファイル名・関数名は出さない）。

## 構成

ビルド不要の静的PWA。GitHub Pages で公開（利用者が GitHub のWeb画面からファイルをアップロードして更新している）。

- `index.html` … アプリ本体（HTML・CSS・JS をすべて1ファイルに内包。外部ライブラリなし。Google Fonts のみ外部読み込み）
- `sw.js` … オフライン起動用 Service Worker
- `manifest.webmanifest`、`icons/` … ホーム画面追加用

### 重要な決まり

- **`index.html` を変更したら、必ず `sw.js` の `CACHE` の番号を1つ上げる**（例 `sosaku-memo-v9` → `v10`）。上げないと利用者の端末が古い版のまま更新されない。
- 1ファイル構成を維持する（利用者の更新手順が「ファイルを上書きアップロード」なので、ファイルを増やす場合は利用者に伝える）。
- データはすべて端末内（IndexedDB）。サーバーは持たない。オフラインで全機能（保存・閲覧・検索）が動くこと。

## index.html の中身（上から順）

- `<style>` … 色はすべて `:root` のトークン（ライト）＋ダーク用の2ブロック（`prefers-color-scheme` と `[data-theme="dark"]`）。ペールトーン基調。画面ごとの上部バー色 `--bar-search/--bar-view/--bar-list/--bar-edit`（`syncThemeColor` でスマホ上端の帯 `theme-color` も同じ色に）、文字色 `--tc-*`、マーカー `--hl-*` もトークン。
- Utilities … `h()`（要素生成ヘルパー）、`fmtDate`、`lsGet/lsSet`（localStorage は try/catch 付き）
- HTML sanitizer … 本文HTMLの許可タグ制限。色は **クラス**（`tc-rose` 等／`hl-yellow` 等）でのみ保存し、色コードは保存しない（ダークモード対応のため）。旧版の色コードは `LEGACY_TC` でクラスに変換。スタイルで付いた太字等は `<b>/<i>/<s>/<u>` に置き換え。空の書式要素は削除。
- Storage … IndexedDB `sosaku-memo`（v1）。ストア: `memos` / `lists` / `meta`（key `app`） / `files`（添付ファイルの Blob）
- Manager（メモ管理機能） … メモ・リストの保存/削除、検索用索引、階層（ツリー）索引、毎日0時の整理（`maintain`）、旧「参照メモ」→親子への一度きりの移行（`migrateTree`）
- UI state & navigation … 画面スタック `UI.stack` とブラウザ履歴を連動（Android の戻る操作対応）。`go / back / backTo / resetTo / goHome`。選択モード（まとめて削除）、パンくず `crumbBar()`
- Render … 画面: `renderSearch`（タブ: メモ／ツリー／リスト、🔍で開閉する検索パネル）、`renderListScreen`、`renderView`、`renderEdit`
- 設定 … ダークモード、バックアップ書き出し／読み込み（JSON に添付ファイルも data URL で含める）
- Boot

### データ形式（memos）

`{ id, title, genres[], bodyHtml, bodyText, attachments[{id,name,type,size,fileId}], tags[], parentId, listIds[], links[](旧参照・現在は未使用), createdAt, updatedAt }`

- `createdAt` は作成時から不変、`updatedAt` は保存のたびに更新。
- 階層は `parentId` のみで表す。親が消えた／循環している場合は最上位扱い（`effParent`）。親を削除すると子は1つ上の階層へ移る。
- localStorage は端末ごとの小さな設定だけ: `sm.theme`、`sm.recallHidden`。

## 本文エディタの注意点（不具合が出やすい箇所）

- `contenteditable` + `document.execCommand`。スマホの日本語入力を前提にする。
- 文字を選んでいない状態の太字・斜体・取り消し線・下線は、`execCommand` ではなく自前の `toggleInline`（ゼロ幅スペース `​` を使う）で切り替える。保存時と `htmlToText` でゼロ幅スペースは除去。
- `restoreRange` は、本文にフォーカスとカーソルがある間は選択範囲を触らない（触ると「次の文字を太字に」等の状態が消える）。
- 文字色・マーカーは、色ごとの目印色で一旦付けて `convertMarks` でクラスに置き換える。日本語変換中（`isComposing`）は本文を書き換えない。
- 書式ボタンの押下状態は `updateStates`（選択なしのときは DOM の祖先要素で判定）。
- スマホで本文入力中はツールバーをキーボードの上に固定（`visualViewport` 使用）。小窓（`.pop`）は `position: fixed` で body 直下に出す。
- `confirm()` 等のブラウザ標準ダイアログは使わず、自前の `modal()` を使う。

## 動作確認

利用者に渡す前に、スマホ幅（390×844）でブラウザ自動操作による確認を行う。

```bash
python3 -m http.server 8765        # このフォルダで起動
python3 tests/e2e_smoke.py          # 主要操作の確認（Playwright が必要）
```

- 日本語入力の再現には `page.keyboard.insert_text()` を使う（キーイベントが出ない点がスマホの IME に近い）。
- ダークモードは `document.documentElement.dataset.theme = 'dark'` で確認。
- JS の構文確認: `<script>` 部分を取り出して `node --check`。

## これまでに決まった方針（変える前に利用者に確認する）

- AI検索・Wikipedia 等の「調べる」機能は**撤廃済み**（スマホ標準の選択メニューのWeb検索で足りるため）。再追加しない。
- 文字サイズ変更ボタンは撤廃済み（ピンチ操作で代替）。
- バックアップを促す常時表示は出さない（設定内に前回の書き出し日時を表示）。
- ダークモード切替は設定内。
- ジャンルは「体験」「学び」「アイデア」の3つ固定（1つ以上必須。自動保存時のみ未選択可）。
- Googleドライブ連携は**未着手**。直接保存はオフライン不可になるため見送り、「端末保存＋裏でドライブへ自動同期」を候補として提案済み（Google Cloud 登録 or GAS 方式は未決定）。
