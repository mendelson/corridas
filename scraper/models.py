from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

# "inscricao"  — platform where the user actually registers (Ticket Sports, RunSignup, …)
# "organizador" — official race organizer site (Maratona Rio, TF Sports, majors, …)
# "calendario"  — aggregator/calendar that lists events but doesn't process registration
FonteTipo = Literal["inscricao", "organizador", "calendario"]


@dataclass
class FonteInfo:
    nome: str
    link_evento: str
    links_inscricao: list[str]
    tipo: FonteTipo


@dataclass
class PeriodoInscricao:
    abertura: str | None
    encerramento: str | None


@dataclass
class Distancia:
    km: float | str
    data: str | None
    horario: str | None


@dataclass
class Corrida:
    id: str
    titulo: str
    data_evento: str
    horario: str | None
    localizacao: str
    cidade: str
    estado: str
    distancias: list[Distancia]
    imagem_url: str | None
    inscricoes_abertas: bool | None
    periodo_inscricao: PeriodoInscricao | None
    fontes: list[FonteInfo]
    miss_count: int
    first_seen_at: str
    updated_at: str
    pais: str = "BR"
    fotos: list[dict] = field(default_factory=list)
