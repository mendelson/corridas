# US Road Running (`usroadrunning.py`) — research notes

**Status:** ATIVA (adicionada 2026-06-05). Fonte internacional (EUA).
`tipo = "organizador"`.

## O que é

`usroadrunning.com` é uma **organizadora americana** que realiza séries temáticas
próprias (Medal Madness, Haunted, Eagle, Ninja…) nas modalidades **5K / 10K /
Meia (13.1 mi)** em dezenas de cidades dos EUA. A inscrição é processada pelo
**RunSignup** (cada evento tem `offers.url` → `runsignup.com/...`), mas o site da
organizadora é a página oficial do evento e expõe dados estruturados completos.

## Sondagem (2026-06-05)

| URL | Resultado |
|---|---|
| `/` | 200, sem WAF |
| `/robots.txt` | 200 — sem `Disallow` nas páginas de corrida; lista `sitemap.xml` |
| `/sitemap.xml` | 200 (~197 KB) — ~570 páginas de evento `Races/{UF}/{Cidade}/{id}-{Nome}-…/` |
| `/Races/{UF}/{Cidade}/{id}-…/` (detalhe) | 200 — JSON-LD `["Event","SportsEvent"]` completo |
| `/Races/NearMe/RaceSearch.php?event_type=running_race&state={UF}` | 200 — **20 blocos `["Event","SportsEvent"]` inline** (próximos eventos do estado) |

Acessível por `httpx` direto, sem proxy/Playwright.

## Arquitetura escolhida — listagem por estado (barata)

Em vez de buscar as ~570 páginas de detalhe, o scraper usa a **listagem de
busca por estado**, que já embute o schema completo de cada evento:

```
GET /Races/NearMe/RaceSearch.php?event_type=running_race&state=<UF>[&start_date=YYYY-MM-DD]
```

- A resposta tem **um JSON-LD com `@graph`** contendo um `ItemList` + um objeto
  `@type: ["Event","SportsEvent"]` por corrida (≈20 próximos eventos).
  ⚠️ **Cuidado:** os eventos estão dentro de `@graph`, não como `<script
  type="application/ld+json">` separados — o parser precisa achatar o `@graph`.
- **Paginação por data:** o parâmetro `start_date` desloca a janela. O scraper
  refaz a busca com `start_date = (maior data vista) + 1 dia` até a página não
  trazer evento novo (cap de segurança `_MAX_PAGES_PER_STATE = 18`).
- Itera os 50 estados + DC.

## Mapeamento de campos (do JSON-LD `Event`/`SportsEvent`)

| Campo | Origem |
|---|---|
| `titulo` | `name` (ex.: "Medal Madness 5K, 10K, & 13.1M at Piedmont, AL (23)") |
| `data_evento` + `horario` | `startDate` (`2026-06-06T08:00:00-05:00` → `2026-06-06` + `08:00`) |
| `cidade` / `estado` / `pais` | `location.address` → `addressLocality` / `addressRegion` (UF) / `addressCountry` (US) |
| `distancias` | parse do `name`: `NK` → N km, `NM` → "N mi" (milhas preservadas; `13.1M` → `"13.1 mi"`) |
| `imagem_url` | `image[0]` |
| `id` | id numérico da URL (`/Races/AL/Piedmont/189898-…` → `usrr_189898`) |
| link | a própria URL do evento (`offers.url` do RunSignup **não** é usada como link da fonte) |

`estado` é validado contra `web/locations/US.json` (`geo.validate_estado`); se o
`addressRegion` faltar, tenta `geo.resolve(cidade, "", "US")`. Eventos sem
horário, sem cidade/UF válida ou sem distância são descartados (campos
obrigatórios).

## Redundância com RunSignup

As inscrições são no RunSignup, então pode haver sobreposição com a fonte
`runsignup`. Mitigado pelo merger (dedup por título+data+local). Ganho: a busca
por termos do `runsignup` não cobre todos os eventos do US Road Running, e aqui o
dado é mais limpo (horário e endereço exatos por JSON-LD).

## Validação offline

Parser rodado contra a listagem real da AL: **20 eventos**, 0 com campo
obrigatório faltando, todos com `horario` (08:00), UF válida (AL) e
distâncias `[5.0, 10.0, "13.1 mi"]`.
