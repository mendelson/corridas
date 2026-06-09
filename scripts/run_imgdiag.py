"""TEMPORARY standalone diag — survey card images on production with geo
mocked to Brasília/DF (mirrors the user's filtered view), save screenshots."""
import json
from playwright.sync_api import sync_playwright

GEO_FAKE = json.dumps({"country_code": "BR", "region_code": "DF",
                       "city": "Brasília", "latitude": -15.79, "longitude": -47.88})
_GEO_HOSTS = ("ipwho.is", "freeipapi.com", "api.ip.sb")

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 412, "height": 915}, locale="pt-BR")

    def handle(route, request):
        if any(h in request.url for h in _GEO_HOSTS):
            route.fulfill(status=200, content_type="application/json", body=GEO_FAKE)
        else:
            route.continue_()
    ctx.route("**/*", handle)

    page = ctx.new_page()
    page.goto("https://run.mmendelson.com/pt/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".card", state="attached", timeout=30000)
    page.wait_for_timeout(4000)
    page.evaluate("""() => {
        [...document.querySelectorAll('.month-separator[aria-expanded="false"]')]
            .slice(0, 4).forEach(b => b.click());
    }""")
    page.wait_for_timeout(1000)
    shots = 0
    for i in range(18):
        page.evaluate("window.scrollBy(0, 1500)")
        page.wait_for_timeout(450)
        if i in (2, 6, 10) and shots < 3:
            page.screenshot(path=f"diag-shot-{shots}.png")
            shots += 1
    page.wait_for_timeout(6000)
    res = page.evaluate("""() => {
        const out = {filter_label: (document.querySelector('#estado-filter-btn')||{}).textContent||'',
                     visible_cards:0, loaded:0, placeholder:0, broken_visible:0,
                     pending:0, no_src:0, broken_samples:[], pending_samples:[]};
        for (const card of document.querySelectorAll('.month-section--open .card')) {
            const img = card.querySelector('.card-img');
            const ph  = card.querySelector('.card-img-placeholder');
            if (!img) continue;
            out.visible_cards++;
            const src = img.getAttribute('src') || '';
            const imgShown = getComputedStyle(img).display !== 'none';
            const phShown  = ph && getComputedStyle(ph).display !== 'none';
            if (!src) { out.no_src++; continue; }
            if (imgShown && img.complete && img.naturalWidth === 0) {
                out.broken_visible++;
                if (out.broken_samples.length < 10) out.broken_samples.push(src.slice(0,90));
            } else if (img.naturalWidth > 0 && imgShown) {
                out.loaded++;
            } else if (!imgShown && phShown) {
                out.placeholder++;
            } else {
                out.pending++;
                if (out.pending_samples.length < 5) out.pending_samples.push(src.slice(0,90));
            }
        }
        return out;
    }""")
    page.screenshot(path="diag-shot-final.png")
    browser.close()

with open("diag-result.json", "w") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print(json.dumps(res, ensure_ascii=False))
