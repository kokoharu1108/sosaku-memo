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

def menu_go(pg, label):
    """上部バーのメニュー（三本線）から選ぶ"""
    pg.click(".nav-toggle"); pg.click(f".nav-menu button:has-text('{label}')"); time.sleep(0.35)

def tab(pg, name):
    """検索画面のタブ（最近・フォルダ・情報まとめ）へ。今その画面ならそのまま"""
    if pg.inner_text(".tab-name") != name: menu_go(pg, "まとめ" if name == "情報まとめ" else name)

def settings(q):
    q.click(".nav-toggle"); q.click(".nav-menu button:has-text('設定')")

def new_memo(pg, title, genre="体験", body=None):
    pg.click(".fab"); pg.fill("#title", title); pg.click(f".genre-pick >> text={genre}")
    if body: pg.click(".editor"); pg.keyboard.insert_text(body)
    pg.click("#title"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".nav-toggle"); time.sleep(0.2)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector(".fab")

    # 作成・保存・一覧
    new_memo(pg, "京都取材", body="鞍馬で火祭を見た")
    new_memo(pg, "単独メモ", genre="学び")
    check("上部のアプリ名は参考画像の文字の形のロゴ", pg.locator(".brand svg.logo[aria-label=ヒフミヨ] path").count() >= 4)
    check("メモが一覧に出る", pg.locator(".memo-card").count() == 2)

    # 検索パネル・ジャンル
    menu_go(pg, "検索"); pg.fill("#q", "火祭"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("キーワード検索", pg.locator(".memo-card").count() == 1)
    check("検索窓の下の絞り込みが隠れない", pg.evaluate("(()=>{const s=document.querySelector('#genre-search');const r=s.getBoundingClientRect();return document.elementFromPoint(r.left+5,r.top+5)===s})()"))
    pg.click(".filter-chip button"); pg.select_option("#genre-search", "学び"); time.sleep(0.1)
    check("ジャンル絞り込み", pg.locator(".memo-card").count() == 1)
    pg.click(".search-close"); time.sleep(0.2)
    check("検索窓を閉じると検索の言葉・ジャンルの絞り込みも解除される", pg.locator(".memo-card").count() == 2 and pg.locator(".filter-chip").count() == 0 and not pg.locator(".search-panel").is_visible())
    menu_go(pg, "検索")
    check("もう一度開くと検索窓・ジャンルは空", pg.input_value("#q") == "" and pg.input_value("#genre-search") == "")
    pg.click(".search-close"); time.sleep(0.2)

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
    pg.click(".menu-btn"); pg.click(".menu >> text=編集"); pg.fill("#taginput", "取材"); pg.keyboard.press("Enter"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".view-title"); time.sleep(0.3)
    check("閲覧画面のタグは本文の下（バーには出さない）で、検索画面と同じ水色・枠線なし", pg.evaluate("(()=>{const t=document.querySelector('.view-tags .tag-chip');return !!t&&!document.querySelector('header .tag-chip')&&t.getBoundingClientRect().top>document.querySelector('.view-meta').getBoundingClientRect().top&&getComputedStyle(t).borderTopWidth==='0px'&&getComputedStyle(t).color==='rgb(18, 180, 245)'})()"))
    check("戻るボタンと題名の1行目の高さがそろう", pg.evaluate("(()=>{const r=e=>e.getBoundingClientRect();const t=r(document.querySelector('header .view-title')),b=r(document.querySelector('header .back'));return Math.abs((b.top+b.height/2)-(t.top+14))<3})()"))
    check("題名はタグの有無で位置が変わらず、文字は20px", pg.evaluate("(()=>{const t=document.querySelector('header .view-title');return Math.abs(t.getBoundingClientRect().top-document.querySelector('header.topbar').getBoundingClientRect().top-39)<4&&getComputedStyle(t).fontSize==='20px'})()"))
    check("パスは右（今の画面）のタブが上に重なる", pg.evaluate("(()=>{const c=[...document.querySelectorAll('.crumbs .crumb')];return c.every((e,i)=>i===0||+getComputedStyle(e).zIndex>+getComputedStyle(c[i-1]).zIndex)})()"))
    pg.click(".view-tags .tag-chip"); time.sleep(0.4)
    check("タグを押すと検索窓を開いた検索画面になる", pg.locator(".search-panel").is_visible() and pg.input_value("#q") == "#取材" and pg.locator(".memo-card", has_text="タグ付きメモ").count() == 1)
    check("パス表示はタブの形で「ホーム」から今の画面まで", pg.inner_text(".crumb.home") == "ホーム" and pg.locator(".crumbs .crumb").count() == 3 and "検索" in pg.inner_text(".crumb.current"))
    pg.go_back(); time.sleep(0.4)
    check("戻るとタグを押す前の閲覧画面に戻る", pg.inner_text("header .view-title") == "タグ付きメモ")
    pg.go_back(); time.sleep(0.3)
    check("ホームの検索はタグの検索の影響を受けない", pg.locator(".filter-chip").count() == 0 and not pg.locator(".search-panel").is_visible())
    pg.locator(".memo-card", has_text="京都取材").click(); pg.wait_for_selector(".view-title")

    # 戻る操作（Android のスワイプと同じ）
    pg.go_back(); time.sleep(0.3)
    check("戻る操作で前の画面へ", pg.locator(".nav-toggle").count() == 1)

    # 上部バーの色（画面ごとに違う色・スマホ上端の帯も同じ色）
    tab(pg, "最近")
    bars = {}
    bars["search"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    tc_search = pg.evaluate("document.querySelector('meta[name=theme-color]').content")
    pg.locator(".memo-card").first.click(); pg.wait_for_selector(".view-title")
    bars["view"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    check("スマホ上端の帯が画面に合わせて変わる", tc_search != pg.evaluate("document.querySelector('meta[name=theme-color]').content"))
    pg.click(".menu-btn"); pg.click(".menu >> text=編集")
    bars["edit"] = pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor")
    check("メモ画面の上下のバーは検索画面と同じ色・閲覧画面は違う色", bars["edit"] == bars["search"] and bars["view"] != bars["search"], str(bars))

    # 編集中にパンくずで最初の画面へ → 未保存の確認が出る
    pg.fill("#title", "京都取材（仮）"); pg.click(".crumb.home"); time.sleep(0.3)
    check("未保存のままパンくずで離れると確認が出る", pg.locator(".modal").count() == 1)
    pg.click(".modal >> text=破棄して戻る"); pg.wait_for_selector(".nav-toggle"); time.sleep(0.2)
    check("破棄すると最初の画面へ・変更は保存されない", pg.locator(".memo-card", has_text="京都取材（仮）").count() == 0)

    # フォルダ画面で新規メモ → 保存後はフォルダ画面に戻る
    tab(pg, "フォルダ"); pg.click(".fab"); pg.fill("#newlist", "京都"); pg.click(".modal >> text=作成"); time.sleep(0.3)
    if pg.locator(".modal").count(): pg.click(".modal >> text=キャンセル"); time.sleep(0.2)
    check("フォルダ画面の上部は名前の左にフォルダのアイコン（「フォルダ」の見出しなし）", pg.locator(".folder-title .folder-ico svg").count() == 1 and pg.locator(".list-head-label").count() == 0)
    check("パスのタブは透けない（重なりが見えない）", pg.evaluate("(()=>{const c=document.querySelector('.crumb:not(.current)');return !c||!getComputedStyle(c).backgroundColor.startsWith('rgba')})()"))
    check("2画面からパス表示を出す（丸角・斜体なし）", pg.locator(".crumbs .crumb").count() == 2 and pg.evaluate("(()=>{const c=getComputedStyle(document.querySelector('.crumb.current'));return c.clipPath==='none'&&parseFloat(c.borderTopLeftRadius)>0&&c.fontStyle==='normal'})()"))
    check("「保存済みのメモを入れる」ボタンはない", pg.locator("text=保存済みのメモを入れる").count() == 0)
    pg.click(".fab")
    check("右下のボタンで「保存済から追加」「新規追加」を選べる", pg.locator(".fab-menu >> text=保存済から追加").is_visible() and pg.locator(".fab-menu >> text=新規追加").is_visible())
    pg.click(".fab-menu >> text=新規追加"); pg.fill("#title", "フォルダ内メモ"); pg.click(".genre-pick >> text=学び"); pg.click(".edit-actions .btn.primary"); time.sleep(0.4)
    check("フォルダで作ったメモは保存後フォルダ画面に戻る", pg.locator(".folder-title").count() == 1 and pg.locator(".memo-card", has_text="フォルダ内メモ").count() == 1)

    # 選択モードのままパンくずで戻っても、その後の「戻る」が効く
    long_press(pg, pg.locator(".memo-card").first)
    check("フォルダ画面でもメモの長押しで選択が始まる", pg.locator(".select-bar").count() == 1 and pg.locator(".memo-card.picked").count() == 1)
    pg.click(".topbar .back"); time.sleep(0.4)
    if pg.locator(".nav-toggle").count() == 0: pg.click(".topbar .back"); time.sleep(0.4)
    tab(pg, "最近"); pg.locator(".memo-card").first.click(); pg.wait_for_selector(".view-title")
    pg.go_back(); time.sleep(0.3)
    check("選択モード後も戻る操作が効く", pg.locator(".nav-toggle").count() == 1)

    tab(pg, "フォルダ")
    check("フォルダ一覧の更新日は「更新」の文字ではなくアイコン", pg.locator(".list-sub .upd-ico svg").count() >= 1 and "更新" not in pg.inner_text(".list-sub"))
    pg.click(".list-row .open"); time.sleep(0.3)
    # フォルダ → 閲覧 → 編集で削除すると、フォルダ画面に戻り「戻る」もずれない
    pg.locator(".memo-card", has_text="フォルダ内メモ").click(); pg.wait_for_selector(".view-title")
    pg.click(".menu-btn"); pg.click(".menu >> text=編集"); pg.click(".topbar .btn.danger"); time.sleep(0.2)
    if pg.locator(".modal").count(): pg.click(".modal >> text=Yes")
    time.sleep(0.6)
    check("編集画面で削除するとフォルダ画面に戻る", pg.locator(".folder-title").count() == 1 and pg.locator(".memo-card", has_text="フォルダ内メモ").count() == 0)
    pg.go_back(); time.sleep(0.4)
    check("削除後の戻る操作で最初の画面へ", pg.locator(".nav-toggle").count() == 1)

    # 本文エディタ（本文より上は題名とジャンルだけ・書式ボタンは1行）
    tab(pg, "最近"); pg.click(".fab")
    check("題名の欄は「題名」だけ", pg.get_attribute("#title", "placeholder") == "題名")
    pg.click(".genre-pick >> text=体験"); pg.click(".edit-actions .btn.primary"); time.sleep(0.3)
    check("題名も本文も空なら保存できない", pg.locator(".edit-actions").count() == 1 and "題名か本文を入力してください" in " ".join(pg.locator(".toast").all_inner_texts()))
    check("フォルダはプルダウンで選ぶ", pg.locator("select#elist").count() == 1)
    check("メモ画面の下部の見出しは「タグ」「フォルダ」だけ", "そのほかの設定" not in pg.inner_text("main") and "自由に付けられます" not in pg.inner_text("main") and "フォルダに入れる" not in pg.inner_text("main"))
    check("新規メモで本文が1画面目に見える", pg.evaluate("document.querySelector('.editor').getBoundingClientRect().top < 400"))
    check("タグ・フォルダは本文より下・階層の欄はない", pg.evaluate("(()=>{const e=document.querySelector('.editor').getBoundingClientRect().top;return document.querySelector('#taginput').getBoundingClientRect().top>e&&!document.querySelector('.parent-box')})()"))
    check("箇条書きのボタンはない", pg.locator(".fmt-bar >> text=•").count() == 0)
    check("ジャンルの選択はアイコン付きでチェック印なし", pg.locator(".genre-pick button svg").count() == 3 and "✓" not in pg.inner_text(".genre-pick"))
    check("書式ボタンが1行に収まる", pg.evaluate("(()=>{const f=document.querySelector('.fmt-bar');return f.scrollWidth<=f.clientWidth+1})()"))
    pg.click("#title"); check("題名を触ると直近の題名が出る", pg.locator(".recent-titles").is_visible())
    pg.click(".topbar .back"); time.sleep(0.3)
    if pg.locator(".modal").count(): pg.click(".modal >> text=破棄して戻る")
    pg.wait_for_selector(".nav-toggle")
    tab(pg, "最近"); pg.click(".fab"); pg.fill("#title", "書式"); pg.click(".genre-pick >> text=アイデア"); pg.click(".editor")
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
    pg.set_input_files("#file", ICON); pg.wait_for_selector(".att-tile img"); time.sleep(0.3)
    check("添付の縮小画像がファイル名に重ならない", pg.evaluate("(()=>{const t=document.querySelector('.att-tile');return t.querySelector('img').getBoundingClientRect().bottom<=t.querySelector('.name').getBoundingClientRect().top+1})()"))
    pg.click("#title"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".nav-toggle"); time.sleep(0.2)
    pg.locator(".memo-card", has_text="書式").click(); pg.wait_for_selector(".view-title")
    check("閲覧画面の本文は16px・行間は詰めめ", pg.evaluate("(()=>{const c=getComputedStyle(document.querySelector('.view-body'));return c.fontSize==='16px'&&parseFloat(c.lineHeight)/16<=1.65})()"))
    pg.click("text=添付ファイル（1件）")
    check("添付ファイルの欄はサイズまで枠内に収まる", pg.evaluate("document.querySelector('.att-size').getBoundingClientRect().right <= document.querySelector('.att-details').getBoundingClientRect().right"))
    pg.click(".att-row"); pg.wait_for_selector(".lightbox img")
    pg.click(".lightbox img"); time.sleep(0.2)
    check("画像を押しても原寸表示にならず、拡大表示が閉じる", pg.locator(".lightbox").count() == 0 and "原寸" not in pg.content())
    pg.go_back(); pg.wait_for_selector(".nav-toggle"); time.sleep(0.6)
    check("画像付きのメモはカードの右側に画像を薄く敷く", pg.evaluate("(()=>{const c=[...document.querySelectorAll('.memo-card')].find(e=>e.textContent.includes('書式'));const t=c&&c.querySelector('.card-thumb img');return !!t&&!!t.getAttribute('src')&&parseFloat(getComputedStyle(t.parentNode).opacity)<1})()"))
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

    # マーカー・文字色を付けて「なし」「標準」で外す（選んだ部分だけ外れる）
    pg.goto(URL); pg.wait_for_selector(".fab")
    pg.click(".fab"); pg.fill("#title", "マーカー"); pg.click(".genre-pick >> text=学び"); pg.click(".editor"); pg.keyboard.insert_text("あいうえおかきく")
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
    check("添付はドロップ表記なしのボタン", "ドロップ" not in pg.inner_text(".edit-screen, main") and pg.locator("label.add-file").count() == 1)
    check("下の保存バーも編集画面の色", pg.evaluate("getComputedStyle(document.querySelector('.edit-actions')).backgroundColor") == pg.evaluate("getComputedStyle(document.querySelector('.topbar')).backgroundColor"))
    pg.click("#title"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".nav-toggle"); time.sleep(0.2)

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
    pg.go_back(); pg.wait_for_selector(".nav-toggle"); time.sleep(0.3)
    check("情報まとめから戻る操作で「最近」へ（絞り込みは解除）", pg.inner_text(".tab-name") == "最近" and pg.locator(".filter-chip").count() == 0)
    tab(pg, "フォルダ"); pg.click(".list-row .open"); time.sleep(0.2)
    pg.click(".fab"); pg.click(".fab-menu >> text=保存済から追加"); pg.locator(".modal .ref-item").first.click(); pg.click(".modal >> text=決定"); time.sleep(0.3)
    check("フォルダ画面のまとめるボタンは鉛筆の右隣", pg.evaluate("(()=>{const b=[...document.querySelectorAll('header .head-actions > *')];return b.length===2&&b[1].classList.contains('report-btn')})()"))
    pg.click(".report-btn"); pg.wait_for_selector(".rp-doc")
    check("フォルダからもまとめを作れる", pg.inner_text(".rp-title") == "京都のまとめ")
    pg.go_back(); time.sleep(0.2); pg.go_back(); pg.wait_for_selector(".nav-toggle"); tab(pg, "最近")

    # 検索窓はスマホの戻る操作で閉じる（検索も解除）・検索履歴は出さない（撤廃）
    menu_go(pg, "検索")
    for q in ["一", "二", "三", "四"]: pg.fill("#q", q); pg.keyboard.press("Enter"); time.sleep(0.15)
    check("検索履歴は出さない", pg.locator(".hist-row, .hist-chips").count() == 0 and "最近" not in pg.inner_text(".search-panel"))
    pg.go_back(); time.sleep(0.3)
    check("戻る操作で検索窓が閉じ、検索も解除（画面はそのまま）", not pg.locator(".search-panel").is_visible() and pg.locator(".nav-toggle").count() == 1 and pg.locator(".filter-chip").count() == 0 and pg.inner_text(".tab-name") == "最近")
    menu_go(pg, "検索"); pg.fill("#q", "めも"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("ひらがなで探してもカタカナのメモが見つかる", pg.locator(".memo-card", has_text="単独メモ").count() == 1)
    pg.fill("#q", "ﾒﾓ"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("半角カタカナでも見つかる", pg.locator(".memo-card", has_text="単独メモ").count() == 1)
    pg.click(".search-close"); time.sleep(0.2)
    pg.click(".nav-toggle"); time.sleep(0.35)
    items = [t.strip() for t in pg.locator(".nav-menu button").all_inner_texts()]
    check("メニューは「フォルダ・検索・まとめ・設定」（今の「最近」は出さない）", items == ["フォルダ", "検索", "まとめ", "設定"], str(items))
    check("メニューの各項目にアイコン", pg.locator(".nav-menu button svg").count() == 4)
    check("上部バーの検索・まとめ・設定のボタンとタブはメニューにまとめた", pg.locator("header .tabs, header .search-toggle, header .report-btn, header [aria-label=設定]").count() == 0)
    pg.click(".nav-toggle"); time.sleep(0.2)
    check("もう一度押すとメニューが閉じる", not pg.locator(".nav-menu").is_visible())
    pg.click(".nav-toggle"); time.sleep(0.3); pg.go_back(); time.sleep(0.4)
    check("メニューはスマホの戻る操作で閉じる（画面はそのまま）", not pg.locator(".nav-menu").is_visible() and pg.inner_text(".tab-name") == "最近")
    pg.click(".nav-toggle"); time.sleep(0.3)
    box = pg.locator(".memo-card").first.bounding_box(); pg.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2); time.sleep(0.4)
    check("メニューの外を押すとメニューが閉じるだけ（下のメモは開かない）", not pg.locator(".nav-menu").is_visible() and pg.locator(".view-title").count() == 0)
    check("上部バーの画面名の左にアイコン", pg.locator(".tab-name svg").count() == 1)
    check("検索画面の「＋」は下端から少し上", pg.evaluate("innerHeight - document.querySelector('.fab').getBoundingClientRect().bottom") >= 50)
    check("上部バーに今の画面の名前", pg.inner_text(".tab-name") == "最近")
    check("押したときの四角い色は出さない（丸いボタン等は形に合わせた表示）", pg.evaluate("getComputedStyle(document.querySelector('.fab')).webkitTapHighlightColor") == "rgba(0, 0, 0, 0)")
    check("タグは鮮やかな水色", pg.evaluate("getComputedStyle(document.querySelector('.tag-mini')||document.body).color") == "rgb(18, 180, 245)" if pg.locator(".tag-mini").count() else True)
    check("検索画面の右下のボタンは「＋」だけの丸いボタン", pg.evaluate("(()=>{const f=document.querySelector('.fab');return f.classList.contains('round')&&f.textContent.trim()===''&&f.getAttribute('aria-label')==='新規メモ'})()"))
    check("上部バーに水色の線を付けない", pg.evaluate("getComputedStyle(document.querySelector('.topbar'),'::after').content") in ("none", "normal"))
    check("検索窓に「検索」ボタンはない（Enter で検索）", pg.locator(".search-go").count() == 0)
    check("最近タブに件数を出さない", pg.locator(".result-meta").count() == 0)
    check("メモのカードの左端にジャンルのアイコンを置いた色の帯がある", pg.evaluate("(()=>{const b=document.querySelector('.memo-card .genre-band .gb');const c=getComputedStyle(b);return c.backgroundColor!=='rgba(0, 0, 0, 0)'&&!!b.querySelector('svg')})()"))
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
    pg.go_back(); pg.wait_for_selector(".nav-toggle")

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
    check("フォルダからさらにスライドで情報まとめ", pg.inner_text(".tab-name") == "情報まとめ" and pg.locator(".rp-tools").count() == 1)
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
    pg.go_back(); pg.wait_for_selector(".nav-toggle")

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
    with pg.expect_file_chooser() as fc: pg.click(".modal >> text=画像を選ぶ")
    fc.value.set_files(ICON)
    # 画像を縮めて保存し終えるまで待つ（遅い端末でも決まった秒数で判定しない）
    try: pg.wait_for_function("document.documentElement.classList.contains('has-bg')", timeout=8000)
    except Exception: pass
    time.sleep(0.2)
    check("背景を端末の画像にできる", pg.evaluate("document.documentElement.classList.contains('has-bg')") and pg.locator(".bg-preview").is_visible())
    pg.click(".modal >> text=元に戻す"); time.sleep(0.4)
    check("背景を元に戻せる", not pg.evaluate("document.documentElement.classList.contains('has-bg')"))
    check("背景の画像はカメラを起動しない指定（端末内の画像だけ）", pg.evaluate("[...document.querySelectorAll('.modal input[type=file]')].every(i=>!/image\\/\\*/.test(i.accept)&&!i.hasAttribute('capture'))"))
    check("バックアップの欄に「端末内の保存の保護」は出さない", "保存の保護" not in pg.inner_text(".modal"))
    pg.click(".modal [aria-label=上部バーを透過]"); time.sleep(0.3)
    check("上部バーを透過でき、境目に線が出る（アイコンには枠）", pg.evaluate("document.documentElement.classList.contains('clear-bar') && getComputedStyle(document.querySelector('.topbar.bar-search')).borderBottomWidth === '2px' && getComputedStyle(document.querySelector('.topbar .icon-btn.ico')).boxShadow !== 'none'"))
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
    pg.go_back(); pg.wait_for_selector(".nav-toggle"); time.sleep(0.3)
    check("まとめから戻ると選択モードは終わっている", pg.locator(".select-bar").count() == 0)

    # まとめて削除
    n_cards = pg.locator(".memo-card").count()
    long_press(pg, pg.locator(".memo-card").first)
    check("メモの長押しで選択が始まり、そのメモが選ばれる（離しても外れない）", pg.locator(".select-bar").count() == 1 and pg.locator(".memo-card.picked").count() == 1)
    pg.locator(".memo-card").nth(1).click()
    check("選択中は押すたびに選ぶ・外す", pg.locator(".memo-card.picked").count() == 2)
    pg.locator(".memo-card").nth(1).click()
    check("選択のチェックは太い線の印", pg.evaluate("(()=>{const s=document.querySelector('.memo-card.picked .pick-box svg');return !!s&&parseFloat(s.getAttribute('stroke-width'))>=3})()"))
    pg.click(".select-bar >> text=削除")
    check("削除の確認の「Yes」は警告色の赤", "danger-solid" in pg.get_attribute(".modal >> text=Yes", "class"))
    pg.click(".modal >> text=Yes"); time.sleep(0.4)
    check("まとめて削除", pg.locator(".select-bar").count() == 0)
    # 作成・更新の日時: 1時間未満は「○分前」、24時間未満は「○時間前」、それより前は日付
    tc = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
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
        c = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        c.route(FakeGas.URL, gas.handle)
        q = c.new_page(); q.on("pageerror", lambda e: errors.append(str(e))); q.goto(URL); q.wait_for_selector(".fab"); return q
    def sync_on(q, key="aikotoba-123", url=FakeGas.URL):
        settings(q)
        if q.locator(".sync-setup").get_attribute("open") is None: q.click(".sync-setup summary")
        q.fill("#sync-url", url); q.fill("#sync-key", key); q.click(".sync-btn"); q.wait_for_timeout(1500)
        st = q.inner_text(".sync-status"); q.click(".modal .modal-x"); return st
    pa = device()
    pa.click(".fab"); pa.fill("#title", "同期のメモ"); pa.click(".genre-pick >> text=体験"); pa.set_input_files("#file", ICON); pa.wait_for_selector(".att-tile")
    pa.click(".edit-actions .btn.primary"); pa.wait_for_timeout(5000)
    check("同期がオフの間はドライブへ送らない", gas.calls == [])
    # 複数アカウントでログイン中にコピーした「/macros/u/1/s/…」の形でも、自動で直してつながる
    st = sync_on(pa, url=FakeGas.URL.replace("/macros/s/", "/macros/u/1/s/"))
    check("「同期」を押すとドライブへ送る（URLの形も自動で直す）", st.startswith("オン") and gas.data and len(gas.data["memos"]) == 1 and len(gas.files) == 1, st)
    pb = device()
    check("合言葉が違うと分かる", "合言葉が違います" in sync_on(pb, "machigai"))
    settings(pb); pb.click(".sync-btn"); pb.wait_for_timeout(300); pb.click(".modal .modal-x")
    sync_on(pb); pb.wait_for_timeout(500)
    check("別の端末で同期するとメモと添付が戻る", pb.locator(".memo-card", has_text="同期のメモ").count() == 1 and "📎 1" in pb.inner_text(".memo-card"))
    pb.locator(".memo-card").first.click(); pb.click(".menu-btn"); pb.click(".menu >> text=削除"); pb.click(".modal >> text=Yes"); pb.wait_for_timeout(5500)
    # 接続先のプログラムが古い（保存前に公開した）ときは、Google のエラー画面を見分けて直し方を示す
    pc = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
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
    pb.click(".fab"); pb.fill("#title", "大きな添付"); pb.click(".genre-pick >> text=学び")
    pb.set_input_files("#file", files=[{"name": "big.bin", "mimeType": "application/octet-stream", "buffer": big}]); pb.wait_for_selector(".att-tile")
    gas.fail_next = 3   # 最初の送信は3回とも通信切れ（自動のやり直しも失敗）
    pb.click(".edit-actions .btn.primary"); pb.wait_for_timeout(9000)
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
    old = FakeGas(version=1); pd = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True); pd.route(FakeGas.URL, old.handle)
    qd = pd.new_page(); qd.goto(URL); qd.wait_for_selector(".fab")
    check("古い版の接続先は更新を案内", "最新の gas/Code.gs" in sync_on(qd)); pd.close()

    b.close()

real_errors = [e for e in errors if "fonts.g" not in e]
check("JavaScript エラーなし", not real_errors, "; ".join(real_errors))
print(f"\n{'すべて成功' if not failures else str(len(failures)) + '件失敗'}")
sys.exit(1 if failures else 0)
