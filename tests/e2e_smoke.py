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

    # 検索パネル・ジャンル
    pg.click(".search-toggle"); pg.fill("#q", "火祭"); pg.keyboard.press("Enter"); time.sleep(0.2)
    check("キーワード検索", pg.locator(".memo-card").count() == 1)
    check("検索窓の下の絞り込みが隠れない", pg.evaluate("(()=>{const s=document.querySelector('#genre-search');const r=s.getBoundingClientRect();return document.elementFromPoint(r.left+5,r.top+5)===s})()"))
    pg.click(".filter-chip button"); pg.select_option("#genre-search", "学び"); time.sleep(0.1)
    check("ジャンル絞り込み", pg.locator(".memo-card").count() == 1)
    pg.select_option("#genre-search", ""); pg.click(".search-toggle")

    # ツリー（階層）は廃止: タブ・閲覧画面・編集画面に出ない
    new_memo(pg, "鞍馬の火祭")
    check("ツリーのタブがない", pg.locator(".tabs >> text=ツリー").count() == 0)
    check("カードは題名・日付・冒頭・ジャンルだけ（リスト名・時刻なし）", pg.locator(".memo-card .list-tag").count() == 0 and ":" not in pg.locator(".memo-card .card-date").first.inner_text())
    pg.locator(".memo-card", has_text="京都取材").click(); pg.wait_for_selector(".view-title")
    check("閲覧画面の上部バーに題名とジャンル（「メモを読む」はない）", pg.inner_text("header .view-title") == "京都取材" and pg.locator("header .genre").count() >= 1 and "メモを読む" not in pg.inner_text("header"))
    check("アプリ名はヒフミヨ", pg.title() == "ヒフミヨ")
    check("閲覧画面に階層の欄がない", pg.locator(".child-sec, .tree-path").count() == 0 and "階層" not in pg.inner_text(".view-doc"))

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
    pg.click(".select-btn"); pg.click(".crumb.home"); time.sleep(0.4)
    pg.click(".tabs >> text=メモ"); pg.locator(".memo-card").first.click(); pg.wait_for_selector(".view-title")
    pg.go_back(); time.sleep(0.3)
    check("選択モード後も戻る操作が効く", pg.locator(".search-toggle").count() == 1)

    pg.click(".tabs >> text=リスト")
    check("リスト一覧の更新日は「更新」の文字ではなくアイコン", pg.locator(".list-sub .upd-ico svg").count() >= 1 and "更新" not in pg.inner_text(".list-sub"))
    pg.click(".list-row .open"); time.sleep(0.3)
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
    check("題名の欄は「題名」だけ", pg.get_attribute("#title", "placeholder") == "題名")
    check("リストはプルダウンで選ぶ", pg.locator("select#elist").count() == 1)
    check("メモ画面の下部の見出しは「タグ」「リスト」だけ", "そのほかの設定" not in pg.inner_text("main") and "自由に付けられます" not in pg.inner_text("main") and "リストに入れる" not in pg.inner_text("main"))
    check("新規メモで本文が1画面目に見える", pg.evaluate("document.querySelector('.editor').getBoundingClientRect().top < 400"))
    check("タグ・リストは本文より下・階層の欄はない", pg.evaluate("(()=>{const e=document.querySelector('.editor').getBoundingClientRect().top;return document.querySelector('#taginput').getBoundingClientRect().top>e&&!document.querySelector('.parent-box')})()"))
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
    pg.set_input_files("#file", ICON); pg.wait_for_selector(".att-tile img"); time.sleep(0.3)
    check("添付の縮小画像がファイル名に重ならない", pg.evaluate("(()=>{const t=document.querySelector('.att-tile');return t.querySelector('img').getBoundingClientRect().bottom<=t.querySelector('.name').getBoundingClientRect().top+1})()"))
    pg.click("#title"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".search-toggle"); time.sleep(0.2)
    pg.locator(".memo-card", has_text="書式").click(); pg.wait_for_selector(".view-title")
    check("閲覧画面の本文は16px・行間は詰めめ", pg.evaluate("(()=>{const c=getComputedStyle(document.querySelector('.view-body'));return c.fontSize==='16px'&&parseFloat(c.lineHeight)/16<=1.65})()"))
    pg.click("text=添付ファイル（1件）"); pg.click(".att-row"); pg.wait_for_selector(".lightbox img")
    pg.click(".lightbox img"); time.sleep(0.2)
    check("画像を押しても原寸表示にならず、拡大表示が閉じる", pg.locator(".lightbox").count() == 0 and "原寸" not in pg.content())
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
    pg.click("#title"); pg.click(".edit-actions .btn.primary"); pg.wait_for_selector(".search-toggle"); time.sleep(0.2)

    # 情報まとめ: 検索結果からまとめ → 画面表示・ファイル保存
    pg.click(".search-toggle"); pg.fill("#q", "火祭"); pg.keyboard.press("Enter"); time.sleep(0.2)
    pg.click(".report-btn"); pg.wait_for_selector(".rp-doc"); time.sleep(0.3)
    check("まとめは新しい資料として抜き出した文章だけ（元の題名は出ない）", "火祭" in pg.inner_text(".rp-doc") and "京都取材" not in pg.inner_text(".rp-doc .rp-sec"))
    with pg.expect_download() as dl: pg.click(".rp-tools [aria-label=ファイルに保存]")
    import shutil; out = Path(__file__).resolve().parent / "_report_test.html"; shutil.copy(dl.value.path(), out)
    html = out.read_text(encoding="utf-8"); out.unlink()
    check("まとめを1つのファイルに保存できる", dl.value.suggested_filename.endswith(".html") and "rp-doc" in html and "blob:" not in html)
    import re as _re
    check("ファイル名は「まとめの題名_日付」", bool(_re.fullmatch(r"火祭のまとめ_\d{8}\.html", dl.value.suggested_filename)), dl.value.suggested_filename)
    pg.click(".rp-tools >> text=メモにする"); pg.wait_for_selector(".editor")
    check("まとめを新しいメモの下書きにできる", pg.input_value("#title") == "火祭のまとめ" and "火祭" in pg.inner_text(".editor"))
    pg.click(".topbar .back"); time.sleep(0.3)
    if pg.locator(".modal").count(): pg.click(".modal >> text=破棄して戻る"); time.sleep(0.3)
    pg.go_back(); pg.wait_for_selector(".search-toggle"); pg.click(".filter-chip button"); pg.click(".search-toggle")
    pg.click(".tabs >> text=リスト"); pg.click(".list-row .open"); time.sleep(0.2)
    pg.click("text=保存済みのメモを入れる"); pg.locator(".modal .ref-item").first.click(); pg.click(".modal >> text=決定"); time.sleep(0.3)
    pg.click(".report-btn"); pg.wait_for_selector(".rp-doc")
    check("リストからもまとめを作れる", pg.inner_text(".rp-title") == "京都のまとめ")
    pg.go_back(); time.sleep(0.2); pg.go_back(); pg.wait_for_selector(".search-toggle"); pg.click(".tabs >> text=メモ")

    # 検索パネルはスマホの戻る操作で閉じる・検索履歴は出さない（撤廃）
    pg.click(".search-toggle")
    for q in ["一", "二", "三", "四"]: pg.fill("#q", q); pg.keyboard.press("Enter"); time.sleep(0.15)
    check("検索履歴は出さない", pg.locator(".hist-row, .hist-chips").count() == 0 and "最近" not in pg.inner_text(".search-panel"))
    pg.go_back(); time.sleep(0.3)
    check("戻る操作で検索パネルが閉じる（画面はそのまま）", not pg.locator(".search-panel").is_visible() and pg.locator(".search-toggle").count() == 1)
    pg.click(".filter-chip button"); time.sleep(0.2)
    # 検索ボタンを2回押して閉じたら、押したままの見た目が残らない（スマホ）
    pg.tap(".search-toggle"); time.sleep(0.3); pg.tap(".search-toggle"); time.sleep(0.3)
    check("検索パネルを閉じると検索ボタンは押していない見た目に戻る", pg.evaluate("getComputedStyle(document.querySelector('.search-toggle')).backgroundColor") == "rgba(0, 0, 0, 0)")
    check("メモ／リストのタブは選んでいる方が塗りつぶし", pg.evaluate("(()=>{const [a,b]=document.querySelectorAll('.tabs button');const c=e=>getComputedStyle(e).backgroundColor;return c(a)!==c(b)&&c(a)!=='rgba(0, 0, 0, 0)'})()"))
    check("タグは鮮やかな青", pg.evaluate("getComputedStyle(document.querySelector('.tag-mini')||document.body).color") == "rgb(29, 155, 240)" if pg.locator(".tag-mini").count() else True)
    check("メモのカードに1件ずつの色の帯がある", pg.evaluate("parseFloat(getComputedStyle(document.querySelector('.memo-card')).borderLeftWidth) >= 5"))

    # まとめ: キーワードなしでも作れて、作成日時の期間（今日など）で絞れる
    pg.click(".report-btn"); pg.wait_for_selector(".rp-tools")
    check("キーワードなしで全メモのまとめ", pg.inner_text(".rp-title") == "すべてのメモのまとめ")
    check("リスト・期間は「未選択」から選ぶ", pg.locator("#rp-period option").first.inner_text() == "未選択")
    check("キーワードなしでは「関連部分だけ／全文」を出さない", pg.locator(".rp-seg").count() == 0)
    pg.select_option("#rp-period", "today"); time.sleep(0.3)
    import datetime as _dt
    check("期間「今日」でまとめられる", pg.inner_text(".rp-title") == _dt.date.today().strftime("%Y/%m/%d") + "のまとめ")
    pg.select_option("#rp-period", "lastmonth"); time.sleep(0.3)
    check("期間に該当なしなら案内が出る", "まとめるメモがありません" in pg.inner_text(".rp-holder"))
    pg.go_back(); pg.wait_for_selector(".search-toggle")

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
window.__midX=getComputedStyle(document.querySelector('.swipe-area > div:last-child')).transform;
fire('touchend',x1,false);}"""
    pg.evaluate(SWIPE, [300, 120]); time.sleep(0.6)
    check("スライド中は指に合わせて一覧が動く", pg.evaluate("window.__midX") not in ("none", ""))
    check("左へスライドでリストタブ", pg.locator(".tabs [aria-selected=true]").inner_text() == "リスト")
    pg.evaluate(SWIPE, [8, 250]); time.sleep(0.6)
    check("画面の端からの操作ではタブが変わらない", pg.locator(".tabs [aria-selected=true]").inner_text() == "リスト")
    pg.evaluate(SWIPE, [120, 300]); time.sleep(0.6)
    check("右へスライドでメモタブ", pg.locator(".tabs [aria-selected=true]").inner_text() == "メモ")

    # まとめ: リストを選べる
    pg.click(".report-btn"); pg.wait_for_selector("#rp-list")
    pg.select_option("#rp-list", label="京都"); time.sleep(0.3)
    check("まとめでリストを選べる", pg.inner_text(".rp-title").startswith("京都のまとめ"))
    pg.go_back(); pg.wait_for_selector(".search-toggle")

    # 検索画面: 「null」が出ない・「選択」は上部の固定バー
    check("検索画面に「null」が出ない", "null" not in pg.inner_text("body"))
    check("「選択」は上部の固定バーのアイコン", pg.locator("header .select-btn").count() == 1)

    # バックアップの書き出し → 「前回の書き出し」がその場で更新される
    pg.goto(URL); pg.wait_for_selector(".fab"); pg.click("button[aria-label=設定]")
    with pg.expect_download() as dl: pg.click(".modal >> text=バックアップを書き出す")
    check("バックアップを書き出せる", dl.value.suggested_filename.startswith("hifumiyo-backup-"))
    time.sleep(0.3)
    check("前回の書き出し日時がすぐ更新される", "まだありません" not in pg.inner_text(".modal"))
    pg.click(".modal >> text=閉じる")

    # オフライン起動
    pg.goto(URL); pg.wait_for_selector(".fab"); time.sleep(1)
    ctx.set_offline(True); pg.reload(); pg.wait_for_selector(".memo-card", timeout=8000)
    check("オフラインで起動・一覧表示", pg.locator(".memo-card").count() >= 4)
    ctx.set_offline(False)

    # まとめて削除
    pg.click(".select-btn"); pg.locator(".memo-card").first.click()
    check("選択のチェックは太い線の印", pg.evaluate("(()=>{const s=document.querySelector('.memo-card.picked .pick-box svg');return !!s&&parseFloat(s.getAttribute('stroke-width'))>=3})()"))
    pg.click(".select-bar >> text=削除"); pg.click(".modal >> text=Yes"); time.sleep(0.4)
    check("まとめて削除", pg.locator(".select-bar").count() == 0)
    # Googleドライブ同期（偽の接続先で確認）: オンにしたときだけ送る・別の端末で同期すると戻る・オフの間は送らない
    gas = FakeGas()
    def device():
        c = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        c.route(FakeGas.URL, gas.handle)
        q = c.new_page(); q.on("pageerror", lambda e: errors.append(str(e))); q.goto(URL); q.wait_for_selector(".fab"); return q
    def sync_on(q, key="aikotoba-123", url=FakeGas.URL):
        q.click("[aria-label=設定]")
        if q.locator(".sync-setup").get_attribute("open") is None: q.click(".sync-setup summary")
        q.fill("#sync-url", url); q.fill("#sync-key", key); q.click(".sync-btn"); q.wait_for_timeout(1500)
        st = q.inner_text(".sync-status"); q.click(".modal >> text=閉じる"); return st
    pa = device()
    pa.click(".fab"); pa.fill("#title", "同期のメモ"); pa.click(".genre-pick >> text=体験"); pa.set_input_files("#file", ICON); pa.wait_for_selector(".att-tile")
    pa.click(".edit-actions .btn.primary"); pa.wait_for_timeout(5000)
    check("同期がオフの間はドライブへ送らない", gas.calls == [])
    # 複数アカウントでログイン中にコピーした「/macros/u/1/s/…」の形でも、自動で直してつながる
    st = sync_on(pa, url=FakeGas.URL.replace("/macros/s/", "/macros/u/1/s/"))
    check("「同期」を押すとドライブへ送る（URLの形も自動で直す）", st.startswith("オン") and gas.data and len(gas.data["memos"]) == 1 and len(gas.files) == 1, st)
    pb = device()
    check("合言葉が違うと分かる", "合言葉が違います" in sync_on(pb, "machigai"))
    pb.click("[aria-label=設定]"); pb.click(".sync-btn"); pb.wait_for_timeout(300); pb.click(".modal >> text=閉じる")
    sync_on(pb); pb.wait_for_timeout(500)
    check("別の端末で同期するとメモと添付が戻る", pb.locator(".memo-card", has_text="同期のメモ").count() == 1 and "📎 1" in pb.inner_text(".memo-card"))
    pb.locator(".memo-card").first.click(); pb.click(".menu-btn"); pb.click(".menu >> text=削除"); pb.click(".modal >> text=Yes"); pb.wait_for_timeout(5500)
    # 接続先のプログラムが古い（保存前に公開した）ときは、Google のエラー画面を見分けて直し方を示す
    pc = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pc.route(FakeGas.URL, lambda r: r.fulfill(status=200, content_type="text/html", body="<html><body>スクリプト関数が見つかりません: doPost</body></html>"))
    qc = pc.new_page(); qc.goto(URL); qc.wait_for_selector(".fab")
    check("古い接続先のときは直し方を表示", "プログラムが古いまま" in sync_on(qc))
    pc.unroute(FakeGas.URL); pc.route(FakeGas.URL, lambda r: r.fulfill(status=404, content_type="text/html", body="<html><head><title>ページが見つかりません</title></head></html>"))
    qc.click("[aria-label=設定]"); qc.click(".sync-btn"); qc.wait_for_timeout(300); qc.click(".modal >> text=閉じる")
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
    pb.click("[aria-label=設定]"); st = pb.inner_text(".sync-status")
    check("通信が切れてもメモは先にドライブへ・失敗した添付は件数で知らせる", any(m["title"] == "大きな添付" for m in gas.data["memos"]) and "添付ファイル1件" in st, st)
    pb.click(".sync-btn"); pb.wait_for_timeout(300); pb.click(".sync-btn"); pb.wait_for_timeout(4000)   # オフ→オンで今すぐ同期
    pb.click(".modal >> text=閉じる")
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
    pb.click("[aria-label=設定]"); pb.click(".sync-btn"); pb.wait_for_timeout(300); pb.click(".modal >> text=閉じる")   # pb はオフに
    n = len(gas.calls); pb.wait_for_timeout(21000); pb.evaluate(RESUME); pb.wait_for_timeout(2000)
    check("同期オフなら画面に戻しても通信しない", len(gas.calls) == n)

    # Google の返事の受け取り口（googleusercontent.com）の一時的な 404 は、自動でやり直して同期を続ける
    def sync_now(q):
        q.click("[aria-label=設定]"); q.click(".sync-btn"); q.wait_for_timeout(300); q.click(".sync-btn"); q.wait_for_timeout(6000)
        st = q.inner_text(".sync-status"); q.click(".modal >> text=閉じる"); return st
    gas.echo404 = {"listFiles": 2}
    st = sync_now(pa)
    check("返事の受け取り口の一時的な404は、その場でやり直して成功", st.startswith("オン") and gas.echo404["listFiles"] == 0, st)
    # 1分待ちを8秒に縮めて確かめる
    pa.add_init_script("(() => { const st = window.setTimeout; window.setTimeout = (f, d, ...a) => st(f, d === 60000 ? 8000 : d, ...a); })()")
    pa.reload(); pa.wait_for_selector(".fab"); pa.wait_for_timeout(3000)
    gas.echo404 = {"listFiles": 3}
    st = sync_now(pa)
    check("やり直しても404なら一時的な不調と知らせる", "一時的な不調" in st and "添付の確認" in st, st)
    pa.wait_for_timeout(9000); pa.click("[aria-label=設定]"); st = pa.inner_text(".sync-status"); pa.click(".modal >> text=閉じる")
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
