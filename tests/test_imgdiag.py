"""TEMPORARY validation — load the LOCAL site with the PATCHED app.js, allowing
real image loads, and report whether cards that have an image URL still show the
placeholder. With the fix, cards with a src must NOT show the branded placeholder
(ph_display must be 'none'). Deleted after."""

def test_diag(browser, live_server):
    ctx = browser.new_context()  # no abort route → real images may load
    page = ctx.new_page()
    page.goto(live_server + "/pt/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".card", state="attached", timeout=30000)
    page.wait_for_timeout(8000)
    res = page.evaluate(
        """() => {
        const cards = [...document.querySelectorAll('.card')];
        let with_src=0, with_src_placeholder=0;
        const sample=[];
        for (const card of cards) {
            const img = card.querySelector('.card-img');
            const ph = card.querySelector('.card-img-placeholder');
            if (!img) continue;
            const src = img.getAttribute('src') || '';
            const phd = ph ? getComputedStyle(ph).display : null;
            if (src) {
                with_src++;
                if (phd === 'flex') with_src_placeholder++;
                if (sample.length < 6) sample.push({
                    src: src.slice(0,50), complete: img.complete,
                    nw: img.naturalWidth, img_d: getComputedStyle(img).display, ph_d: phd,
                });
            }
        }
        return {total: cards.length, with_src, with_src_placeholder, sample};
    }"""
    )
    ctx.close()
    import json
    raise AssertionError("IMGFIX=" + json.dumps(res, ensure_ascii=False))
