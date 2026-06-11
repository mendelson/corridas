"""Tests for the slim web/corridas.json projection (scripts/generate_web_data.py).

The web copy must stay a faithful projection of data/corridas.json: same
events, only frontend-consumed fields, and every event keeps a working link
(the frontend falls back to link_evento when links_inscricao is omitted).
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def _load(p):
    d = json.loads((ROOT / p).read_text(encoding="utf-8"))
    return d["corridas"] if isinstance(d, dict) else d

def _gen():
    spec = importlib.util.spec_from_file_location(
        "generate_web_data", ROOT / "scripts" / "generate_web_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

GEN = _gen()
ALLOWED = set(GEN.KEEP)


def test_same_events_same_order():
    full, slim = _load("data/corridas.json"), _load("web/corridas.json")
    assert len(full) == len(slim)
    assert [c["titulo"] for c in full] == [c["titulo"] for c in slim]
    assert [c["data_evento"] for c in full] == [c["data_evento"] for c in slim]


def test_only_frontend_fields_present():
    slim = _load("web/corridas.json")
    extra = {k for c in slim for k in c} - ALLOWED
    assert not extra, f"unexpected fields in web copy: {extra}"
    dropped = {"id", "miss_count", "updated_at", "periodo_inscricao",
               "inscricoes_abertas"}
    assert not (ALLOWED & dropped), "projection must not whitelist state fields"


def test_every_event_keeps_a_link_and_fonte_tipo():
    slim = _load("web/corridas.json")
    for c in slim:
        fontes = c.get("fontes") or []
        assert fontes, f"{c['titulo']}: no fontes"
        assert any(f.get("link_evento") or (f.get("links_inscricao") or [None])[0]
                   for f in fontes), f"{c['titulo']}: no link"
        assert all(f.get("tipo") in ("inscricao", "organizador", "calendario")
                   for f in fontes), f"{c['titulo']}: invalid fonte tipo"


def test_projection_meaningfully_smaller():
    full = (ROOT / "data" / "corridas.json").stat().st_size
    slim = (ROOT / "web" / "corridas.json").stat().st_size
    assert slim < full * 0.7, f"slim={slim} full={full}: projection not slimming"


def test_committed_web_copy_matches_generator():
    committed = (ROOT / "web" / "corridas.json").read_text(encoding="utf-8")
    full = json.loads((ROOT / "data" / "corridas.json").read_text(encoding="utf-8"))
    corridas = full["corridas"] if isinstance(full, dict) else full
    regenerated = {
        "gerado_em": full.get("gerado_em") if isinstance(full, dict) else None,
        "total": len(corridas),
        "corridas": [GEN._slim_event(ev) for ev in corridas],
    }
    assert json.loads(committed) == regenerated, (
        "web/corridas.json is stale — re-run scripts/generate_web_data.py")


# ---------------------------------------------------------------------------
# Boot shard (web/corridas-boot.json) — first-paint payload
# ---------------------------------------------------------------------------

def _boot():
    return json.loads((ROOT / "web" / "corridas-boot.json").read_text(encoding="utf-8"))


def test_boot_shard_window_and_flag():
    boot = _boot()
    assert boot.get("parcial") is True, "boot shard must carry parcial:true"
    lo, hi = GEN.boot_window(boot.get("gerado_em"))
    assert boot["corridas"], "boot shard is empty"
    for c in boot["corridas"]:
        assert lo <= c["data_evento"] <= hi, (
            f"{c['titulo']}: {c['data_evento']} outside boot window {lo}..{hi}"
        )
    assert boot["total"] == len(boot["corridas"])


def test_boot_shard_is_exact_subset_of_web_copy():
    boot, slim = _boot(), _load("web/corridas.json")
    lo, hi = GEN.boot_window(boot.get("gerado_em"))
    expected = [c for c in slim if lo <= (c.get("data_evento") or "") <= hi]
    assert boot["corridas"] == expected, (
        "web/corridas-boot.json is stale — re-run scripts/generate_web_data.py"
    )


def test_boot_shard_meaningfully_smaller_than_web_copy():
    boot = (ROOT / "web" / "corridas-boot.json").stat().st_size
    slim = (ROOT / "web" / "corridas.json").stat().st_size
    assert boot < slim * 0.6, f"boot={boot} slim={slim}: shard not slimming first paint"
