"""テスト用: Google Apps Script（gas/Code.gs）と同じ受け答えをする偽の接続先（Playwright の route で使う）"""
import json

class FakeGas:
    URL = "https://script.google.com/macros/s/TEST/exec"

    def __init__(self, key="aikotoba-123", version=2):
        self.key, self.data, self.files, self.calls, self.version = key, None, {}, [], version
        self.parts, self.fail_next = {}, 0   # fail_next: 次の putChunk を何回「通信切れ」にするか
        self.echo404 = {}   # {操作名: 回数}: 処理はしたが、返事が 404 になる回数（本物では googleusercontent.com で起きる）

    def echo(self, route):
        route.fulfill(status=404, content_type="text/html", headers={"Access-Control-Allow-Origin": "*"}, body="<html><head><title>ページが見つかりません</title></head></html>")

    def handle(self, route):
        req = json.loads(route.request.post_data or "{}")
        self.calls.append(req.get("action"))
        if req.get("action") == "putChunk" and self.fail_next > 0:
            self.fail_next -= 1; route.abort("connectionreset"); return
        if req.get("key") != self.key:
            out = {"ok": False, "error": "auth"}
        else:
            a = req.get("action")
            if a == "ping":
                out = {"ok": True, "version": self.version}
            elif a == "putChunk":
                if req["id"] in self.files:
                    out = {"ok": True, "done": True}
                else:
                    self.parts.setdefault(req["id"], {})[req["index"]] = req.get("data", "")
                    if req["index"] == req["total"] - 1:
                        ps = self.parts.pop(req["id"])
                        self.files[req["id"]] = (req.get("type"), "".join(ps[i] for i in range(req["total"])))
                    out = {"ok": True}
            elif a == "getChunk":
                t, d = self.files.get(req["id"], (None, None))
                if d is None:
                    out = {"ok": False, "error": "nofile"}
                else:
                    o, n = req.get("offset", 0), req.get("length", len(d))
                    out = {"ok": True, "type": t, "total": len(d), "data": d[o:o + n]}
            elif a == "pull":
                out = {"ok": True, "data": self.data}
            elif a == "push":
                self.data = req.get("data"); out = {"ok": True}
            elif a == "listFiles":
                out = {"ok": True, "ids": list(self.files)}
            elif a == "putFile":
                self.files.setdefault(req["id"], (req.get("type"), req["data"])); out = {"ok": True}
            elif a == "getFile":
                t, d = self.files.get(req["id"], (None, None))
                out = {"ok": True, "type": t, "data": d} if d is not None else {"ok": False, "error": "nofile"}
            else:
                out = {"ok": True}
        if self.echo404.get(req.get("action"), 0) > 0:
            self.echo404[req["action"]] -= 1
            self.echo(route); return   # 本物は googleusercontent.com へ回されてから 404（Playwright では回し先を横取りできないため、その場で 404 を返す）
        route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps(out))
