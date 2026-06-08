"""TEMPORARY diagnostic — load the REAL production page in a CI browser and report
the actual image state of the first cards, to see why every card shows the
placeholder. Surfaces results via an intentional assertion. Deleted after."""

def test_diag(browser):
    page = browser.new_page()
    page.goto("https://run.mmendelson.com/pt/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector(".card", state="attached", timeout=30000)
    page.wait_for_timeout(6000)  # let images attempt to load
    res = page.evaluate(
        """() => {
        const out = {ua: navigator.userAgent.slice(0,40), cards: []};
        const cards = [...document.querySelectorAll('.card')].slice(0, 8);
        for (const card of cards) {
            const img = card.querySelector('.card-img');
            const ph = card.querySelector('.card-img-placeholder');
            out.cards.push({
                title: (card.querySelector('.card-title')||{}).textContent || '',
                src: img ? (img.getAttribute('src') || '') : null,
                currentSrc: img ? img.currentSrc : null,
                complete: img ? img.complete : null,
                naturalWidth: img ? img.naturalWidth : null,
                img_display: img ? getComputedStyle(img).display : null,
                ph_display: ph ? getComputedStyle(ph).display : null,
            });
        }
        return out;
    }"""
    )
    import json
    raise AssertionError("IMGDIAG=" + json.dumps(res, ensure_ascii=False))
