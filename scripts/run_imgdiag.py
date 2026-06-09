"""TEMPORARY validation — serve the LOCAL site (with the no-referrer fix),
load it in a real browser, and capture the content-type/size served by
correrbrasilia.com.br for card images. With the fix the host must serve the
real art (image/jpeg), not the hotlink substitute (image/png)."""
import json, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory="web", **kw)
    def log_message(self, *a): pass

srv = ThreadingHTTPServer(("127.0.0.1", 8765), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

GEO = json.dumps({"country_code":"BR","region_code":"DF","city":"Brasília",
                  "latitude":-15.79,"longitude":-47.88})
hits = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width":412,"height":915}, locale="pt-BR")
    def route(r, req):
        if any(h in req.url for h in ("ipwho.is","freeipapi.com","api.ip.sb")):
            r.fulfill(status=200, content_type="application/json", body=GEO)
        else:
            r.continue_()
    ctx.route("**/*", route)
    page = ctx.new_page()
    def on_resp(resp):
        if "correrbrasilia.com.br/wp-content/uploads" in resp.url:
            try:
                req_ref = resp.request.header_value("referer")
            except Exception:
                req_ref = "?"
            try:
                size = len(resp.body())
            except Exception:
                size = -1
            hits.append({"url": resp.url.rsplit("/",1)[-1][:50],
                         "status": resp.status,
                         "ctype": resp.headers.get("content-type",""),
                         "size": size, "referer_sent": req_ref})
    page.on("response", on_resp)
    page.goto("http://127.0.0.1:8765/pt/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".card", state="attached", timeout=30000)
    page.wait_for_timeout(4000)
    page.evaluate("""() => {
        [...document.querySelectorAll('.month-separator[aria-expanded="false"]')]
            .slice(0, 4).forEach(b => b.click());
    }""")
    for _ in range(18):
        page.evaluate("window.scrollBy(0, 1500)")
        page.wait_for_timeout(400)
    page.wait_for_timeout(6000)
    summary = page.evaluate("""() => {
        let cb_loaded=0, cb_total=0;
        for (const img of document.querySelectorAll('.card-img')) {
            const src = img.getAttribute('src')||'';
            if (!src.includes('correrbrasilia.com.br')) continue;
            cb_total++;
            if (img.naturalWidth > 0) cb_loaded++;
        }
        return {cb_total, cb_loaded};
    }""")
    b.close()
srv.shutdown()

res = {"summary": summary, "responses": hits[:20],
       "jpeg": sum(1 for h in hits if "jpeg" in h["ctype"]),
       "png_substitute": sum(1 for h in hits if "png" in h["ctype"])}
with open("diag-result.json","w") as f: json.dump(res,f,ensure_ascii=False,indent=2)
print(json.dumps(res,ensure_ascii=False))
