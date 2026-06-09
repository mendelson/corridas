"""TEMPORARY diagnostic — load production, scroll through the list so lazy
images attempt to load, then classify every card image: loaded OK, branded
placeholder shown, or BROKEN VISIBLE (img displayed, load finished, zero size).
Surfaces results via an intentional assertion. Deleted after."""
import json

def test_diag(browser):
    page = browser.new_page(viewport={"width": 412, "height": 915})
    page.goto("https://run.mmendelson.com/pt/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".card", state="attached", timeout=30000)
    page.wait_for_timeout(3000)
    # Expand every month so all cards render, then scroll through the page in
    # steps so loading="lazy" images enter the viewport and actually fetch.
    page.evaluate("""() => {
        document.querySelectorAll('.month-separator[aria-expanded="false"]')
            .forEach(b => b.click());
    }""")
    page.wait_for_timeout(1000)
    for _ in range(40):
        page.evaluate("window.scrollBy(0, 2200)")
        page.wait_for_timeout(350)
    page.wait_for_timeout(5000)
    res = page.evaluate("""() => {
        const out = {loaded:0, placeholder:0, broken_visible:0, pending:0,
                     no_src:0, broken_samples:[]};
        for (const card of document.querySelectorAll('.card')) {
            const img = card.querySelector('.card-img');
            const ph  = card.querySelector('.card-img-placeholder');
            if (!img) continue;
            const src = img.getAttribute('src') || '';
            const imgShown = getComputedStyle(img).display !== 'none';
            const phShown  = ph && getComputedStyle(ph).display !== 'none';
            if (!src) { out.no_src++; continue; }
            if (imgShown && img.complete && img.naturalWidth === 0) {
                out.broken_visible++;
                if (out.broken_samples.length < 10)
                    out.broken_samples.push({src: src.slice(0,90), ph: phShown});
            } else if (imgShown && img.naturalWidth > 0) {
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
