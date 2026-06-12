"""Regression: reconcile must not resurrect merger leftovers.

Real case (prod, 2026-06-12): "Circuito De Corridas Vale - São Luís" existia
como ativo_40257 E corridasbrasil_58913. O merger funde o batch fresco num
único campeão, mas o registro antigo da outra fonte caía em unmatched_future,
passava na checagem de link (a página existe) e era ressuscitado para sempre.
Agora ele é absorvido como duplicata do sobrevivente, levando suas fontes.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# O job de frontend (ci-frontend `test`) instala só requirements-test.txt;
# importar scraper.main puxa httpx/bs4 etc. O teste roda de verdade no
# `validate` (ci-scraper), que instala as dependências completas.
try:
    from scraper.main import reconcile
    from scraper.models import Corrida, Distancia, FonteInfo
except ImportError as exc:  # pragma: no cover
    pytest.skip(f"dependências do scraper indisponíveis: {exc}",
                allow_module_level=True)


def _ev(id_, fonte_nome, link):
    futuro = (date.today() + timedelta(days=30)).isoformat()
    return Corrida(
        id=id_,
        titulo="Circuito De Corridas Vale - São Luís",
        data_evento=futuro,
        horario="05:30",
        localizacao="São Luís, MA",
        cidade="São Luís",
        estado="MA",
        pais="BR",
        distancias=[Distancia(km=5.0, data=None, horario=None),
                    Distancia(km=10.0, data=None, horario=None)],
        imagem_url=None,
        inscricoes_abertas=None,
        periodo_inscricao=None,
        fontes=[FonteInfo(nome=fonte_nome, link_evento=link,
                          links_inscricao=[link], tipo="calendario")],
        miss_count=0,
        first_seen_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def test_unmatched_old_duplicate_is_absorbed_not_resurrected():
    fresh = _ev("ativo_40257", "Ativo", "https://ativo.com/a")
    fresh.fontes.append(FonteInfo(nome="Corridas Brasil",
                                  link_evento="https://corridasbrasil.com.br/b",
                                  links_inscricao=["https://corridasbrasil.com.br/b"],
                                  tipo="calendario"))
    old_a = _ev("ativo_40257", "Ativo", "https://ativo.com/a")
    old_b = _ev("corridasbrasil_58913", "Corridas Brasil", "https://corridasbrasil.com.br/b")

    result = reconcile({old_a.id: old_a, old_b.id: old_b}, [fresh])

    same_day = [c for c in result if c.data_evento == fresh.data_evento]
    assert len(same_day) == 1, f"duplicata ressuscitada: {[c.id for c in same_day]}"
    nomes = {f.nome for f in same_day[0].fontes}
    assert {"Ativo", "Corridas Brasil"} <= nomes
