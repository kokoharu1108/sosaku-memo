/**
 * ヒフミヨ — Googleドライブ同期用のプログラム（Google Apps Script）
 *
 * 使い方は docs/Googleドライブ同期の設定.md を見てください。
 * このプログラムは、あなた自身の Googleドライブの「ヒフミヨ_同期」フォルダにだけ読み書きします。
 *
 * ▼ 下の KEY の "ここに合言葉" を、自分で決めた合言葉（英数字12文字以上がおすすめ）に書き換えてください。
 *   アプリの設定にも同じ合言葉を入れます。合言葉を知らない人はデータを読み書きできません。
 */
const KEY = "ここに合言葉";

const FOLDER_NAME = "ヒフミヨ_同期";   // ドライブに作るフォルダの名前
const KEEP_DAYS = 30;                  // 毎日の控え（data-日付.json）を残す日数

/* ブラウザでURLを開いたときの表示（接続の確認用）。アプリとのやり取りは下の doPost で行う */
function doGet() {
  const ok = KEY && KEY !== "ここに合言葉";
  const msg = ok
    ? "ヒフミヨ同期：準備できています。このページは閉じて、このURLをアプリの設定「接続先のURL」に貼り付けてください。"
    : "ヒフミヨ同期：まだ合言葉が設定されていません。プログラムの KEY を書き換えて保存し、新しいバージョンで公開し直してください。";
  return HtmlService.createHtmlOutput('<meta name="viewport" content="width=device-width,initial-scale=1"><p style="font:16px/1.7 sans-serif;padding:16px">' + msg + "</p>");
}

function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents);
    if (!KEY || KEY === "ここに合言葉") return out_({ ok: false, error: "nokey" });
    if (req.key !== KEY) return out_({ ok: false, error: "auth" });
    const root = folder_(DriveApp.getRootFolder(), FOLDER_NAME);
    const files = folder_(root, "files");
    switch (req.action) {
      case "ping":
        return out_({ ok: true });
      case "pull": {   // メモ・リストのデータを返す
        const f = first_(root.getFilesByName("data.json"));
        return out_({ ok: true, data: f ? JSON.parse(f.getBlob().getDataAsString("UTF-8")) : null });
      }
      case "push": {   // メモ・リストのデータを保存（1日1回、日付つきの控えも残す）
        const text = JSON.stringify(req.data);
        const f = first_(root.getFilesByName("data.json"));
        if (f) f.setContent(text); else root.createFile("data.json", text, "application/json");
        const day = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
        const daily = first_(root.getFilesByName("data-" + day + ".json"));
        if (daily) daily.setContent(text); else root.createFile("data-" + day + ".json", text, "application/json");
        cleanup_(root);
        return out_({ ok: true });
      }
      case "listFiles": {   // ドライブにある添付ファイルの番号の一覧
        const ids = [];
        const it = files.getFiles();
        while (it.hasNext()) ids.push(it.next().getName());
        return out_({ ok: true, ids: ids });
      }
      case "putFile": {   // 添付ファイルを1つ保存（中身は base64）
        if (!first_(files.getFilesByName(req.id))) {
          files.createFile(Utilities.newBlob(Utilities.base64Decode(req.data), req.type || "application/octet-stream", req.id));
        }
        return out_({ ok: true });
      }
      case "getFile": {   // 添付ファイルを1つ返す
        const f = first_(files.getFilesByName(req.id));
        if (!f) return out_({ ok: false, error: "nofile" });
        const blob = f.getBlob();
        return out_({ ok: true, type: blob.getContentType(), data: Utilities.base64Encode(blob.getBytes()) });
      }
      default:
        return out_({ ok: false, error: "action" });
    }
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}

function folder_(parent, name) {
  const it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}
function first_(it) { return it.hasNext() ? it.next() : null; }
function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
/* 古い日付の控えをゴミ箱へ移す */
function cleanup_(root) {
  const limit = Date.now() - KEEP_DAYS * 24 * 60 * 60 * 1000;
  const it = root.getFiles();
  while (it.hasNext()) {
    const f = it.next();
    if (/^data-\d{4}-\d{2}-\d{2}\.json$/.test(f.getName()) && f.getLastUpdated().getTime() < limit) f.setTrashed(true);
  }
}
