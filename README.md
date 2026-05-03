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

| Fonte | Em uso | URL de busca | Método |
|---|---|---|---|
| Ticket Sports | ✅ | `ticketsports.app/api/events/list` | JSON API |
| Circuito das Estações | ✅ | `hotsites.nortemkt.com/api/events/circuito-das-estacoes` | JSON API dedicada |
| Central da Corrida | ✅ | `centraldacorrida.com.br/calendario` | HTML |
| TF Sports | ✅ | `painel-website.tfsports.com.br/api` + `tfsports.com.br` | JSON API + HTML |
| Yescom | ✅ | `yescom.com.br` | HTML |
| Brasil Corrida | ✅ | `brasilcorrida.com.br/api/src/Site` | JSON API |
| Iguana Sports | ✅ | `iguanasports.com.br/blogs/calendario-corridas-de-rua` | HTML |
| Ativo | ✅ | `ativo.com/eventos.json` | JSON API |
| MKS Esportes | ✅ | `mksesportes.com.br` (sitemap + HTML) | HTML |
| Corridas Brasil | ✅ | `corridasbrasil.com.br/calendario/` | HTML |
| Minhas Inscrições | ✅ | `minhasinscricoes.com.br/pt-br/calendario?url=corrida-de-rua` | HTML |
| Runner Brasil | ✅ | `runnerbrasil.com.br` | HTML |
| GoDream | ✅ | `godream.com.br/corrida-de-rua` | Playwright (intercepção de JSON) |
| Portal das Corridas | ✅ | `portaldascorridas.com.br` | Playwright (SPA) |

### Fontes brasileiras — específicas Brasília-DF

| Fonte | Em uso | URL de busca | Método |
|---|---|---|---|
| Brasil que Corre | ✅¹ | `brasilquecorre.com/distritofederal` | HTML |
| Correr Brasília | ✅ | `correrbrasilia.com.br/calendario/` | HTML |
| SESC DF | ✅ | `sescdf.com.br/corridas` | HTML |

> ¹ Retorna 0 eventos — `brasilquecorre.com` bloqueia IPs de datacenter (403). Playwright não bypassa.

### Fontes brasileiras — eventos específicos

| Fonte | Em uso | URL de busca |
|---|---|---|
| Maratona do Rio | ✅ | `maratonadorio.com.br` |
| Maratona de Porto Alegre | ✅ | `maratonadeportoalegre.com.br` |
| SP City Marathon | ✅ | `iguanasports.com.br/products/sp-city-marathon-{ano}` |
| São Silvestre | ✅ | `saosilvestre.com.br` |
| Volta do Lago | ✅ | `voltadolago.com.br` |

### Fontes com WAF intransponível

Estas fontes estão registradas no código mas retornam 0 eventos. O bloqueio ocorre em nível de IP de datacenter — Scrapestack e Apify (datacenter) também são bloqueados, e Playwright headless não bypassa o Cloudflare dessas propriedades.

| Fonte | URL | Situação |
|---|---|---|
| Live Run | `liverun.com.br/calendario` | 403 → proxies falham → sem fallback implementado |
| Let's Do This | `letsdothis.com` (calendário UK) | 403 → proxies falham → Playwright renderiza 992KB mas eventos carregam via API client-side |
| World Marathons | `worldsmarathons.com` | Cloudflare retorna challenge page (370KB) tanto via HTTP quanto via Playwright |

### Fontes internacionais

| Fonte | Em uso | URL de busca | Observação |
|---|---|---|---|
| Cardiff Half Marathon | ✅ | `cardiffhalfmarathon.co.uk` | Acesso via Scrapestack |

---

## World Marathon Majors

22 scrapers dedicados em `scraper/sources/majors/`. Retornam 1–2 edições futuras com
projeção automática para o ano seguinte quando todas as datas conhecidas já passaram.

| Evento | Em uso | URL oficial |
|---|---|---|
| Tokyo Marathon | ✅ | `marathon.tokyo/en` |
| Boston Marathon | ✅ | `baa.org/races/boston-marathon` |
| Brighton Marathon | ✅ | `londonmarathonevents.co.uk/brighton-marathon-weekend` |
| Paris Marathon | ✅ | `schneiderelectricparismarathon.com/en` |
| TCS London Marathon | ✅ | `tcslondonmarathon.com` |
| Prague Marathon | ✅ | `runczech.com/en/events/prague-international-marathon-2026` |
| Copenhagen Marathon | ✅ | `copenhagenmarathon.dk/en` |
| Edinburgh Marathon Festival | ✅ | `edinburghmarathon.com` |
| Stockholm Marathon | ✅ | `stockholmmarathon.se/eng` |
| Manchester Marathon | ✅ | `manchestermarathon.co.uk` |
| TCS Sydney Marathon | ✅ | `tcssydneymarathon.com` |
| Great North Run | ✅ | `greatrun.org/events/great-north-run` |
| BMW Berlin Marathon | ✅ | `bmw-berlin-marathon.com/en` |
| Cardiff Half Marathon | ✅ | `cardiffhalfmarathon.co.uk` |
| Manchester Half Marathon | ✅ | `manchesterhalfmarathon.com` |
| Bank of America Chicago Marathon | ✅ | `chicagomarathon.com` |
| Amsterdam Marathon | ✅ | `tcsamsterdammarathon.nl/en` |
| Venice Marathon | ✅ | `venicemarathon.it/en` |
| Dublin City Marathon | ✅ | `irishlifedublinmarathon.ie` |
| TCS New York City Marathon | ✅ | `nyrr.org/races/tcsnycmarathon` |
| Athens Classic Marathon | ✅ | `athensauthenticmarathon.gr/en` |
| Valencia Marathon | ✅ | `valenciaciudaddelrunning.com/en/marathon` |

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

| Fonte | Em uso | URL | Motivo |
|---|---|---|---|
| Corridas BR | ❌ | `corridasbr.com.br/df/calendario.asp` | Agrega eventos de outras fontes sem links de inscrição reais. Retorna 403 no CI. |
| Bora Correr | ❌ | `coelhodeprograma.com.br/boracorrer` | Implementado mas nunca ativado. Retorna 403 no CI. |

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
