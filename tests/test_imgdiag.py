"""TEMPORARY diagnostic — reproduce buildCard's image sync-check in a real browser
against a real, reachable image, to see whether `img.complete` misfires. Surfaces
results via an intentional assertion so they appear in the CI log. Deleted after."""
REAL = "https://d368g9lw5ileu7.cloudfront.net/races/race128258-logo-0.bL-e_9.png"

def test_diag(browser):
    page = browser.new_page()
    # Tall spacer so an in-DOM lazy image sits below the viewport (deferred).
    page.set_content("<div style='height:3000px'></div><div id='host'></div>")
    res = page.evaluate(
        """async (REAL) => {
        function probe(makeImg) {
            const img = makeImg();
            img.src = REAL;
            return {complete_sync: img.complete, nw_sync: img.naturalWidth, img};
        }
        const out = {};
        // Scenario A: detached createElement + loading=lazy (the buildCard path)
        {
            const r = probe(() => { const i=document.createElement('img'); i.loading='lazy'; return i; });
            out.A_detached_lazy = {complete_sync: r.complete_sync, nw_sync: r.nw_sync};
            document.getElementById('host').appendChild(r.img);
            await new Promise(res=>{ r.img.onload=res; r.img.onerror=res; setTimeout(res,5000); });
            out.A_detached_lazy.complete_after = r.img.complete;
            out.A_detached_lazy.nw_after = r.img.naturalWidth;
        }
        // Scenario B: detached createElement WITHOUT lazy
        {
            const r = probe(() => document.createElement('img'));
            out.B_detached_eager = {complete_sync: r.complete_sync, nw_sync: r.nw_sync};
        }
        return out;
    }""",
        REAL,
    )
    raise AssertionError("IMGDIAG=" + str(res))
