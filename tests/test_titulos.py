"""Regression tests for utils.normalize_titulo — roman edition numerals must
stay uppercase through title-casing ("IX Corrida", never "Ix Corrida")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.utils import normalize_titulo


def test_roman_numerals_uppercased():
    assert normalize_titulo("iv corrida da paz") == "IV Corrida Da Paz"
    assert normalize_titulo("IX CONEZO - CONGRESSO") == "IX Conezo - Congresso"
    assert normalize_titulo("CORRIDA DO FOGO - ETAPA III") == "Corrida Do Fogo - Etapa III"
    assert normalize_titulo("XXVII SÃO SILVESTRE DE LONDRINA") == "XXVII São Silvestre De Londrina"
    assert normalize_titulo("VI. CORRIDA NOTURNA") == "VI. Corrida Noturna"


def test_roman_lookalike_words_untouched():
    # Words that title-case into roman lookalikes must NOT be uppercased —
    # only I/V/X numerals (1–39) qualify, never L/C/D/M combinations.
    assert normalize_titulo("CORRIDA MIX MATEUS") == "Corrida Mix Mateus"
    assert normalize_titulo("LIV RUN FESTIVAL") == "Liv Run Festival"


def test_existing_abbreviations_preserved():
    assert normalize_titulo("corrida 5k e 10k") == "Corrida 5K E 10K"
