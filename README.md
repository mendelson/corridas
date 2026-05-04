# Corridas BR

Agrega e exibe corridas de rua no Brasil — com foco em Brasília-DF, nas principais
maratonas nacionais e nos World Marathon Majors. Eventos encontrados em múltiplas fontes
são consolidados em um único registro. Atualizado automaticamente a cada 4 horas via
GitHub Actions.

**App:** [mendelson.github.io/corridas](https://mendelson.github.io/corridas) ·
**Stack:** Python (httpx + BeautifulSoup4 + Playwright) · JSON · HTML/CSS/JS puro · GitHub Pages

---

## Fontes ativas

### Fontes brasileiras — calendários gerais

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Ticket Sports<!--ticket_sports--> | ✅ | `ticketsports.app/api/events/list` | JSON API | 2026-05-03 22:59 | ✅ | 2026-05-03 22:59 |
| Circuito das Estações<!--circuito_das_estacoes--> | ✅ | `hotsites.nortemkt.com/api/events/circuito-das-estacoes` | JSON API dedicada | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Central da Corrida<!--central_da_corrida--> | ✅ | `centraldacorrida.com.br/calendario` | HTML | 2026-05-03 22:56 | ✅ | 2026-05-03 22:56 |
| TF Sports<!--tf_sports--> | ✅ | `painel-website.tfsports.com.br/api` + `tfsports.com.br` | JSON API + HTML | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |
| Yescom<!--yescom--> | ✅ | `yescom.com.br` | HTML | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Brasil Corrida<!--brasil_corrida--> | ✅ | `brasilcorrida.com.br/api/src/Site` | JSON API | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Iguana Sports<!--iguana_sports--> | ✅ | `iguanasports.com.br/blogs/calendario-corridas-de-rua` | HTML | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Ativo<!--ativo--> | ✅ | `ativo.com/eventos.json` | JSON API | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| MKS Esportes<!--mks_esportes--> | ✅ | `mksesportes.com.br` (sitemap + HTML) | HTML | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Corridas Brasil<!--corridas_brasil--> | ✅ | `corridasbrasil.com.br/calendario/` | HTML | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Minhas Inscrições<!--minhas_inscricoes--> | ✅ | `minhasinscricoes.com.br/pt-br/calendario?url=corrida-de-rua` | HTML | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |
| Runner Brasil<!--runner_brasil--> | ✅ | `runnerbrasil.com.br` | HTML | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| GoDream<!--godream--> | ✅ | `godream.com.br/corrida-de-rua` | Playwright (intercepção de JSON) | 2026-05-04 00:55 | ❌ 0 eventos | — |
| Portal das Corridas<!--portal_das_corridas--> | ✅ | `portaldascorridas.com.br` | Playwright (SPA) | 2026-05-03 22:58 | ❌ 0 eventos | — |

### Fontes brasileiras — específicas Brasília-DF

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Brasil que Corre<!--brasil_que_corre--> | ✅¹ | `brasilquecorre.com/distritofederal` | HTML | 2026-05-03 22:56 | ❌ 0 eventos | — |
| Correr Brasília<!--correr_brasilia--> | ✅ | `correrbrasilia.com.br/calendario/` | HTML | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| SESC DF<!--sesc_df--> | ✅ | `sescdf.com.br/corridas` | HTML | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |

> ¹ Retorna 0 eventos — `brasilquecorre.com` bloqueia IPs de datacenter (403). Playwright não bypassa.

### Fontes brasileiras — eventos específicos

| Fonte | Em uso | URL de busca | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Maratona do Rio<!--maratona_rio--> | ✅ | `maratonadorio.com.br` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Maratona de Porto Alegre<!--maratona_porto_alegre--> | ✅ | `maratonadeportoalegre.com.br` | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |
| SP City Marathon<!--sp_city_marathon--> | ✅ | `iguanasports.com.br/products/sp-city-marathon-{ano}` | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |
| São Silvestre<!--sao_silvestre--> | ✅ | `saosilvestre.com.br` | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |
| Volta do Lago<!--volta_do_lago--> | ✅ | `voltadolago.com.br` | 2026-05-03 22:58 | ❌ 0 eventos | — |

### Fontes com WAF intransponível

Estas fontes estão registradas no código mas retornam 0 eventos. O bloqueio ocorre em nível de IP de datacenter — Scrapestack e Apify (datacenter) também são bloqueados, e Playwright headless não bypassa o Cloudflare dessas propriedades.

| Fonte | URL | Situação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Live Run<!--liverun--> | `liverun.com.br/calendario` | 403 → proxies falham → sem fallback implementado | 2026-05-03 22:57 | ❌ 0 eventos | — |
| Let's Do This<!--lets_do_this--> | `letsdothis.com` (calendário UK) | 403 → proxies falham → Playwright renderiza 992KB mas eventos carregam via API client-side | 2026-05-03 22:57 | ❌ 0 eventos | — |
| World Marathons<!--world_marathons--> | `worldsmarathons.com` | Cloudflare retorna challenge page (370KB) tanto via HTTP quanto via Playwright | 2026-05-03 22:58 | ❌ 0 eventos | — |

### Fontes internacionais

| Fonte | Em uso | URL de busca | Observação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Cardiff Half Marathon<!--majors/cardiff_half--> | ✅ | `cardiffhalfmarathon.co.uk` | Acesso via Scrapestack | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |

---

## World Marathon Majors

22 scrapers dedicados em `scraper/sources/majors/`. Retornam 1–2 edições futuras com
projeção automática para o ano seguinte quando todas as datas conhecidas já passaram.

| Evento | Em uso | URL oficial | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Tokyo Marathon<!--majors/tokyo--> | ✅ | `marathon.tokyo/en` | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |
| Boston Marathon<!--majors/boston--> | ✅ | `baa.org/races/boston-marathon` | 2026-05-03 22:56 | ✅ | 2026-05-03 22:56 |
| Brighton Marathon<!--majors/brighton--> | ✅ | `londonmarathonevents.co.uk/brighton-marathon-weekend` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Paris Marathon<!--majors/paris--> | ✅ | `schneiderelectricparismarathon.com/en` | 2026-05-03 22:56 | ✅ | 2026-05-03 22:56 |
| TCS London Marathon<!--majors/london--> | ✅ | `tcslondonmarathon.com` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Prague Marathon<!--majors/prague--> | ✅ | `runczech.com/en/events/prague-international-marathon-2026` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Copenhagen Marathon<!--majors/copenhagen--> | ✅ | `copenhagenmarathon.dk/en` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Edinburgh Marathon Festival<!--majors/edinburgh--> | ✅ | `edinburghmarathon.com` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Stockholm Marathon<!--majors/stockholm--> | ✅ | `stockholmmarathon.se/eng` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Manchester Marathon<!--majors/manchester--> | ✅ | `manchestermarathon.co.uk` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| TCS Sydney Marathon<!--majors/sydney--> | ✅ | `tcssydneymarathon.com` | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |
| Great North Run<!--majors/great_north_run--> | ✅ | `greatrun.org/events/great-north-run` | 2026-05-03 22:56 | ✅ | 2026-05-03 22:56 |
| BMW Berlin Marathon<!--majors/berlin--> | ✅ | `bmw-berlin-marathon.com/en` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Cardiff Half Marathon<!--majors/cardiff_half--> | ✅ | `cardiffhalfmarathon.co.uk` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Manchester Half Marathon<!--majors/manchester_half--> | ✅ | `manchesterhalfmarathon.com` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Bank of America Chicago Marathon<!--majors/chicago--> | ✅ | `chicagomarathon.com` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Amsterdam Marathon<!--majors/amsterdam--> | ✅ | `tcsamsterdammarathon.nl/en` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Venice Marathon<!--majors/venice--> | ✅ | `venicemarathon.it/en` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Dublin City Marathon<!--majors/dublin--> | ✅ | `irishlifedublinmarathon.ie` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| TCS New York City Marathon<!--majors/nyc--> | ✅ | `nyrr.org/races/tcsnycmarathon` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Athens Classic Marathon<!--majors/athens--> | ✅ | `athensauthenticmarathon.gr/en` | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Valencia Marathon<!--majors/valencia--> | ✅ | `valenciaciudaddelrunning.com/en/marathon` | 2026-05-03 22:58 | ✅ | 2026-05-03 22:58 |

---

## Estratégia de acesso

Cada requisição HTTP passa pela cadeia de fallback implementada em `http_client.py`:

1. **Direto** — request padrão com headers de browser realista
2. **Scrapestack** — proxy reverso (100 req/mês no plano gratuito); ativado via `SCRAPESTACK_KEY`
3. **Apify proxy** — proxy de datacenter; ativado via `APIFY_PROXY_PASSWORD`

Se todos falharem (403/429), o scraper da fonte tenta **Playwright headless** com configurações básicas anti-detecção (desativa `navigator.webdriver`, simula `window.chrome`). Isso funciona para alguns WAFs, mas não para Cloudflare em modo estrito.

Buscas de fotos (`fotos.py`) usam `get_direct()` — sem proxy — para não consumir créditos do Scrapestack.

---

## Fontes desativadas

| Fonte | Em uso | URL | Motivo | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Corridas BR<!--corridas_br--> | ❌ | `corridasbr.com.br/df/calendario.asp` | Agrega eventos de outras fontes sem links de inscrição reais. Retorna 403 no CI. | 2026-05-03 22:57 | ✅ | 2026-05-03 22:57 |
| Bora Correr<!--bora_correr--> | ❌ | `coelhodeprograma.com.br/boracorrer` | Implementado mas nunca ativado. Retorna 403 no CI. | 2026-05-03 22:57 | ❌ 0 eventos | — |

## Fontes testadas e inviáveis

| Fonte | URL | Motivo |
|---|---|---|
| Ahotu | `ahotu.com/pt-br/races` | WAF bloqueia IPs de datacenter em nível de rede. Playwright não resolve. |
| Finishers | `finishers.com/pt-br/races?country=BR` | Mesmo bloqueio que Ahotu. |

---

## Estrutura do repositório

```
corridas/
├── .github/workflows/
│   ├── scrape.yml           # CI: roda a cada 4h, commita JSON atualizado
│   ├── test-sources.yml     # CI/manual: testa cada fonte como job independente (matrix com dropdown)
│   └── debug-scraper.yml    # Workflow manual para diagnóstico de fonte individual (com artefato de log)
├── scraper/
│   ├── main.py              # Orquestrador: executa scrapers, merge, persistência
│   ├── models.py            # Dataclasses: Corrida, Distancia, FonteInfo, etc.
│   ├── merger.py            # Deduplicação e merge entre fontes
│   ├── utils.py             # Normalização de datas, strings, slugify, cidade→estado
│   ├── http_client.py       # GET com fallback: direto → Scrapestack → Apify
│   ├── playwright_client.py # Playwright headless com evasão básica de bot-detection
│   ├── fotos.py             # Busca de fotos em plataformas (desativada temporariamente)
│   └── sources/
│       ├── *.py             # Scrapers brasileiros
│       └── majors/          # Scrapers dos World Marathon Majors
├── data/
│   ├── corridas.json        # Base acumulativa (versionada no repo)
│   └── last-scraper.log     # Log da última execução do CI
└── web/
    ├── index.html           # Redirect para /pt ou /en conforme idioma do browser
    ├── pt/ en/ es/ de/ fr/  # Páginas por idioma
    ├── app.js               # Lógica do app (filtros, cards, i18n)
    ├── style.css
    └── manifest.json        # PWA
```
