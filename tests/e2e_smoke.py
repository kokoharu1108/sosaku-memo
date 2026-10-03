"""創作メモ帳: 主要操作の自動確認（スマホ幅）

使い方:
  1. このリポジトリのルートで  python3 -m http.server 8765
  2. 別の端末で            python3 tests/e2e_smoke.py
  （必要: pip install playwright && playwright install chromium）

日本語入力の再現には keyboard.insert_text() を使う（スマホの IME と同じくキーイベントが出ない）。
"""
import os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
ICON = str(Path(__file__).resolve().parent.parent / "icons" / "icon-192.png")
failures, errors = [], []

def check(name, cond, detail=""):
    print(("OK  " if cond else "NG  ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond: failures.append(name)

def new_memo(pg, title, genre="体験", body=None):
    pg.click(".fab"); pg.fill("#title", title); pg.click(f".genre-pick >> text={genre}")
    if body: pg.click(".editor"); pg.keyboard.insert_text(body)
    pg.click("#title"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".search-toggle"); time.sleep(0.2)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector(".fab")

    # 作成・保存・一覧
    new_memo(pg, "京都取材", body="鞍馬で火祭を見た")
    new_memo(pg, "単独メモ", genre="学び")
    check("メモが一覧に出る", pg.locator(".memo-card").count() == 2)

    # 検索パネル・履歴・ジャンル
    pg.click(".search-toggle"); pg.fill("#q", "火祭"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("キーワード検索", pg.locator(".memo-card").count() == 1)
    check("履歴が絞り込みを隠さない", pg.evaluate("(()=>{const s=document.querySelector('#genre-search');const r=s.getBoundingClientRect();return document.elementFromPoint(r.left+5,r.top+5)===s})()"))
    pg.click(".filter-chip button"); pg.select_option("#genre-search", "学び"); time.sleep(0.1)
    check("ジャンル絞り込み", pg.locator(".memo-card").count() == 1)
    pg.select_option("#genre-search", ""); pg.click(".search-toggle")

    # 階層（子メモ）とツリー
    pg.locator(".memo-card", has_text="京都取材").click(); pg.wait_for_selector(".view-title")
    pg.click(".child-head .btn"); pg.fill("#title", "鞍馬の火祭"); pg.click(".genre-pick >> text=体験")
    pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".view-title"); time.sleep(0.2)
    check("子メモ保存後は親メモに戻る", pg.inner_text(".view-title") == "京都取材" and pg.locator(".child-sec .tree-title", has_text="鞍馬の火祭").count() == 1)
    pg.go_back(); pg.wait_for_selector(".search-toggle"); time.sleep(0.2)
    pg.click(".tabs >> text=ツリー")
    check("ツリーは階層のあるメモだけ", pg.locator(".tree .tree-title").count() == 1)
    pg.locator(".tree-title", has_text="京都取材").click()
    check("ツリーを開くと子が出る", pg.locator(".tree .tree-title", has_text="鞍馬の火祭").count() == 1)
    pg.locator(".tree-title", has_text="鞍馬の火祭").click(); pg.wait_for_selector(".view-title")
    check("階層パス表示", "京都取材" in pg.inner_text(".tree-path"))

    # 戻る操作（Android のスワイプと同じ）
    pg.go_back(); time.sleep(0.3)
    check("戻る操作で前の画面へ", pg.locator(".search-toggle").count() == 1)

    # 上部バーの色（画面ごとに違う色・スマホ上端の帯も同じ色）
    pg.click(".tabs >> text=メモ")
    bars = {}
    bars["search"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    tc_search = pg.evaluate("document.querySelector('meta[name=theme-color]').content")
    pg.locator(".memo-card").first.click(); pg.wait_for_selector(".view-title")
    bars["view"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    check("スマホ上端の帯が画面に合わせて変わる", tc_search != pg.evaluate("document.querySelector('meta[name=theme-color]').content"))
    pg.click(".menu-btn"); pg.click(".menu >> text=編集")
    bars["edit"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    check("上部バーが画面ごとに違う色", len(set(bars.values())) == 3, str(bars))

    # 編集中にパンくずで最初の画面へ → 未保存の確認が出る
    pg.fill("#title", "京都取材（仮）"); pg.click(".crumb.home"); time.sleep(0.3)
    check("未保存のままパンくずで離れると確認が出る", pg.locator(".modal").count() == 1)
    pg.click(".modal >> text=破棄して戻る"); pg.wait_for_selector(".search-toggle"); time.sleep(0.2)
    check("破棄すると最初の画面へ・変更は保存されない", pg.locator(".memo-card", has_text="京都取材（仮）").count() == 0)

    # リスト画面で新規メモ → 保存後はリスト画面に戻る
    pg.click(".tabs >> text=リスト"); pg.click(".fab"); pg.fill("#newlist", "京都"); pg.click(".modal >> text=作成"); time.sleep(0.3)
    if pg.locator(".modal").count(): pg.click(".modal >> text=キャンセル"); time.sleep(0.2)
    pg.click(".fab"); pg.fill("#title", "リスト内メモ"); pg.click(".genre-pick >> text=学び"); pg.click(".edit-actions .btn.primary"); time.sleep(0.4)
    check("リストで作ったメモは保存後リスト画面に戻る", pg.locator(".list-head-label").count() == 1 and pg.locator(".memo-card", has_text="リスト内メモ").count() == 1)

    # 選択モードのままパンくずで戻っても、その後の「戻る」が効く
    pg.click(".sel-start"); pg.click(".crumb.home"); time.sleep(0.4)
    pg.click(".tabs >> text=メモ"); pg.locator(".memo-card").first.click(); pg.wait_for_selector(".view-title")
    pg.go_back(); time.sleep(0.3)
    check("選択モード後も戻る操作が効く", pg.locator(".search-toggle").count() == 1)

    pg.click(".tabs >> text=リスト"); pg.click(".list-row .open"); time.sleep(0.3)
    # リスト → 閲覧 → 編集で削除すると、リスト画面に戻り「戻る」もずれない
    pg.locator(".memo-card", has_text="リスト内メモ").click(); pg.wait_for_selector(".view-title")
    pg.click(".menu-btn"); pg.click(".menu >> text=編集"); pg.click(".topbar .btn.danger"); time.sleep(0.2)
    if pg.locator(".modal").count(): pg.click(".modal >> text=Yes")
    time.sleep(0.6)
    check("編集画面で削除するとリスト画面に戻る", pg.locator(".list-head-label").count() == 1 and pg.locator(".memo-card", has_text="リスト内メモ").count() == 0)
    pg.go_back(); time.sleep(0.4)
    check("削除後の戻る操作で最初の画面へ", pg.locator(".search-toggle").count() == 1)

    # 本文エディタ（本文より上は題名とジャンルだけ・書式ボタンは1行）
    pg.click(".tabs >> text=メモ"); pg.click(".fab")
    check("新規メモで本文が1画面目に見える", pg.evaluate("document.querySelector('.editor').getBoundingClientRect().top < 400"))
    check("タグ・階層は本文より下", pg.evaluate("(()=>{const e=document.querySelector('.editor').getBoundingClientRect().top;return document.querySelector('#taginput').getBoundingClientRect().top>e&&document.querySelector('.parent-box').getBoundingClientRect().top>e})()"))
    check("書式ボタンが1行に収まる", pg.evaluate("(()=>{const f=document.querySelector('.fmt-bar');return f.scrollWidth<=f.clientWidth+1})()"))
    pg.click("#title"); check("題名を触ると直近の題名が出る", pg.locator(".recent-titles").is_visible())
    pg.click(".topbar .back"); pg.wait_for_selector(".search-toggle")
    pg.click(".tabs >> text=メモ"); pg.click(".fab"); pg.fill("#title", "書式"); pg.click(".genre-pick >> text=アイデア"); pg.click(".editor")
    pg.click(".b-bold"); pg.click(".b-italic"); pg.keyboard.insert_text("太斜")
    pg.click(".b-bold"); pg.keyboard.insert_text("斜"); pg.click(".b-italic"); pg.keyboard.insert_text("標準")
    html = pg.inner_html(".editor").replace("​", "")
    check("太字+斜体を付けて1つずつ外す", "<b><i>太斜</i></b><i>斜</i>標準" in html, html)
    check("書式ボタンの状態が戻る", pg.get_attribute(".b-bold", "aria-pressed") == "false" and pg.get_attribute(".b-italic", "aria-pressed") == "false")
    pg.keyboard.press("Enter"); pg.keyboard.insert_text("見出し")
    pg.click(".head-btn")
    check("見出しの小窓が画面内", pg.evaluate("(()=>{const r=document.querySelector('.pop').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})()"))
    pg.click(".pop .hp-h2")
    pg.keyboard.press("Enter"); pg.click(".color-btn"); pg.click(".pop .tc-rose"); pg.keyboard.insert_text("赤")
    check("文字色はクラスで付く", pg.locator(".editor .tc-rose").count() == 1)
    pg.set_input_files("#file", ICON); pg.wait_for_selector(".att-tile")
    pg.click("#title"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".search-toggle"); time.sleep(0.2)
    pg.locator(".memo-card", has_text="書式").click(); pg.wait_for_selector(".view-title")
    body = pg.inner_html(".view-body")
    check("保存後も書式・見出しが残る", "<b>" in body and "<h2>" in body and "tc-rose" in body, body[:200])
    check("ゼロ幅スペースが残らない", "​" not in body)
    pg.evaluate("document.documentElement.dataset.theme='dark'")
    check("ダークモードで文字色が明るい色に", pg.evaluate("getComputedStyle(document.querySelector('.view-body .tc-rose')).color") == "rgb(242, 154, 172)")
    pg.evaluate("document.documentElement.dataset.theme='light'")
    pg.click(".att-details summary")
    check("添付ファイルが一覧に出る", pg.locator(".att-row").count() == 1)

    # 編集→保存で前の画面へ
    pg.click(".menu-btn"); pg.click(".menu >> text=編集"); pg.fill("#title", "書式（改）")
    pg.click(".edit-actions .btn.primary"); time.sleep(0.5)
    check("編集保存後は閲覧画面に戻る", pg.locator(".view-title").count() == 1 and pg.inner_text(".view-title") == "書式（改）")

    # バックアップの書き出し → 「前回の書き出し」がその場で更新される
    pg.goto(URL); pg.wait_for_selector(".fab"); pg.click("button[aria-label=設定]")
    with pg.expect_download() as dl: pg.click(".modal >> text=バックアップを書き出す")
    check("バックアップを書き出せる", dl.value.suggested_filename.startswith("sosaku-memo-backup-"))
    time.sleep(0.3)
    check("前回の書き出し日時がすぐ更新される", "まだありません" not in pg.inner_text(".modal"))
    pg.click(".modal >> text=閉じる")

    # オフライン起動
    pg.goto(URL); pg.wait_for_selector(".fab"); time.sleep(1)
    ctx.set_offline(True); pg.reload(); pg.wait_for_selector(".memo-card", timeout=8000)
    check("オフラインで起動・一覧表示", pg.locator(".memo-card").count() >= 4)
    ctx.set_offline(False)

    # まとめて削除
    pg.click(".sel-start"); pg.locator(".memo-card").first.click(); pg.click(".select-bar >> text=削除"); pg.click(".modal >> text=Yes"); time.sleep(0.4)
    check("まとめて削除", pg.locator(".select-bar").count() == 0)
    b.close()

real_errors = [e for e in errors if "fonts.g" not in e]
check("JavaScript エラーなし", not real_errors, "; ".join(real_errors))
print(f"\n{'すべて成功' if not failures else str(len(failures)) + '件失敗'}")
sys.exit(1 if failures else 0)
