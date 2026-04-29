"""Validate data/corridas.json: detects empty dates, malformed URLs,
HTML entities in titles, missing letters, suspicious values.
Exits non-zero when issues are found."""
from __future__ import annotations
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

DATA_PATH = Path(__file__).parent.parent / "data" / "corridas.json"

ISSUES: list[str] = []


def issue(msg: str) -> None:
    ISSUES.append(msg)
    print(f"  ✗ {msg}")


def check_corrida(c: dict) -> None:
    cid = c.get("id", "?")
    titulo = c.get("titulo", "")

    if not titulo or len(titulo) < 4:
        issue(f"[{cid}] título vazio/curto: {titulo!r}")

    # HTML entities or stray symbols suggesting parsing errors
    if any(ent in titulo for ent in ["&amp;", "&lt;", "&gt;", "&quot;", "&#"]):
        issue(f"[{cid}] título com entidade HTML: {titulo!r}")

    # Suspicious garbled chars (mojibake)
    if re.search(r"[ÃÂ][\x80-\x9F¢£¤¥]", titulo):
        issue(f"[{cid}] título possivelmente mojibake: {titulo!r}")

    data_ev = c.get("data_evento", "")
    if not data_ev:
        issue(f"[{cid}] data_evento vazia ({titulo})")
    elif not re.match(r"^\d{4}-\d{2}-\d{2}$", data_ev):
        issue(f"[{cid}] data_evento mal-formada: {data_ev!r}")

    estado = c.get("estado", "")
    if estado in ("", "??"):
        issue(f"[{cid}] estado inválido: {estado!r}")

    fontes = c.get("fontes", [])
    if not fontes:
        issue(f"[{cid}] sem fontes")

    for f in fontes:
        link = f.get("link_evento", "")
        if not link:
            issue(f"[{cid}] fonte {f.get('nome')!r} sem link_evento")
            continue
        u = urlparse(link)
        if u.scheme not in ("http", "https") or not u.netloc:
            issue(f"[{cid}] link_evento mal-formado: {link!r}")
        # Suspicious hint of guessed paths that often 404
        if any(seg in link for seg in ["/enter/", "/register/", "/participants/"]):
            issue(f"[{cid}] link com subpath suspeito (potencial 404): {link!r}")
        for lnk in f.get("links_inscricao", []):
            u = urlparse(lnk)
            if u.scheme not in ("http", "https") or not u.netloc:
                issue(f"[{cid}] links_inscricao mal-formado: {lnk!r}")


def main() -> int:
    if not DATA_PATH.exists():
        print(f"ERRO: {DATA_PATH} não existe", file=sys.stderr)
        return 2

    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    corridas = raw.get("corridas", [])
    print(f"Validando {len(corridas)} corridas em {DATA_PATH}")
    print()

    today = date.today().isoformat()

    for c in corridas:
        check_corrida(c)

    # Aggregate stats
    print()
    print("=== Estatísticas ===")
    com_data = sum(1 for c in corridas if c.get("data_evento"))
    sem_data = len(corridas) - com_data
    futuras = sum(1 for c in corridas if c.get("data_evento", "") >= today)
    passadas = com_data - futuras
    int_count = sum(1 for c in corridas if c.get("estado") == "INT")
    br_count = len(corridas) - int_count
    print(f"  Total:       {len(corridas)}")
    print(f"  Com data:    {com_data}")
    print(f"  Sem data:    {sem_data}")
    print(f"  Futuras:     {futuras}")
    print(f"  Passadas:    {passadas}")
    print(f"  INT:         {int_count}")
    print(f"  BR:          {br_count}")

    print()
    if ISSUES:
        print(f"❌ {len(ISSUES)} problemas encontrados")
        return 1
    print("✅ Sem problemas detectados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
