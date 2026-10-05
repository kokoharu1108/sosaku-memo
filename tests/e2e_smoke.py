"""ヒフミヨ（創作メモアプリ）: 主要操作の自動確認（スマホ幅）

使い方:
  1. このリポジトリのルートで  python3 -m http.server 8765
  2. 別の端末で            python3 tests/e2e_smoke.py
  （必要: pip install playwright && playwright install chromium）

日本語入力の再現には keyboard.insert_text() を使う（スマホの IME と同じくキーイベントが出ない）。
"""
import os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fake_gas import FakeGas

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/"
ICON = str(Path(__file__).resolve().parent.parent / "icons" / "icon-192.png")
failures, errors = [], []

def check(name, cond, detail=""):
    print(("OK  " if cond else "NG  ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond: failures.append(name)

def long_press(pg, loc):
    """長押し（指を置いたまま0.7秒）。離したあとの「押した」扱いも含めて確かめる"""
    box = loc.bounding_box(); x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    pg.mouse.move(x, y); pg.mouse.down(); pg.wait_for_timeout(700); pg.mouse.up(); pg.wait_for_timeout(300)

NAV_KEY = {"最近": "memos", "フォルダ": "lists", "検索": "search", "まとめ": "report", "設定": "settings"}
def menu_go(pg, label):
    """画面の下のアイコンの列から選ぶ"""
    pg.click(f".bottom-nav .bn-{NAV_KEY[label]}"); time.sleep(0.35)

def tab(pg, name):
    """検索画面のタブ（最近・フォルダ・情報まとめ）へ。今その画面ならそのまま"""
    if pg.inner_text(".tab-name") != name: menu_go(pg, "まとめ" if name == "情報まとめ" else name)

def settings(q):
    q.click(".bottom-nav .bn-settings")

def attach_image(q, choice="そのまま"):
    """写真のボタンで画像を置く（1枚なら写真の編集が画面いっぱいに出る。そのまま保存）"""
    q.set_input_files("#file-media", ICON); q.wait_for_selector(".img-editor")
    q.click(".ie-save"); q.wait_for_selector(".editor img[data-att]")

def new_screen(q, sel=".fab"):
    """新しいメモの画面を開き、本文にカーソルが当たるまで待つ（当たる前に題名を入れると、文字が本文に入ってしまう）"""
    q.click(sel)
    try: q.wait_for_function("document.activeElement && document.activeElement.classList.contains('editor')", timeout=5000)
    except Exception: pass

def new_memo(pg, title, genre="体験", body=None):
    new_screen(pg); pg.fill("#title", title); pg.click(f".genre-pick >> text={genre}")
    if body: pg.click(".editor"); pg.keyboard.insert_text(body)
    pg.click("#title"); pg.click(".save-btn"); pg.wait_for_selector(".bottom-nav"); time.sleep(0.2)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector(".fab")

    # 作成・保存・一覧
    new_memo(pg, "京都取材", body="鞍馬で火祭を見た")
    new_memo(pg, "単独メモ", genre="学び")
    check("上部のアプリ名は参考画像の文字の形のロゴ", pg.locator(".brand svg.logo[aria-label=ヒフミヨ] path").count() >= 4)
    check("メモが一覧に出る", pg.locator(".memo-card").count() == 2)

    # 検索画面（下のアイコンの「検索」）: 言葉・ジャンルで探す
    menu_go(pg, "検索"); pg.fill("#q", "火祭"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("検索画面でキーワード検索", pg.inner_text(".tab-name") == "検索" and pg.locator(".search-tab .memo-card").count() == 1)
    check("検索窓の下の絞り込みが隠れない", pg.evaluate("(()=>{const s=document.querySelector('#genre-search');const r=s.getBoundingClientRect();return document.elementFromPoint(r.left+5,r.top+5)===s})()"))
    pg.fill("#q", ""); pg.keyboard.press("Enter"); pg.select_option("#genre-search", "学び"); time.sleep(0.2)
    check("ジャンル絞り込み", pg.locator(".search-tab .memo-card").count() == 1)
    pg.click(".search-close"); time.sleep(0.2)
    check("✕で検索の言葉・ジャンルを消せる", pg.input_value("#q") == "" and pg.input_value("#genre-search") == "")
    menu_go(pg, "最近")
    check("最近は絞り込まずに全部のメモ", pg.inner_text(".tab-name") == "最近" and pg.locator(".memo-card").count() == 2)

    # ツリー（階層）は廃止: タブ・閲覧画面・編集画面に出ない
    new_memo(pg, "鞍馬の火祭")
    check("ツリーのタブがない", pg.locator(".tabs >> text=ツリー").count() == 0)
    check("カードは題名・日付・冒頭・ジャンルだけ（フォルダ名・時刻なし）", pg.locator(".memo-card .list-tag").count() == 0 and ":" not in pg.locator(".memo-card .card-date").first.inner_text())
    pg.locator(".memo-card", has_text="京都取材").click(); pg.wait_for_selector(".view-title")
    check("閲覧画面の上部バーに題名、背景に大きくジャンル（「メモを読む」はない）", pg.inner_text("header .view-title") == "京都取材" and "体験" in pg.inner_text("header .genre-mark") and pg.locator("header.topbar.g-体験").count() == 1 and "メモを読む" not in pg.inner_text("header"))
    check("アプリ名はヒフミヨ", pg.title() == "ヒフミヨ")
    check("閲覧画面の題名は斜体にしない", pg.evaluate("getComputedStyle(document.querySelector('header .view-title')).fontStyle") == "normal")
    check("閲覧画面に階層の欄がない", pg.locator(".child-sec, .tree-path").count() == 0 and "階層" not in pg.inner_text(".view-doc"))

    # タグを押すと、検索窓を開いた検索画面を重ねて開き、戻ると閲覧画面へ
    pg.go_back(); time.sleep(0.3)
    new_memo(pg, "タグ付きメモ", body="タグの確認")
    pg.locator(".memo-card", has_text="タグ付きメモ").click(); pg.wait_for_selector(".view-title")
    pg.click(".menu-btn"); pg.click(".menu >> text=編集"); time.sleep(0.3); pg.keyboard.insert_text(" #取材"); pg.click(".save-btn"); pg.wait_for_selector(".view-title"); time.sleep(0.3)
    check("本文の「#〜」はタグの水色で押せる（下のタグの行に重ねて出さない）", pg.evaluate("(()=>{const t=document.querySelector('.view-body .hashtag');return !!t&&t.textContent==='#取材'&&getComputedStyle(t).color==='rgb(18, 180, 245)'&&!document.querySelector('.view-tags')&&!document.querySelector('header .tag-chip')})()"))
    check("戻るボタンと題名の1行目の高さがそろう", pg.evaluate("(()=>{const r=e=>e.getBoundingClientRect();const t=r(document.querySelector('header .view-title')),b=r(document.querySelector('header .back'));return Math.abs((b.top+b.height/2)-(t.top+14))<3})()"))
    check("題名はタグの有無で位置が変わらず、文字は20px", pg.evaluate("(()=>{const t=document.querySelector('header .view-title');return Math.abs(t.getBoundingClientRect().top-document.querySelector('header.topbar').getBoundingClientRect().top-39)<4&&getComputedStyle(t).fontSize==='20px'})()"))
    check("パスは右（今の画面）のタブが上に重なる", pg.evaluate("(()=>{const c=[...document.querySelectorAll('.crumbs .crumb')];return c.every((e,i)=>i===0||+getComputedStyle(e).zIndex>+getComputedStyle(c[i-1]).zIndex)})()"))
    pg.click(".view-body .hashtag"); time.sleep(0.4)
    check("タグを押すと検索窓を開いた検索画面になる", pg.inner_text(".tab-name") == "検索" and pg.locator(".search-panel").is_visible() and pg.input_value("#q") == "#取材" and pg.locator(".memo-card", has_text="タグ付きメモ").count() == 1)
    check("パス表示はタブの形で「ホーム」から今の画面まで", pg.inner_text(".crumb.home") == "ホーム" and pg.locator(".crumbs .crumb").count() == 3 and "検索" in pg.inner_text(".crumb.current"))
    pg.go_back(); time.sleep(0.4)
    check("戻るとタグを押す前の閲覧画面に戻る", pg.locator("header .view-title").count() == 1 and pg.inner_text("header .view-title") == "タグ付きメモ", pg.evaluate("document.querySelector('#app').innerText.slice(0,200)+' | '+JSON.stringify(history.state)"))
    pg.go_back(); time.sleep(0.3)
    check("ホームの検索はタグの検索の影響を受けない", pg.locator(".filter-chip").count() == 0 and not pg.locator(".search-panel").is_visible())
    pg.locator(".memo-card", has_text="京都取材").click(); pg.wait_for_selector(".view-title")

    # 戻る操作（Android のスワイプと同じ）
    pg.go_back(); time.sleep(0.3)
    check("戻る操作で前の画面へ", pg.locator(".bottom-nav").count() == 1)

    # 上部バーの色（画面ごとに違う色・スマホ上端の帯も同じ色）
    tab(pg, "最近"); time.sleep(0.2)
    bars = {}
    bars["search"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    tc_search = pg.evaluate("document.querySelector('meta[name=theme-color]').content")
    pg.locator(".memo-card").first.click(); pg.wait_for_selector(".view-title"); time.sleep(0.6)   # 帯の色は画面を描いてから変わる
    bars["view"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    check("スマホ上端の帯が画面に合わせて変わる", tc_search != pg.evaluate("document.querySelector('meta[name=theme-color]').content"))
    pg.click(".menu-btn"); pg.click(".menu >> text=編集")
    bars["edit"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    check("メモ画面の上下のバーは検索画面と同じ色・閲覧画面は違う色", bars["edit"] == bars["search"] and bars["view"] != bars["search"], str(bars))
    check("メモ画面の左上は「×」", pg.locator(".topbar .back svg").count() == 1 and pg.get_attribute(".topbar .back", "aria-label") == "閉じる")

    # 本文にカーソルが当たるまで待つ（遅い環境では描画のあと少しかかる）
    try: pg.wait_for_function("document.activeElement && document.activeElement.classList.contains('editor')", timeout=5000)
    except Exception: pass
    time.sleep(0.2)
    check("メモ画面を開くと本文にカーソル（キーボードが出る）・パス表示はない・保存は右上", pg.evaluate("document.activeElement.classList.contains('editor')") and pg.locator(".crumbs").count() == 0 and pg.locator("header .save-btn").count() == 1 and pg.locator(".edit-actions, header .btn.danger").count() == 0)
    check("本文の入力中だけ、本文のボタン（▶・カメラ・#・写真）をキーボードの上に、等間隔で出す", pg.locator(".fmt-bar.floating").is_visible() and pg.locator(".fmt-bar .more-btn").count() == 1 and pg.locator(".fmt-media button").count() == 3 and pg.locator(".fmt-bar [aria-label='ファイルを置く']").count() == 0 and pg.evaluate("(()=>{const bs=[document.querySelector('.more-btn'),...document.querySelectorAll('.fmt-media button')].map(b=>{const r=b.getBoundingClientRect();return r.left+r.width/2});const g=bs.slice(1).map((x,i)=>x-bs[i]);return Math.max(...g)-Math.min(...g)<3})()"))
    pg.go_back(); time.sleep(0.5)
    check("本文の入力中の戻る操作は左上の「×」と同じ（変更がなければ前の画面へ）", pg.locator(".view-title").count() == 1 and pg.locator(".edit-screen").count() == 0)
    pg.click(".menu-btn"); pg.click(".menu >> text=編集"); pg.wait_for_selector(".edit-screen"); time.sleep(0.3)
    # 編集中に戻る → 未保存の確認が出る
    pg.fill("#title", "京都取材（仮）"); time.sleep(0.2); pg.go_back(); time.sleep(0.3)
    check("未保存のまま戻ると確認が出る（保存・破棄を選べる）", pg.locator(".modal").count() == 1 and pg.locator(".modal .btn.primary", has_text="保存").count() == 1)
    pg.click(".modal .btn.danger"); time.sleep(0.4)
    if pg.locator(".view-title").count(): pg.go_back()
    pg.wait_for_selector(".bottom-nav"); time.sleep(0.2)
    check("破棄すると最初の画面へ・変更は保存されない", pg.locator(".memo-card", has_text="京都取材（仮）").count() == 0)

    # フォルダ画面で新規メモ → 保存後はフォルダ画面に戻る
    tab(pg, "フォルダ")
    check("フォルダのタブの上部バーも検索画面と同じ色", pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor") == bars["search"])
    pg.click(".fab"); pg.fill("#newlist", "京都"); pg.click(".modal >> text=作成"); time.sleep(0.3)
    if pg.locator(".modal").count(): pg.click(".modal >> text=キャンセル"); time.sleep(0.2)
    check("フォルダ画面の上部は名前の左にフォルダのアイコン（「フォルダ」の見出しなし）", pg.locator(".folder-title .folder-ico svg").count() == 1 and pg.locator(".list-head-label").count() == 0)
    check("パスのタブは透けない（重なりが見えない）", pg.evaluate("(()=>{const c=document.querySelector('.crumb:not(.current)');return !c||!getComputedStyle(c).backgroundColor.startsWith('rgba')})()"))
    check("2画面からパス表示を出す（丸角・斜体なし）", pg.locator(".crumbs .crumb").count() == 2 and pg.evaluate("(()=>{const c=getComputedStyle(document.querySelector('.crumb.current'));return c.clipPath==='none'&&parseFloat(c.borderTopLeftRadius)>0&&c.fontStyle==='normal'})()"))
    check("「保存済みのメモを入れる」ボタンはない", pg.locator("text=保存済みのメモを入れる").count() == 0)
    check("フォルダの中の上部バーも検索画面と同じ色・名前の変更ボタンはない", pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor") == bars["search"] and pg.locator("header [aria-label='フォルダ名を変更']").count() == 0)
    check("フォルダの中の右下は「＋」だけの丸いボタン", pg.evaluate("(()=>{const f=document.querySelector('.fab');return f.classList.contains('round')&&f.textContent.trim()===''})()"))
    pg.click(".fab")
    check("右下のボタンで「保存済から追加」「新規追加」を選べる（ふわっと出る）", pg.locator(".fab-menu >> text=保存済から追加").is_visible() and pg.locator(".fab-menu >> text=新規追加").is_visible() and pg.evaluate("getComputedStyle(document.querySelector('.fab-menu button')).animationName") == "fab-in")
    pg.click(".fab"); time.sleep(0.05)
    check("もう一度押すと、引っ込めてから閉じる", pg.evaluate("document.querySelector('.fab-menu').classList.contains('closing')"))
    time.sleep(0.4)
    check("閉じたあとは隠れる", pg.locator(".fab-menu").is_hidden())
    pg.evaluate("document.querySelector('main').append(Object.assign(document.createElement('div'),{id:'pad',style:'height:2000px'}))")
    pg.mouse.move(200, 400); pg.mouse.wheel(0, 300); time.sleep(0.5)
    check("フォルダの中も下へスクロールすると上のバーと「＋」をしまう", pg.evaluate("document.querySelector('.screen').classList.contains('chrome-hidden')"))
    pg.mouse.wheel(0, -300); time.sleep(0.5); pg.evaluate("document.getElementById('pad').remove()")
    pg.click(".fab"); time.sleep(0.3)
    new_screen(pg, ".fab-menu >> text=新規追加"); pg.fill("#title", "フォルダ内メモ"); pg.click(".genre-pick >> text=学び"); pg.click(".save-btn"); time.sleep(0.4)
    check("フォルダで作ったメモは保存後フォルダ画面に戻る", pg.locator(".folder-title").count() == 1 and pg.locator(".memo-card", has_text="フォルダ内メモ").count() == 1)

    # 選択モードのままパンくずで戻っても、その後の「戻る」が効く
    long_press(pg, pg.locator(".memo-card").first)
    check("フォルダ画面でもメモの長押しで選択が始まる", pg.locator(".select-bar").count() == 1 and pg.locator(".memo-card.picked").count() == 1)
    pg.click(".topbar .back"); time.sleep(0.4)
    if pg.locator(".bottom-nav").count() == 0: pg.click(".topbar .back"); time.sleep(0.4)
    tab(pg, "最近"); pg.locator(".memo-card").first.click(); pg.wait_for_selector(".view-title")
    pg.go_back(); time.sleep(0.3)
    check("選択モード後も戻る操作が効く", pg.locator(".bottom-nav").count() == 1)

    tab(pg, "フォルダ")
    check("フォルダ一覧の更新日は「更新」の文字ではなくアイコン", pg.locator(".list-sub .upd-ico svg").count() >= 1 and "更新" not in pg.inner_text(".list-sub"))
    pg.click(".list-row .open"); time.sleep(0.3)
    # フォルダ → 閲覧 → 編集で削除すると、フォルダ画面に戻り「戻る」もずれない
    pg.locator(".memo-card", has_text="フォルダ内メモ").click(); pg.wait_for_selector(".view-title")
    pg.click(".menu-btn"); pg.click(".menu >> text=削除"); time.sleep(0.2)
    if pg.locator(".modal").count(): pg.click(".modal >> text=Yes")
    time.sleep(0.6)
    check("閲覧画面で削除するとフォルダ画面に戻る", pg.locator(".folder-title").count() == 1 and pg.locator(".memo-card", has_text="フォルダ内メモ").count() == 0)
    pg.go_back(); time.sleep(0.4)
    check("削除後の戻る操作で最初の画面へ", pg.locator(".bottom-nav").count() == 1)

    # 本文エディタ（本文より上は題名とジャンルだけ・書式ボタンは1行）
    tab(pg, "最近"); pg.click(".fab")
    check("題名の欄は「題名」だけ", pg.get_attribute("#title", "placeholder") == "題名")
    pg.click(".genre-pick >> text=体験"); pg.click(".save-btn"); time.sleep(0.3)
    check("題名も本文も空なら保存できない", pg.locator(".edit-screen").count() == 1 and "題名か本文を入力してください" in " ".join(pg.locator(".toast").all_inner_texts()))
    check("フォルダはプルダウンで選ぶ", pg.locator("select#elist").count() == 1)
    check("メモ画面の下部の見出しは「タグ」「フォルダ」だけ", "そのほかの設定" not in pg.inner_text("main") and "自由に付けられます" not in pg.inner_text("main") and "フォルダに入れる" not in pg.inner_text("main"))
    check("新規メモで本文が1画面目に見える", pg.evaluate("document.querySelector('.editor').getBoundingClientRect().top < 400"))
    check("題名・ジャンル・フォルダは本文より下・タグ欄と添付欄はない", pg.evaluate("(()=>{const e=document.querySelector('.editor').getBoundingClientRect().top;return document.querySelector('#title').getBoundingClientRect().top>e&&document.querySelector('.genre-pick').getBoundingClientRect().top>e&&!document.querySelector('#taginput')&&!document.querySelector('.att-grid, .drop')&&!document.querySelector('.parent-box')})()"))
    check("箇条書きのボタンはない", pg.locator(".fmt-bar >> text=•").count() == 0)
    check("ジャンルの選択はアイコン付きでチェック印なし", pg.locator(".genre-pick button svg").count() == 3 and "✓" not in pg.inner_text(".genre-pick"))
    check("書式ボタンが1行に収まる", pg.evaluate("(()=>{const f=document.querySelector('.fmt-bar');return f.scrollWidth<=f.clientWidth+1})()"))
    pg.click("#title")
    check("本文と題名は1つの枠（境目に線）・直近の題名は出さない", pg.locator(".recent-titles").count() == 0 and pg.evaluate("(()=>{const t=document.querySelector('#title');return !!t.closest('.editor-box')&&getComputedStyle(t).borderTopWidth==='1px'})()"))
    pg.click(".topbar .back"); time.sleep(0.3)
    if pg.locator(".modal").count(): pg.click(".modal .btn.danger")
    pg.wait_for_selector(".bottom-nav")
    tab(pg, "最近"); pg.click(".fab")
    try: pg.wait_for_function("document.activeElement && document.activeElement.classList.contains('editor')", timeout=5000)
    except Exception: pass
    pg.keyboard.insert_text("書きかけ"); time.sleep(0.2); pg.go_back(); time.sleep(0.5)
    check("新規メモで本文の入力中に戻る操作をすると「×」と同じく保存・破棄を選ぶ", pg.locator(".modal .btn.primary", has_text="保存").count() == 1)
    pg.click(".modal .btn.danger"); pg.wait_for_selector(".bottom-nav"); time.sleep(0.3)
    tab(pg, "最近"); new_screen(pg); pg.fill("#title", "書式"); pg.click(".genre-pick >> text=アイデア"); pg.click(".editor")
    pg.click(".more-btn")
    check("▶ を押すと書式のボタン（見出し〜リンク）に切り替わる", pg.locator(".fmt-more .head-btn").is_visible() and pg.locator(".fmt-more [aria-label=リンク]").is_visible() and not pg.locator(".fmt-media").is_visible())
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
    pg.set_input_files("#file-media", ICON); pg.wait_for_selector(".img-editor"); time.sleep(0.3)
    check("写真を1枚選ぶと写真の編集が画面いっぱいに出る", pg.evaluate("(()=>{const r=document.querySelector('.img-editor').getBoundingClientRect();return r.width===innerWidth&&r.height===innerHeight})()") and pg.locator(".ie-crop .ie-h").count() == 4)
    check("四隅の周りには指でつかむための余白がある", pg.evaluate("(()=>{const h=document.querySelector('.ie-holder').getBoundingClientRect(),s=document.querySelector('.ie-stage').getBoundingClientRect();return h.left-s.left>=20&&s.right-h.right>=20&&h.top-s.top>=20})()"))
    check("「枠を動かしたり〜」の説明文はない・元に戻すはアイコン", "枠を動かしたり" not in pg.inner_text(".img-editor") and pg.locator(".ie-panel [aria-label='切り取りを元に戻す'] svg").count() == 1)
    hc = pg.locator(".ie-crop").bounding_box()
    # 角の少し外側（画像の外）からでもつかめる
    pg.mouse.move(hc["x"] + hc["width"] + 14, hc["y"] + hc["height"] + 14); pg.mouse.down(); pg.mouse.move(hc["x"] + hc["width"] - 60, hc["y"] + hc["height"] - 60, steps=4); pg.mouse.up()
    pg.mouse.move(hc["x"] - 12, hc["y"] - 12); pg.mouse.down(); pg.mouse.move(hc["x"] + 30, hc["y"] + 30, steps=4); pg.mouse.up()
    check("四隅を（少し外からでも）引っぱって範囲を変えられる", pg.evaluate("(()=>{const c=document.querySelector('.ie-crop').getBoundingClientRect(),h=document.querySelector('.ie-holder').getBoundingClientRect();return c.width<h.width-50&&c.left>h.left+5})()"))
    hc = pg.locator(".ie-crop").bounding_box(); pg.mouse.move(hc["x"] + hc["width"] / 2, hc["y"] + 2); pg.mouse.down(); pg.mouse.move(hc["x"] + hc["width"] / 2, hc["y"] + 22, steps=3); pg.mouse.up()
    check("辺をつかんで1方向だけ縮められる", pg.evaluate("document.querySelector('.ie-crop').getBoundingClientRect().top") > hc["y"] + 10)
    pg.click(".ie-tabs [data-t=adjust]"); time.sleep(0.2)
    check("切り取りは別の道具に替えると反映される", pg.evaluate("(()=>{const c=document.querySelector('.ie-base');return c.width<512})()"))
    check("補正の道具に切り替えると下からふわっと出る", pg.evaluate("document.querySelector('.ie-pin:last-child').classList.contains('enter')"))
    pg.click(".ie-param.auto")
    check("自動補正でコントラストは下げない", pg.evaluate("parseInt(document.querySelector('.ie-param[data-p=c] small').textContent)") >= 100)
    rb = pg.locator(".ie-ruler").bounding_box(); cx = rb["x"] + rb["width"] / 2; cy = rb["y"] + rb["height"] / 2
    pg.click(".ie-param[data-p=b]"); pg.click("[aria-label='すべて100%に戻す']")
    check("100%に戻すボタンで元の値に", pg.inner_text(".ier-val") == "100%" and "brightness(100%)" in pg.evaluate("document.querySelector('.ie-base').style.filter"))
    pg.mouse.move(cx, cy); pg.mouse.down(); pg.mouse.move(cx - 60, cy, steps=5); pg.mouse.up()
    check("目盛りを左右に滑らせて値を変えられる", pg.inner_text(".ier-val") == "112%", pg.inner_text(".ier-val"))
    pg.mouse.move(cx, cy); pg.mouse.down(); pg.mouse.move(cx + 50, cy, steps=5); pg.mouse.up()
    check("100%の近くでは100%に吸い付く", pg.inner_text(".ier-val") == "100%", pg.inner_text(".ier-val"))
    pg.click(".ie-tabs [data-t=draw]"); hb = pg.locator(".ie-holder").bounding_box()
    pg.mouse.move(hb["x"] + 20, hb["y"] + 20); pg.mouse.down(); pg.mouse.move(hb["x"] + 80, hb["y"] + 60, steps=5); pg.mouse.up()
    check("指で描ける（取り消しはアイコンで押せる）", pg.locator(".ie-panel [aria-label='取り消し'] svg").count() == 1 and pg.locator(".ie-panel [aria-label='取り消し']").is_enabled())
    pg.click(".ie-panel [aria-label='消しゴム']")
    check("消しゴムを選べる", pg.get_attribute(".ie-panel [aria-label='消しゴム']", "aria-pressed") == "true")
    pg.mouse.move(hb["x"] + 20, hb["y"] + 20); pg.mouse.down(); pg.mouse.move(hb["x"] + 80, hb["y"] + 60, steps=5); pg.mouse.up()
    pg.click(".ie-tabs [data-t=text]"); pg.focus(".ie-input")
    check("文字を打っている間は、下の道具と保存を隠す", pg.evaluate("document.querySelector('.img-editor').classList.contains('typing')") and not pg.locator(".ie-save").is_visible())
    pg.fill(".ie-input", "メモ"); pg.click(".ie-panel [aria-label='文字を置く']")
    check("文字を置ける・説明文はない", pg.locator(".ie-text").is_visible() and pg.inner_text(".ie-text") == "メモ" and "指で" not in pg.inner_text(".ie-panel"))
    pg.click(".ie-panel [aria-label='選んだ文字を消す']")
    check("置いた文字を消せる", pg.locator(".ie-text").count() == 0)
    pg.fill(".ie-input", "メモ"); pg.click(".ie-panel [aria-label='文字を置く']")
    time.sleep(0.4)   # 文字を打ち終わると下の道具が戻り、写真の位置が少し動くので待つ
    fs0 = pg.evaluate("parseFloat(document.querySelector('.ie-text').style.fontSize)")
    pg.evaluate("document.querySelector('.ie-text').dataset.mark='1'")
    tb = pg.locator(".ie-tsize").bounding_box(); pg.mouse.move(tb["x"] + 13, tb["y"] + 13); pg.mouse.down(); pg.mouse.move(tb["x"] + 70, tb["y"] + 40, steps=5); pg.mouse.up()
    check("右下の丸を引っぱって文字を大きくできる", pg.evaluate("parseFloat(document.querySelector('.ie-text').style.fontSize)") > fs0 * 1.2)
    check("大きさを変えている間も文字は作り直さない（一瞬消えない）", pg.evaluate("document.querySelector('.ie-text').dataset.mark") == "1")
    pg.click(".ie-panel [aria-label='決定（次の文字へ）']")
    check("✓で決めると、次の文字を入れられる", pg.input_value(".ie-input") == "" and pg.locator(".ie-panel [aria-label='文字を置く']").count() == 1)
    pg.fill(".ie-input", "二つ目"); pg.click(".ie-panel [aria-label='文字を置く']")
    check("2つ目の文字も置ける", pg.locator(".ie-text").count() == 2)
    time.sleep(0.3)
    check("保存は下にある（上部バーの保存と重ならない）", pg.evaluate("document.querySelector('.ie-save').getBoundingClientRect().top > innerHeight / 2"))
    pg.click(".ie-save"); pg.wait_for_selector(".editor img[data-att]"); time.sleep(0.3)
    check("保存すると写真の編集が閉じる", pg.locator(".img-editor").count() == 0)
    check("本文に置いた画像は最初「中」の大きさ", pg.evaluate("document.querySelector('.editor img[data-att]').style.width") == "50%")
    check("写真のボタン1つで本文に画像が入る", pg.locator(".editor img[data-att]").count() == 1)
    src0 = pg.get_attribute(".editor img[data-att]", "src")
    check("本文の画像の右上に「×」がある", pg.locator(".img-x").count() == 1)
    pg.click("#title"); time.sleep(0.2)
    pg.click(".editor img[data-att]"); pg.wait_for_selector(".img-editor"); time.sleep(0.3)
    check("置いた画像を押しても本文にカーソルが入らない（キーボードが出ない）", not pg.evaluate("document.activeElement && document.activeElement.classList.contains('editor')"))
    check("置いた画像を押すと、小窓ではなく写真の編集が開く（大きさもここで）", pg.locator(".pop").count() == 0 and pg.locator(".ie-crop .ie-h").count() == 4 and pg.locator(".ie-tabs [data-t=size]").count() == 1)
    pg.click(".ie-tabs [data-t=text]"); time.sleep(0.2)
    check("前に入れた文字は、開き直しても動かしたり消したりできる", pg.locator(".ie-text").count() == 2)
    pg.click(".ie-tabs [data-t=size]"); time.sleep(0.3)
    check("大きさは、メモの見本の上で幅を見せる", pg.locator(".isp-img").is_visible() and pg.evaluate("document.querySelector('.isp-img').style.width") == "50%")
    pg.click(".ie-chip:text-is('全幅')")
    check("大きさを選ぶと見本の画像の幅も変わる", pg.evaluate("document.querySelector('.isp-img').style.width") == "100%")
    pg.go_back(); time.sleep(0.4)
    check("写真の編集は戻る操作でやめられる（メモ画面のまま）", pg.locator(".img-editor").count() == 0 and pg.locator(".edit-screen").count() == 1 and pg.get_attribute(".editor img[data-att]", "src") == src0)
    pg.click(".editor img[data-att]"); pg.wait_for_selector(".img-editor"); time.sleep(0.3)
    hc = pg.locator(".ie-crop").bounding_box(); pg.mouse.move(hc["x"] + hc["width"] - 4, hc["y"] + hc["height"] - 4); pg.mouse.down(); pg.mouse.move(hc["x"] + hc["width"] - 44, hc["y"] + hc["height"] - 44, steps=4); pg.mouse.up()
    pg.click(".ie-tabs [data-t=text]"); time.sleep(0.2); pg.locator(".ie-text").first.click(); pg.click(".ie-panel [aria-label='選んだ文字を消す']")
    pg.click(".ie-tabs [data-t=size]"); pg.click(".ie-chip:text-is('大')")
    pg.click(".ie-save"); time.sleep(0.5)
    check("編集した画像に置き換わり、大きさも変わる", pg.get_attribute(".editor img[data-att]", "src") != src0 and pg.locator(".editor img[data-att]").count() == 1 and pg.evaluate("document.querySelector('.editor img[data-att]').style.width") == "75%")
    check("写真の編集を閉じたあと、メモ画面の保存ボタンは押されていない", pg.locator(".edit-screen").count() == 1)
    check("写真・動画のボタンは写真と動画だけを選ぶ", pg.get_attribute("#file-media", "accept") == "image/*,video/*" and pg.get_attribute("#file-cam", "capture") == "environment")
    pg.click("#title"); pg.click(".save-btn"); pg.wait_for_selector(".bottom-nav"); time.sleep(0.2)
    pg.locator(".memo-card", has_text="書式").click(); pg.wait_for_selector(".view-title")
    check("閲覧画面の本文は16px・行間は詰めめ", pg.evaluate("(()=>{const c=getComputedStyle(document.querySelector('.view-body'));return c.fontSize==='16px'&&parseFloat(c.lineHeight)/16<=1.65})()"))
    check("写真だけのメモは下の「添付ファイル」欄を出さない", pg.locator(".att-details").count() == 0)
    check("所属フォルダがないメモはフォルダの欄も出さない", pg.locator(".view-folders").count() == 0)
    pg.click(".view-body img"); pg.wait_for_selector(".lightbox img")
    check("拡大表示は左上に「×」、右上に保存", pg.evaluate("(()=>{const c=document.querySelector('.lb-close').getBoundingClientRect(),s=document.querySelector('.lb-save').getBoundingClientRect();return c.left<60&&s.right>innerWidth-60})()") and pg.get_attribute(".lb-save", "download") is not None)
    pg.mouse.click(195, 820); time.sleep(0.3)
    check("画像の外（黒い所）を押しても閉じない", pg.locator(".lightbox").count() == 1)
    pg.go_back(); time.sleep(0.4)
    check("戻る操作で拡大表示を閉じ、閲覧画面に戻る", pg.locator(".lightbox").count() == 0 and pg.locator(".view-title").count() == 1)
    pg.click(".view-body img"); pg.wait_for_selector(".lightbox img"); pg.click(".lb-close"); time.sleep(0.3)
    check("「×」で拡大表示が閉じる（原寸表示はない）", pg.locator(".lightbox").count() == 0 and "原寸" not in pg.content())
    pg.go_back(); pg.wait_for_selector(".bottom-nav"); time.sleep(0.6)
    check("画像付きのメモは X の投稿のようにカードに画像を出す", pg.evaluate("(()=>{const c=[...document.querySelectorAll('.memo-card')].find(e=>e.textContent.includes('書式'));const t=c&&c.querySelector('.tw-media img');return !!t&&!!t.getAttribute('src')})()"))
    check("カードの左上に自分のアイコン", pg.locator(".memo-card .tw-ava img").count() >= 1)
    pg.locator(".memo-card", has_text="書式").click(); pg.wait_for_selector(".view-title")
    body = pg.inner_html(".view-body")
    check("保存後も書式・見出しが残る", "<b>" in body and "<h2>" in body and "tc-rose" in body, body[:200])
    check("ゼロ幅スペースが残らない", "​" not in body)
    pg.evaluate("document.documentElement.dataset.theme='dark'")
    check("ダークモードで文字色が明るい色に", pg.evaluate("getComputedStyle(document.querySelector('.view-body .tc-rose')).color") == "rgb(242, 154, 172)")
    pg.evaluate("document.documentElement.dataset.theme='light'")

    # 編集→保存で前の画面へ
    pg.click(".menu-btn"); pg.click(".menu >> text=編集"); pg.fill("#title", "書式（改）")
    pg.click(".save-btn"); time.sleep(0.5)
    check("編集保存後は閲覧画面に戻る", pg.locator(".view-title").count() == 1 and pg.inner_text(".view-title") == "書式（改）")

    # ジャンル2つのメモ・フォルダの表示・閲覧画面を開く／閉じる動き（動きありの画面で確かめる）
    ac = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ap = ac.new_page(); ap.on("pageerror", lambda e: errors.append(str(e))); ap.clock.install(); ap.goto(URL); ap.wait_for_selector(".fab")
    ap.click(".bottom-nav .bn-lists"); time.sleep(0.4); ap.click(".fab"); ap.fill("#newlist", "旅"); ap.click(".modal >> text=作成"); time.sleep(0.6)
    if ap.locator(".modal").count(): ap.click(".modal >> text=キャンセル"); time.sleep(0.4)
    if ap.locator(".folder-title").count() == 0: ap.click(".list-row .open"); time.sleep(0.5)
    ap.click(".fab"); time.sleep(0.3); new_screen(ap, ".fab-menu >> text=新規追加"); ap.keyboard.insert_text("景色。#京都")
    ap.fill("#title", "二つのジャンル"); ap.click(".genre-pick >> text=体験"); ap.click(".genre-pick >> text=アイデア"); ap.click(".save-btn"); ap.wait_for_selector(".folder-title"); time.sleep(0.6)
    ap.locator(".memo-card").first.click(); time.sleep(0.05)
    check("メモを開くとき、押したカードから広がる（ズーム）・背景はアプリの背景のまま", ap.locator(".nav-ghost.under").count() == 1 and ap.locator(".view-screen.zooming.pagebg").count() == 1)
    time.sleep(0.7)
    check("開き終わったら前の画面の写しは消える", ap.locator(".nav-ghost").count() == 0)
    check("ジャンル2つなら上部バーを2色で塗り分ける（混ぜない）", ap.evaluate("(()=>{const t=document.querySelector('.view-screen .topbar');return t.classList.contains('multi')&&getComputedStyle(t).backgroundImage.includes('105deg')})()"))
    check("ジャンルの色は均等に分ける", "50%" in ap.evaluate("document.querySelector('.view-screen .topbar').style.backgroundImage"))
    check("背景のジャンル名は、それぞれの色の帯の上に（赤に体験・黄にアイデア）", ap.evaluate("(()=>{const w=document.querySelector('.genre-mark-wrap').getBoundingClientRect();const e=document.querySelector('.genre-mark.gm-exp'),i=document.querySelector('.genre-mark.gm-idea');if(!e||!i)return false;const c=x=>{const r=x.getBoundingClientRect();return (r.left+r.width/2-w.left)/w.width};return e.textContent==='体験'&&i.textContent==='アイデア'&&c(e)<0.5&&c(i)>0.5})()"))
    check("「。」のすぐ後の「#〜」もタグになる", ap.locator(".view-body .hashtag", has_text="#京都").count() == 1)
    check("所属フォルダは読みやすい大きさで押せる形", ap.locator(".view-folder", has_text="旅").count() == 1 and ap.evaluate("parseFloat(getComputedStyle(document.querySelector('.view-folder')).fontSize)") >= 14)
    ap.go_back(); time.sleep(0.05)
    check("戻るときは閲覧画面がカードへ縮んで戻る（ズーム）", ap.locator(".nav-ghost.over.pagebg").count() == 1 and ap.locator(".folder-title").count() == 1)
    time.sleep(0.7)
    check("閉じ終わったら写しは消える", ap.locator(".nav-ghost").count() == 0)
    check("カードの題名は2行まで折り返して出す（日時は題名の後ろ）", ap.evaluate("(()=>{const l=document.querySelector('.memo-card .tw-line');return !!l&&getComputedStyle(l).webkitLineClamp==='2'&&!!l.querySelector('.card-date')})()"))
    check("フォルダの中の「＋」は他の画面と同じ位置", ap.evaluate("innerHeight - document.querySelector('.fab').getBoundingClientRect().bottom") >= 50)
    ap.click(".fab"); time.sleep(0.3); ap.click(".fab-menu >> text=新規追加"); time.sleep(0.05)
    check("「＋」から開くメモ画面は右から入る（ムーブイン）", ap.locator(".edit-screen.zooming").count() == 1 and "matrix" in ap.evaluate("getComputedStyle(document.querySelector('.edit-screen')).transform"))
    time.sleep(0.6)
    check("入り終わったら前の画面の写しは残らない（ちらつかない）", ap.locator(".nav-ghost").count() == 0 and ap.locator(".zooming, .pagebg").count() == 0)
    ap.click(".topbar .back"); time.sleep(0.05)
    check("閉じるときは右へ抜ける（ムーブアウト）", ap.locator(".nav-ghost.over").count() == 1)
    time.sleep(0.7)
    # フォルダ一覧 → フォルダの中も右から入る
    ap.go_back(); time.sleep(0.6)
    ap.click(".bottom-nav .bn-lists"); time.sleep(0.5); ap.click(".list-row .open"); time.sleep(0.05)
    check("フォルダを押すとフォルダの中が右から入る", ap.locator(".screen.zooming .folder-title").count() == 1)
    time.sleep(0.6); ap.go_back(); time.sleep(0.6)
    # 最近: 読んでいた位置から戻る・新しい並びのボタン
    ap.evaluate("window.__fade=[];new MutationObserver(()=>{const a=document.querySelector('.home-screen .swipe-area');if(a)for(const c of ['tab-out','tab-in'])if(a.classList.contains(c)&&!__fade.includes(c))__fade.push(c)}).observe(document.body,{subtree:true,attributes:true,childList:true,attributeFilter:['class']})")
    ap.click(".bottom-nav .bn-memos"); time.sleep(0.5)
    check("下のアイコンで切り替えるときは軽く消えてから出る", ap.evaluate("__fade.join(',')") == "tab-out,tab-in", ap.evaluate("__fade.join(',')"))
    time.sleep(0.5)
    for i in range(7):
        new_screen(ap); ap.keyboard.insert_text("長い本文。" * 40); ap.fill("#title", f"並び{i}"); ap.click(".genre-pick >> text=体験"); ap.click(".save-btn"); ap.wait_for_selector(".bottom-nav"); time.sleep(0.6)
    ap.mouse.move(200, 400); ap.mouse.wheel(0, 900); time.sleep(0.6)
    y0 = ap.evaluate("scrollY"); idv = ap.evaluate("(()=>{const c=[...document.querySelectorAll('.memo-card')].find(e=>e.getBoundingClientRect().top>120);return c.dataset.id})()")
    ap.locator(f".memo-card[data-id='{idv}']").click(); time.sleep(0.7); ap.go_back(); time.sleep(0.7)
    check("閲覧画面から戻ると、読んでいた位置から（先頭に戻らない）", abs(ap.evaluate("scrollY") - y0) < 30, str((y0, ap.evaluate("scrollY"))))
    ap.clock.fast_forward("11:00"); time.sleep(0.3)
    check("並びが入れ替わる時間になると「新しい並びを見る」が出る", ap.locator(".fresh-pill").is_visible())
    ap.click(".fresh-pill"); time.sleep(0.8)
    check("押すと消えて先頭へ", ap.locator(".fresh-pill").count() == 0 and ap.evaluate("scrollY") < 5)
    check("最近のアイコンは家の形・画面の名前はバーの右端", ap.evaluate("(()=>{const n=document.querySelector('.tab-name').getBoundingClientRect();return n.right>innerWidth-40})()"))
    ac.close()

    # マーカー・文字色を付けて「なし」「標準」で外す（選んだ部分だけ外れる）
    pg.goto(URL); pg.wait_for_selector(".fab")
    new_screen(pg); pg.fill("#title", "マーカー"); pg.click(".genre-pick >> text=学び"); pg.click(".editor"); pg.keyboard.insert_text("あいうえおかきく"); pg.click(".more-btn")
    SEL = """(([s,e])=>{const ed=document.querySelector('.editor');const w=document.createTreeWalker(ed,NodeFilter.SHOW_TEXT);let n,pos=0,r=document.createRange(),a=0,b=0;
while((n=w.nextNode())){const L=n.data.length; if(!a&&s<=pos+L){r.setStart(n,s-pos);a=1} if(!b&&e<=pos+L){r.setEnd(n,e-pos);b=1} pos+=L}
const sel=getSelection();sel.removeAllRanges();sel.addRange(r);})"""
    VIS = """(t)=>{const ed=document.querySelector('.editor');const w=document.createTreeWalker(ed,NodeFilter.SHOW_TEXT);let n;while((n=w.nextNode())){if(n.data.includes(t)){let el=n.parentElement;while(el&&el!==ed){const c=getComputedStyle(el).backgroundColor;if(c!=='rgba(0, 0, 0, 0)')return c;el=el.parentElement}return 'none'}}return '?'}"""
    def marker(k): pg.click("button[aria-label=マーカー]"); pg.click(f".pop .sw[aria-label='マーカー {k}']")
    pg.evaluate(SEL, [0, 6]); marker("黄")
    check("マーカーが付く", pg.evaluate(VIS, "あい") != "none")
    pg.evaluate(SEL, [2, 4]); marker("なし")
    check("マーカー「なし」で選んだ部分だけ外れる", pg.evaluate(VIS, "うえ") == "none" and pg.evaluate(VIS, "おか") != "none")
    pg.evaluate(SEL, [0, 8]); marker("なし")
    check("全体を選んで「なし」で全部外れる", "hl-" not in pg.inner_html(".editor"))
    pg.evaluate(SEL, [8, 8]); marker("緑"); pg.keyboard.insert_text("けこ"); marker("なし"); pg.keyboard.insert_text("さし")
    check("カーソルだけでもマーカーを付けて外せる", pg.evaluate(VIS, "けこ") != "none" and pg.evaluate(VIS, "さし") == "none")
    check("下の添付の欄はない（本文のボタンで置く）", pg.locator("label.add-file, .att-grid").count() == 0)
    pg.click("#title"); pg.click(".save-btn"); pg.wait_for_selector(".bottom-nav"); time.sleep(0.2)

    # 情報まとめ: 検索結果からまとめ → 画面表示・ファイル保存
    menu_go(pg, "検索"); pg.fill("#q", "火祭"); pg.keyboard.press("Enter"); time.sleep(0.2)
    menu_go(pg, "まとめ"); pg.wait_for_selector(".rp-doc"); time.sleep(0.3)
    check("検索中にメニューの「まとめ」でその条件の情報まとめ画面へ", pg.inner_text(".tab-name") == "情報まとめ" and not pg.locator(".search-panel").is_visible())
    check("まとめはジャンル → メモの題名の順に畳んで並ぶ", pg.locator(".rp-doc details.rp-sec").count() >= 1 and pg.locator(".rp-doc details.rp-sec[open]").count() == 0 and pg.locator(".rp-index .rp-idx svg").count() >= 1)
    pg.locator(".rp-sec > summary").first.click(); time.sleep(0.2)
    check("ジャンルを押すとメモの題名が並ぶ（中身は畳んだまま）", pg.locator(".rp-memo-t").first.is_visible() and not pg.locator(".rp-memo-body").first.is_visible())
    pg.locator(".rp-memo > summary").first.click(); time.sleep(0.2)
    check("題名を押すと中身が開く", pg.locator(".rp-memo-body").first.is_visible() and "火祭" in pg.inner_text(".rp-memo-body >> nth=0"))
    check("まとめの末尾に「画像」の欄はない", "画像" not in [t.strip() for t in pg.locator(".rp-doc h2").all_inner_texts()])
    with pg.expect_download() as dl: pg.click(".rp-tools [aria-label=ファイルに保存]")
    import shutil; out = Path(__file__).resolve().parent / "_report_test.html"; shutil.copy(dl.value.path(), out)
    html = out.read_text(encoding="utf-8"); out.unlink()
    check("まとめを1つのファイルに保存できる", dl.value.suggested_filename.endswith(".html") and "rp-doc" in html and "blob:" not in html)
    import re as _re
    check("ファイル名は「まとめの題名_日付」", bool(_re.fullmatch(r"火祭のまとめ_\d{8}\.html", dl.value.suggested_filename)), dl.value.suggested_filename)
    check("「メモにする」はなく、ダウンロードが目立つボタン", pg.locator(".rp-tools >> text=メモにする").count() == 0 and pg.locator(".rp-tools .btn.primary.rp-save").count() == 1)
    check("まとめの日付は作成日時だけ（件数は出さない）", "件のメモから" not in pg.inner_text(".rp-meta") and ":" in pg.inner_text(".rp-meta"))
    pg.go_back(); pg.wait_for_selector(".bottom-nav"); time.sleep(0.3)
    check("情報まとめから戻る操作で「最近」へ（絞り込みは解除）", pg.inner_text(".tab-name") == "最近" and pg.locator(".filter-chip").count() == 0)
    tab(pg, "フォルダ"); pg.click(".list-row .open"); time.sleep(0.2)
    pg.click(".fab"); pg.click(".fab-menu >> text=保存済から追加"); pg.locator(".modal .ref-item").first.click(); pg.click(".modal >> text=決定"); time.sleep(0.3)
    check("フォルダの中の上部は「まとめる」だけ（名前の変更はフォルダ一覧で）", pg.evaluate("(()=>{const b=[...document.querySelectorAll('header .head-actions > *')];return b.length===1&&b[0].classList.contains('report-btn')})()"))
    pg.click(".report-btn"); pg.wait_for_selector(".rp-doc")
    check("まとめ画面の上部バーも検索画面と同じ色", pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor") == bars["search"])
    pg.go_back(); time.sleep(0.3)
    pg.click(".report-btn"); pg.wait_for_selector(".rp-doc")
    check("フォルダからもまとめを作れる", pg.inner_text(".rp-title") == "京都のまとめ")
    pg.go_back(); time.sleep(0.2); pg.go_back(); pg.wait_for_selector(".bottom-nav"); tab(pg, "最近")

    # 検索画面はスマホの戻る操作で「最近」に戻る（検索も解除）・検索履歴は出さない（撤廃）
    menu_go(pg, "検索")
    for q in ["一", "二", "三", "四"]: pg.fill("#q", q); pg.keyboard.press("Enter"); time.sleep(0.15)
    check("検索履歴は出さない", pg.locator(".hist-row, .hist-chips").count() == 0 and "最近" not in pg.inner_text(".search-panel"))
    pg.go_back(); time.sleep(0.3)
    check("戻る操作で最近に戻る", pg.inner_text(".tab-name") == "最近" and pg.locator(".search-panel").count() == 0)
    menu_go(pg, "検索")
    check("戻ってから開いた検索画面は空", pg.input_value("#q") == "")
    pg.fill("#q", "めも"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("ひらがなで探してもカタカナのメモが見つかる", pg.locator(".memo-card", has_text="単独メモ").count() == 1)
    pg.fill("#q", "ﾒﾓ"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("半角カタカナでも見つかる", pg.locator(".memo-card", has_text="単独メモ").count() == 1)
    pg.fill("#q", "京都"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("検索画面ではフォルダも見つかる", pg.locator(".search-tab .list-row", has_text="京都").count() == 1 and pg.locator(".search-tab .memo-card").count() >= 1)
    pg.go_back(); time.sleep(0.3)
    nav = [b.get_attribute("aria-label") for b in pg.locator(".bottom-nav button").all()]
    check("画面の下にアイコンだけの列（最近・フォルダ・検索・まとめ・設定）", nav == ["最近", "フォルダ", "検索", "まとめ", "設定"] and pg.locator(".bottom-nav button svg").count() == 5 and pg.inner_text(".bottom-nav").strip() == "", str(nav))
    check("上部バーにタブ・検索・まとめ・設定・メニューのボタンはない", pg.locator("header .tabs, header .search-toggle, header .report-btn, header [aria-label=設定], header .nav-toggle").count() == 0)
    check("今の画面のアイコンは選んだ色", pg.get_attribute(".bn-memos", "aria-current") == "page")
    check("上部バーの画面名の左にアイコン", pg.locator(".tab-name svg").count() == 1)
    check("検索画面の「＋」は下端から少し上", pg.evaluate("innerHeight - document.querySelector('.fab').getBoundingClientRect().bottom") >= 50)
    check("上部バーに今の画面の名前", pg.inner_text(".tab-name") == "最近")
    check("押したときの四角い色は出さない（丸いボタン等は形に合わせた表示）", pg.evaluate("getComputedStyle(document.querySelector('.fab')).webkitTapHighlightColor") == "rgba(0, 0, 0, 0)")
    check("タグは鮮やかな水色", pg.evaluate("getComputedStyle(document.querySelector('.tag-mini')||document.body).color") == "rgb(18, 180, 245)" if pg.locator(".tag-mini").count() else True)
    check("検索画面の右下のボタンは「＋」だけの丸いボタン", pg.evaluate("(()=>{const f=document.querySelector('.fab');return f.classList.contains('round')&&f.textContent.trim()===''&&f.getAttribute('aria-label')==='新規メモ'})()"))
    check("上部バーに水色の線を付けない", pg.evaluate("getComputedStyle(document.querySelector('.topbar'),'::after').content") in ("none", "normal"))
    check("検索窓に「検索」ボタンはない（Enter で検索）", pg.locator(".search-go").count() == 0)
    check("最近タブに件数を出さない", pg.locator(".result-meta").count() == 0)
    check("カードにジャンルのアイコン（ジャンルの色）", pg.evaluate("(()=>{const b=document.querySelector('.memo-card .tw-g');const c=b&&getComputedStyle(b);return !!c&&c.backgroundColor!=='rgba(0, 0, 0, 0)'&&!!b.querySelector('svg')})()"))
    check("カードの下段にジャンルの重複表示はない", pg.locator(".memo-card .card-foot .genre").count() == 0)
    check("作成から1時間未満は「○分前」", pg.locator(".memo-card .card-date").first.inner_text().endswith("分前"))

    # まとめ: キーワードなしでも作れて、作成日時の期間（今日など）で絞れる
    menu_go(pg, "まとめ"); pg.wait_for_selector(".rp-tools")
    check("条件なしでは「すべてのメモのまとめ」を作らない", pg.locator(".rp-doc").count() == 0 and "まとめる条件を選んでください" in pg.inner_text(".rp-holder"))
    check("フォルダと期間の選択欄は同じ幅", pg.evaluate("(()=>{const a=document.querySelector('#rp-period'),b=document.querySelector('#rp-list');return !b||Math.abs(a.getBoundingClientRect().width-b.getBoundingClientRect().width)<2})()"))
    check("フォルダ・期間は「未選択」から選ぶ", pg.locator("#rp-period option").first.inner_text() == "未選択")
    check("キーワードなしでは「関連部分／全文」を出さない", pg.locator(".rp-seg").count() == 0)
    pg.select_option("#rp-period", "today"); time.sleep(0.3)
    import datetime as _dt
    check("期間「今日」でまとめられる", pg.inner_text(".rp-title") == _dt.date.today().strftime("%Y/%m/%d") + "のまとめ")
    pg.select_option("#rp-period", "lastmonth"); time.sleep(0.3)
    check("期間に該当なしなら案内が出る", "まとめるメモがありません" in pg.inner_text(".rp-holder"))
    pg.go_back(); pg.wait_for_selector(".bottom-nav")

    # ダークモードでも画面ごとのバーが背景とはっきり違う色
    pg.evaluate("document.documentElement.dataset.theme='dark'")
    check("ダークモードのバーが背景と見分けられる", pg.evaluate("""(()=>{const L=c=>{const m=c.match(/\\d+/g).slice(0,3).map(x=>{x/=255;return x<=.03928?x/12.92:((x+.055)/1.055)**2.4});return .2126*m[0]+.7152*m[1]+.0722*m[2]};
      const a=L(getComputedStyle(document.querySelector('.topbar')).backgroundColor),b=L(getComputedStyle(document.body).backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)>1.8})()"""))
    pg.evaluate("document.documentElement.dataset.theme='light'")

    # 検索画面: 横スライドでタブ切り替え（画面の端からの操作は「戻る」なので反応しない）
    SWIPE = """async ([x0,x1])=>{const el=document.querySelector('.swipe-area');const mk=(x)=>new Touch({identifier:1,target:el,clientX:x,clientY:400});
const fire=(type,x,on)=>el.dispatchEvent(new TouchEvent(type,{touches:on?[mk(x)]:[],changedTouches:[mk(x)],bubbles:true}));
fire('touchstart',x0,true);
for(let k=1;k<=8;k++){fire('touchmove',x0+(x1-x0)*k/8,true);await new Promise(r=>setTimeout(r,16));}
window.__midX=getComputedStyle(document.querySelector('.swipe-track')).transform;window.__peer=!!document.querySelector('.swipe-track > .swipe-peer');
fire('touchend',x1,false);}"""
    pg.evaluate(SWIPE, [300, 120]); time.sleep(0.6)
    check("スライド中は指に合わせて一覧が動く", pg.evaluate("window.__midX") not in ("none", ""))
    check("スライド中は隣の画面の中身がすぐ横に並ぶ（空白を作らない）", pg.evaluate("window.__peer") is True)
    check("左へスライドでフォルダ", pg.inner_text(".tab-name") == "フォルダ")
    pg.evaluate(SWIPE, [8, 250]); time.sleep(0.6)
    check("画面の端からの操作ではタブが変わらない", pg.inner_text(".tab-name") == "フォルダ")
    pg.evaluate(SWIPE, [300, 120]); time.sleep(0.6)
    check("フォルダからさらにスライドで検索", pg.inner_text(".tab-name") == "検索" and pg.locator(".search-panel").count() == 1)
    pg.evaluate(SWIPE, [300, 120]); time.sleep(0.6)
    check("検索からさらにスライドで情報まとめ", pg.inner_text(".tab-name") == "情報まとめ" and pg.locator(".rp-tools").count() == 1)
    pg.evaluate(SWIPE, [300, 120]); time.sleep(0.6)
    check("情報まとめからさらにスライドで最近に戻る", pg.inner_text(".tab-name") == "最近")
    pg.evaluate(SWIPE, [120, 300]); time.sleep(0.6)
    check("逆向きのスライドで最近から情報まとめへ", pg.inner_text(".tab-name") == "情報まとめ")
    pg.go_back(); time.sleep(0.3)
    check("スライドで移った先から戻る操作で最近へ", pg.inner_text(".tab-name") == "最近")

    # まとめ: フォルダを選べる
    menu_go(pg, "まとめ"); pg.wait_for_selector("#rp-list"); pg.select_option("#rp-period", "all"); time.sleep(0.3)
    pg.select_option("#rp-list", label="京都"); time.sleep(0.3)
    check("まとめでフォルダを選べる", pg.inner_text(".rp-title").startswith("京都のまとめ"))
    pg.go_back(); pg.wait_for_selector(".bottom-nav")

    # 検索画面: 「null」が出ない・「選択」は上部の固定バー
    check("検索画面に「null」が出ない", "null" not in pg.inner_text("body"))
    check("選択ボタンはない（長押しで選ぶ）", pg.locator(".select-btn").count() == 0)

    # バックアップの書き出し → 「前回の書き出し」がその場で更新される
    pg.goto(URL); pg.wait_for_selector(".fab"); settings(pg)
    with pg.expect_download() as dl: pg.click(".modal >> text=バックアップを書き出す")
    check("バックアップを書き出せる", dl.value.suggested_filename.startswith("hifumiyo-backup-"))
    time.sleep(0.3)
    check("前回の書き出し日時がすぐ更新される", "まだありません" not in pg.inner_text(".modal"))
    # 背景を端末の画像から選べる・元に戻せる
    check("設定のアイコン・背景はそれぞれ「変更」ボタン1つ", pg.locator(".modal .ava-sec .tw-ava img").count() == 1 and pg.locator(".modal .ava-sec button").count() == 1 and pg.locator(".modal .bg-sec button").count() == 1 and pg.locator(".modal .change-btn").count() == 2)
    with pg.expect_file_chooser() as fc: pg.click(".modal .bg-sec .change-btn")
    fc.value.set_files(ICON)
    # 画像を縮めて保存し終えるまで待つ（遅い端末でも決まった秒数で判定しない）
    try: pg.wait_for_function("document.documentElement.classList.contains('has-bg')", timeout=8000)
    except Exception: pass
    time.sleep(0.2)
    check("背景を端末の画像にできる", pg.evaluate("document.documentElement.classList.contains('has-bg')") and pg.locator(".bg-preview").is_visible())
    pg.click(".modal .bg-sec .change-btn"); pg.click(".modal button:text-is('元に戻す')"); time.sleep(0.4)
    check("背景を元に戻せる", not pg.evaluate("document.documentElement.classList.contains('has-bg')"))
    check("背景の画像はカメラを起動しない指定（端末内の画像だけ）", pg.evaluate("[...document.querySelectorAll('.modal input[type=file]')].every(i=>!/image\\/\\*/.test(i.accept)&&!i.hasAttribute('capture'))"))
    check("バックアップの欄に「端末内の保存の保護」は出さない", "保存の保護" not in pg.inner_text(".modal"))
    pg.click(".modal [aria-label=上部バーを透過]"); time.sleep(0.3)
    check("上部バーを透過でき、境目に線が出る（アイコンには枠）", pg.evaluate("document.documentElement.classList.contains('clear-bar') && getComputedStyle(document.querySelector('.topbar.bar-search')).borderBottomWidth === '2px' && getComputedStyle(document.querySelector('.topbar .brand .logo')).filter.includes('drop-shadow')"))
    pg.click(".modal [aria-label=上部バーを透過]"); time.sleep(0.2)
    check("透過をオフに戻せる", not pg.evaluate("document.documentElement.classList.contains('clear-bar')"))
    check("設定は右上の✕で閉じる（下の「閉じる」ボタンはない）", pg.locator(".modal .modal-head .modal-x[aria-label=閉じる]").count() == 1 and pg.locator(".modal .btn", has_text="閉じる").count() == 0 and "閲覧画面以外" not in pg.inner_text(".modal"))
    check("設定の見出しは斜体にしない", pg.evaluate("getComputedStyle(document.querySelector('.settings-sec h4')).fontStyle") == "normal")
    pg.click(".modal .modal-x")

    # オフライン起動
    pg.goto(URL); pg.wait_for_selector(".fab"); time.sleep(1)
    ctx.set_offline(True); pg.reload(); pg.wait_for_selector(".memo-card", timeout=8000)
    check("オフラインで起動・一覧表示", pg.locator(".memo-card").count() >= 4)
    ctx.set_offline(False)

    # 長押しで選んだメモからまとめを作る
    long_press(pg, pg.locator(".memo-card").first)
    pg.click(".select-bar >> text=まとめる"); pg.wait_for_selector(".rp-tools"); time.sleep(0.3)
    check("選んだメモからまとめを作れる", pg.inner_text(".rp-title").startswith("選んだ1件のメモ") and pg.inner_text(".rp-pick") == "1件を選択中")
    pg.click(".rp-pick"); pg.wait_for_selector(".modal .ref-item")
    check("まとめるメモを選ぶ小窓の印は長押しの選択と同じ形", pg.locator(".modal .ref-item .pick-box svg").count() == 1 and "☑" not in pg.inner_text(".modal"))
    pg.click(".modal >> text=キャンセル"); time.sleep(0.2)
    pg.go_back(); pg.wait_for_selector(".bottom-nav"); time.sleep(0.3)
    check("まとめから戻ると選択モードは終わっている", pg.locator(".select-bar").count() == 0)

    # まとめて削除
    n_cards = pg.locator(".memo-card").count()
    if pg.evaluate("document.documentElement.scrollHeight > innerHeight + 300"):
        pg.mouse.move(200, 400); pg.mouse.wheel(0, 600); time.sleep(0.6)
        hidden = pg.evaluate("document.querySelector('.home-screen').classList.contains('chrome-hidden')")
        pg.mouse.wheel(0, -250); time.sleep(0.6)
        shown = not pg.evaluate("document.querySelector('.home-screen').classList.contains('chrome-hidden')")
        check("下へスクロールで上下のバーをしまい、上へスクロールで戻す", hidden and shown)
        pg.evaluate("scrollTo(0,0)"); time.sleep(0.3)
    long_press(pg, pg.locator(".memo-card").first)
    check("メモの長押しで選択が始まり、そのメモが選ばれる（離しても外れない）", pg.locator(".select-bar").count() == 1 and pg.locator(".memo-card.picked").count() == 1)
    pg.locator(".memo-card").nth(1).click()
    check("選択中の下のバー（削除など）は、一番下までスクロールしなくても画面の下に出る", pg.evaluate("(()=>{const b=document.querySelector('.select-bar').getBoundingClientRect();return b.bottom<=innerHeight+1&&b.top<innerHeight})()"))
    check("選択中は押すたびに選ぶ・外す", pg.locator(".memo-card.picked").count() == 2)
    pg.locator(".memo-card").nth(1).click()
    check("選択のチェックは太い線の印", pg.evaluate("(()=>{const s=document.querySelector('.memo-card.picked .pick-box svg');return !!s&&parseFloat(s.getAttribute('stroke-width'))>=3})()"))
    pg.click(".select-bar >> text=削除")
    check("削除の確認の「Yes」は警告色の赤", "danger-solid" in pg.get_attribute(".modal >> text=Yes", "class"))
    pg.click(".modal >> text=Yes"); time.sleep(0.4)
    check("まとめて削除", pg.locator(".select-bar").count() == 0)
    # 作成・更新の日時: 1時間未満は「○分前」、24時間未満は「○時間前」、それより前は日付
    tc = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
    tp = tc.new_page(); tp.clock.install(time=1790000000000); tp.goto(URL); tp.wait_for_selector(".fab")
    new_memo(tp, "時計のメモ")
    tp.clock.fast_forward(25 * 60 * 1000); tp.reload(); tp.wait_for_selector(".memo-card")
    check("作成25分後は「25分前」", tp.inner_text(".memo-card .card-date") == "25分前", tp.inner_text(".memo-card .card-date"))
    tp.clock.fast_forward(2 * 3600 * 1000); tp.reload(); tp.wait_for_selector(".memo-card")
    check("作成2時間半後は「2時間前」", tp.inner_text(".memo-card .card-date") == "2時間前", tp.inner_text(".memo-card .card-date"))
    tp.locator(".memo-card").click(); tp.wait_for_selector(".view-title")
    check("閲覧画面の作成日時も同じ表示（「作成」はアイコン）", "2時間前" in tp.inner_text(".view-meta") and tp.locator(".view-meta .date-ico[aria-label=作成] svg").count() == 1 and "作成" not in tp.inner_text(".view-meta"), tp.inner_text(".view-meta"))
    tp.go_back(); tp.clock.fast_forward(22 * 3600 * 1000); tp.reload(); tp.wait_for_selector(".memo-card")
    check("24時間をすぎたら日付", "/" in tp.inner_text(".memo-card .card-date"), tp.inner_text(".memo-card .card-date"))
    tc.close()

    # フォルダ一覧: 削除アイコンはなく、長押しで選んで削除できる
    tab(pg, "フォルダ"); time.sleep(0.3)
    check("フォルダ一覧に削除アイコンはない", pg.locator(".list-row [aria-label=フォルダを削除]").count() == 0)
    n_lists = pg.locator(".list-row").count()
    long_press(pg, pg.locator(".list-row .open").first)
    check("フォルダの長押しで選択が始まる", pg.locator(".select-bar").count() == 1 and pg.locator(".list-row.picked").count() == 1)
    pg.click(".select-bar >> text=削除"); pg.click(".modal >> text=Yes"); time.sleep(0.5)
    check("選んだフォルダを削除できる", pg.locator(".list-row").count() == n_lists - 1 and pg.locator(".select-bar").count() == 0)
    tab(pg, "最近"); time.sleep(0.2)

    # Googleドライブ同期（偽の接続先で確認）: オンにしたときだけ送る・別の端末で同期すると戻る・オフの間は送らない
    gas = FakeGas()
    def device():
        c = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
        c.route(FakeGas.URL, gas.handle)
        q = c.new_page(); q.on("pageerror", lambda e: errors.append(str(e))); q.goto(URL); q.wait_for_selector(".fab"); return q
    def sync_on(q, key="aikotoba-123", url=FakeGas.URL):
        settings(q)
        if q.locator(".sync-setup").get_attribute("open") is None: q.click(".sync-setup summary")
        q.fill("#sync-url", url); q.fill("#sync-key", key); q.click(".sync-btn"); q.wait_for_timeout(1500)
        st = q.inner_text(".sync-status"); q.click(".modal .modal-x"); return st
    pa = device()
    new_screen(pa); pa.fill("#title", "同期のメモ"); pa.click(".genre-pick >> text=体験"); attach_image(pa)
    pa.click(".save-btn"); pa.wait_for_timeout(5000)
    check("同期がオフの間はドライブへ送らない", gas.calls == [])
    # 複数アカウントでログイン中にコピーした「/macros/u/1/s/…」の形でも、自動で直してつながる
    st = sync_on(pa, url=FakeGas.URL.replace("/macros/s/", "/macros/u/1/s/"))
    check("「同期」を押すとドライブへ送る（URLの形も自動で直す）", st.startswith("オン") and gas.data and len(gas.data["memos"]) == 1 and len(gas.files) == 1, st)
    pb = device()
    check("合言葉が違うと分かる", "合言葉が違います" in sync_on(pb, "machigai"))
    settings(pb); pb.click(".sync-btn"); pb.wait_for_timeout(300); pb.click(".modal .modal-x")
    sync_on(pb); pb.wait_for_timeout(500)
    check("別の端末で同期するとメモと添付が戻る", pb.locator(".memo-card", has_text="同期のメモ").count() == 1 and pb.locator(".memo-card .tw-media").count() == 1)
    pb.locator(".memo-card").first.click(); pb.click(".menu-btn"); pb.click(".menu >> text=削除"); pb.click(".modal >> text=Yes"); pb.wait_for_timeout(5500)
    # 接続先のプログラムが古い（保存前に公開した）ときは、Google のエラー画面を見分けて直し方を示す
    pc = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
    pc.route(FakeGas.URL, lambda r: r.fulfill(status=200, content_type="text/html", body="<html><body>スクリプト関数が見つかりません: doPost</body></html>"))
    qc = pc.new_page(); qc.goto(URL); qc.wait_for_selector(".fab")
    check("古い接続先のときは直し方を表示", "プログラムが古いまま" in sync_on(qc))
    pc.unroute(FakeGas.URL); pc.route(FakeGas.URL, lambda r: r.fulfill(status=404, content_type="text/html", body="<html><head><title>ページが見つかりません</title></head></html>"))
    settings(qc); qc.click(".sync-btn"); qc.wait_for_timeout(300); qc.click(".modal .modal-x")
    st404 = sync_on(qc)
    check("404 のときは段階とGoogleの表示を添える", "接続確認" in st404 and "ページが見つかりません" in st404, st404)
    pc.close()
    pa.reload(); pa.wait_for_selector(".fab"); pa.wait_for_timeout(2500)
    check("削除も他の端末に反映・同期のオンは開き直しても続く", pa.locator(".memo-card").count() == 0 and pa.evaluate("localStorage.getItem('sm.syncOn')") == "true")
    # 大きな添付ファイルは小分けに送る・途中で通信が切れてもメモは同期され、次の同期で続きを送る
    import base64 as _b64
    big = bytes((i * 37) % 256 for i in range(1_200_000))
    new_screen(pb); pb.fill("#title", "大きな添付"); pb.click(".genre-pick >> text=学び")
    pb.set_input_files("#file-media", files=[{"name": "big.bin", "mimeType": "application/octet-stream", "buffer": big}]); pb.wait_for_selector(".editor a[data-att]")
    gas.fail_next = 3   # 最初の送信は3回とも通信切れ（自動のやり直しも失敗）
    pb.click(".save-btn"); pb.wait_for_timeout(9000)
    settings(pb); st = pb.inner_text(".sync-status")
    check("通信が切れてもメモは先にドライブへ・失敗した添付は件数で知らせる", any(m["title"] == "大きな添付" for m in gas.data["memos"]) and "添付ファイル1件" in st, st)
    pb.click(".sync-btn"); pb.wait_for_timeout(300); pb.click(".sync-btn"); pb.wait_for_timeout(4000)   # オフ→オンで今すぐ同期
    pb.click(".modal .modal-x")
    sent = [d for t, d in gas.files.values() if len(d) > 1_000_000]
    check("大きな添付は小分けで送られ、元通りにつながる", len(sent) == 1 and _b64.b64decode(sent[0]) == big and gas.calls.count("putChunk") >= 3)
    pa.reload(); pa.wait_for_selector(".fab"); pa.wait_for_timeout(5000)
    got = pa.evaluate("""() => new Promise(res => { const r = indexedDB.open('sosaku-memo'); r.onsuccess = () => { const q = r.result.transaction('files').objectStore('files').getAll(); q.onsuccess = () => res(q.result.map(f => f.blob.size)); }; })""")
    check("大きな添付を別の端末で小分けに受け取れる", len(big) in got, str(got))

    # アプリを画面に戻したとき: 同期オンなら他の端末のメモを取り込む・オフなら何もしない
    RESUME = "() => { Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true }); document.dispatchEvent(new Event('visibilitychange')); Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }"
    pa.wait_for_timeout(21000)   # 起動時の同期から20秒あける
    import copy as _cp
    other = _cp.deepcopy(gas.data); other["memos"].append({**other["memos"][0], "id": "m-from-other", "title": "別の端末で書いたメモ", "updatedAt": int(time.time() * 1000) + 5000, "attachments": []})
    gas.data = other
    pa.evaluate(RESUME); pa.wait_for_timeout(2500)
    check("画面に戻すと他の端末のメモを取り込む（同期オン）", pa.locator(".memo-card", has_text="別の端末で書いたメモ").count() == 1)
    settings(pb); pb.click(".sync-btn"); pb.wait_for_timeout(300); pb.click(".modal .modal-x")   # pb はオフに
    n = len(gas.calls); pb.wait_for_timeout(21000); pb.evaluate(RESUME); pb.wait_for_timeout(2000)
    check("同期オフなら画面に戻しても通信しない", len(gas.calls) == n)

    # Google の返事の受け取り口（googleusercontent.com）の一時的な 404 は、自動でやり直して同期を続ける
    def sync_now(q):
        settings(q); q.click(".sync-btn"); q.wait_for_timeout(300); q.click(".sync-btn"); q.wait_for_timeout(6000)
        st = q.inner_text(".sync-status"); q.click(".modal .modal-x"); return st
    gas.echo404 = {"listFiles": 2}
    st = sync_now(pa)
    check("返事の受け取り口の一時的な404は、その場でやり直して成功", st.startswith("オン") and gas.echo404["listFiles"] == 0, st)
    # 1分待ちを8秒に縮めて確かめる
    pa.add_init_script("(() => { const st = window.setTimeout; window.setTimeout = (f, d, ...a) => st(f, d === 60000 ? 8000 : d, ...a); })()")
    pa.reload(); pa.wait_for_selector(".fab"); pa.wait_for_timeout(3000)
    gas.echo404 = {"listFiles": 3}
    st = sync_now(pa)
    check("やり直しても404なら一時的な不調と知らせる", "一時的な不調" in st and "添付の確認" in st, st)
    pa.wait_for_timeout(9000); settings(pa); st = pa.inner_text(".sync-status"); pa.click(".modal .modal-x")
    check("少したつと自動でやり直して同期できる", st.startswith("オン"), st)

    # 古い接続先プログラム（版1）のときは更新を案内
    old = FakeGas(version=1); pd = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce"); pd.route(FakeGas.URL, old.handle)
    qd = pd.new_page(); qd.goto(URL); qd.wait_for_selector(".fab")
    check("古い版の接続先は更新を案内", "最新の gas/Code.gs" in sync_on(qd)); pd.close()

    b.close()

real_errors = [e for e in errors if "fonts.g" not in e]
check("JavaScript エラーなし", not real_errors, "; ".join(real_errors))
print(f"\n{'すべて成功' if not failures else str(len(failures)) + '件失敗'}")
sys.exit(1 if failures else 0)
