"""Regression tests for utils.extract_distances_from_text.

The price-table case is verbatim from a probed Ticket Sports event detail
(ts_85715, "Circuito VTR — Etapa Rota do Vulcão"): lot prices joined to the
next distance by "|" used to leak into the shared-suffix matcher and ship
129.9 km "distances" to production cards.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.utils import extract_distances_from_text


def test_lot_price_table_yields_distances_not_prices():
    real = (
        "PRÉ-VENDA (valor único) • Todas as distâncias: R$ 99,90 + taxa "
        "1º LOTE • 7 KM: R$ 129,90 | 15 KM: R$ 139,90 | 30 KM: R$ 159,90 "
        "2º LOTE • 7 KM: R$ 139,90 | 15 KM: R$ 149,90 | 30 KM: R$ 169,90 "
        "3º LOTE • 7 KM: R$ 149,90 | 15 KM: R$ 159,90 | 30 KM: R$ 179,90"
    )
    assert extract_distances_from_text(real) == [7.0, 15.0, 30.0]


def test_standalone_price_does_not_become_distance():
    assert extract_distances_from_text("Inscrição R$ 89,90. Percurso de 10 km") == [10.0]


def test_two_decimal_money_format_rejected_in_shared_suffix():
    assert extract_distances_from_text("99,90 e 10 km") == [10.0]


def test_legit_lists_and_decimals_still_work():
    assert extract_distances_from_text("Percursos de 5km, 10km e meia maratona") == [5.0, 10.0, 21.097]
    assert extract_distances_from_text("3, 5 e 10 km") == [3.0, 5.0, 10.0]
    assert extract_distances_from_text("7,5 km e 15 km") == [7.5, 15.0]
    assert extract_distances_from_text("prova de 21,097 km") == [21.097]
