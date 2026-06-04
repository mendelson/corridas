# Central da Corrida (`central_da_corrida.py`) — research notes

**Status:** ATIVA. Bug de distâncias corrigido em 2026-06-04.

---

## O que a fonte é

Calendário brasileiro de corridas em `centraldacorrida.com.br`, construído no
**Bubble.io**. Os dados vêm de uma **Supabase Edge Function** pública:

```
GET https://tudmqbzxfbrjljpdpili.supabase.co/functions/v1/eventos-publicos?Data_evento=gte.{YYYY-MM-DD}
```

⚠️ **A function ignora os filtros PostgREST.** Sondado em 2026-06-04: tanto
`?slug=eq.2supersunset` quanto `?Nome_evento=ilike.*sunset*` retornaram **a lista
completa (385 eventos)**. O filtro `Data_evento=gte.` usado no scraper provavelmente
também é ignorado — a filtragem por data acontece no lado do scraper (`data_evento < today`).

Cada evento é um dict de 39 chaves. As relevantes:

| Campo | Conteúdo |
|---|---|
| `Nome_evento` | título (`'null'` string quando vazio) |
| `Data_evento` / `data_2` | ISO datetime com TZ — data **e** horário de largada |
| `Cidade`, `Estado` | localização (UF de 2 letras) |
| `slug` | usado na URL pública `/evento/{slug}` |
| `regulamento`, `descricao_evento` | texto rico do Bubble — **fonte das distâncias** |
| `Publicado` (`sim`/`não`), `Ativo` (`não` = cancelado) | filtros de visibilidade |
| `imagem` | banner (CDN bubble.io, prefixo `//`) |

O texto rico usa marcação Bubble: `[h3]`, `[b]`, `[color=rgb(...)]`,
`[highlight=rgb(...)]`, e o literal **`[BARRA_INVERTIDA]n`** no lugar de `\n`.

---

## Bug corrigido (2026-06-04): listas de distância com sufixo `km` compartilhado

**Exemplo reportado:** `https://centraldacorrida.com.br/evento/2supersunset`
("2º Super Sunset Run"). O regulamento diz:

> "…com as **distâncias de 3, 5 e 10 km** com largada na Praça do Cruzeiro às 17:00 h…"

O scraper antigo mostrava distâncias **erradas** (`[3, 10]`, faltando o 5).

### Causa raiz

O extrator antigo procurava cada número **individualmente seguido de `km`** com
`\b(\d+)\s*k(?:m)?\b`. Em português, listas de distância usam **um único sufixo `km`
no final**: "3, 5 e 10 km" significa 3 km, 5 km **e** 10 km — mas só o `10` carrega o
"km". O regex capturava apenas o `10` (e o `3` de "caminhada de 3km" em outro trecho),
**descartando silenciosamente o 5**.

É exatamente a mesma classe de bug corrigida no `correr_brasilia.py` no PR #196.

### Correção

`_extract_distances` foi reescrito para ler distâncias **apenas de enumerações
explícitas**, na ordem:

1. **Listas de tokens** (`_DIST_LIST_RE`) — "5km, 10km e meia maratona" (2+ tokens).
2. **Sufixo `km` compartilhado** (`_DIST_SHARED_SUFFIX_RE`) — "3, 5 e 10 km" → 3, 5, 10.
3. **Valor rotulado** (`_DIST_LABELLED_RE`) — "Modalidade: Maratona", "Distância: 42km".
4. **Fallback numérico** — qualquer `Xkm` explícito (prose-safe, só lê números).

Distâncias nomeadas (`maratona`→42.195, `meia maratona`→21.097) só contam quando são
**token de enumeração** (membro de lista ou valor rotulado), nunca soltas em prosa —
o que impede que "a maior maratona do DF" (coloquial) injete uma maratona-fantasma.
Valores numéricos sofrem *canonical-snap* (42 / 42,2 / 42.195 → uma só; idem 21).
Piso de `3 km` preservado para excluir caminhadas/kids/ruído de hidratação.

### Validação (local, sem rede, contra o JSON real da API)

```
2supersunset   "distâncias de 3, 5 e 10 km"      → [3.0, 5.0, 10.0]      ✓ (5 recuperado)
ue2026         "17h - Corrida 5km e 10km"        → [5.0, 10.0]           ✓
onerun2026     "1, 5 e 10km" + "21km" + 2,5km    → [5.0, 10.0, 21.097]   ✓ (1km/2,5km caminhada excluídos)
prose "a maior maratona do DF" + "5km e 10km"    → [5.0, 10.0]           ✓ sem maratona-fantasma
```

---

## Notas de integridade

- **Horário é obrigatório e está disponível**: `Data_evento` é ISO com TZ; o scraper
  converte para BRT (`_parse_datetime`) e descarta o evento se `horario is None`.
- **Localização**: `Cidade`/`Estado` quase sempre presentes; `_geo.resolve` preenche
  `estado` em falta.
- **Fallback de distâncias**: quando o regulamento não enumera, o scraper segue URLs
  externas embutidas (`_fetch_distances_from_url`) e aplica o mesmo extrator.
- **Eventos kids** (`_KIDS_RE`) e cancelados (`Ativo == 'não'`) são descartados.
