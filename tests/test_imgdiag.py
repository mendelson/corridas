"""TEMPORARY diagnostic (light) — load production, expand only the first 3
collapsed months, scroll so lazy images attempt to load, classify card images.
Deleted after."""
import json

def test_diag(browser):
    page = browser.new_page(viewport={"width": 412, "height": 915})
    page.goto("https://run.mmendelson.com/pt/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".card", state="attached", timeout=30000)
    page.wait_for_timeout(3000)
    page.evaluate("""() => {
        const collapsed = [...document.querySelectorAll('.month-separator[aria-expanded="false"]')];
        collapsed.slice(0, 3).forEach(b => b.click());
    }""")
    page.wait_for_timeout(1000)
    for _ in range(15):
        page.evaluate("window.scrollBy(0, 1800)")
        page.wait_for_timeout(400)
    page.wait_for_timeout(6000)
    res = page.evaluate("""() => {
        const out = {visible_cards:0, loaded:0, placeholder:0, broken_visible:0,
                     pending:0, no_src:0, broken_samples:[]};
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
                if (out.broken_samples.length < 10)
                    out.broken_samples.push(src.slice(0,90));
            } else if (img.naturalWidth > 0 && imgShown) {
                out.loaded++;
            } else if (!imgShown && phShown) {
                out.placeholder++;
            } else {
                out.pending++;
            }
        }
        return out;
    }""")
    raise AssertionError("IMGDIAG2=" + json.dumps(res, ensure_ascii=False))
