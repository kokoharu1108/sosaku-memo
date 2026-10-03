"""テスト用: Google Apps Script（gas/Code.gs）と同じ受け答えをする偽の接続先（Playwright の route で使う）"""
import json

class FakeGas:
    URL = "https://script.google.com/macros/s/TEST/exec"

    def __init__(self, key="aikotoba-123"):
        self.key, self.data, self.files, self.calls = key, None, {}, []

    def handle(self, route):
        req = json.loads(route.request.post_data or "{}")
        self.calls.append(req.get("action"))
        if req.get("key") != self.key:
            out = {"ok": False, "error": "auth"}
        else:
            a = req.get("action")
            if a == "pull":
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
        route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps(out))
