# Corridas BR

Agrega e exibe corridas de rua — eventos brasileiros (todas as regiões), mexicanos,
norte-americanos, britânicos e as principais maratonas internacionais.
Eventos encontrados em múltiplas fontes são consolidados em um único registro.
Atualizado automaticamente a cada 4 horas via GitHub Actions.

**App:** [mendelson.github.io/corridas](https://mendelson.github.io/corridas) ·
**Stack:** Python (httpx + BeautifulSoup4 + Playwright) · JSON · HTML/CSS/JS puro · GitHub Pages

---

## Fontes ativas

### Fontes brasileiras — calendários gerais

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Ticket Sports<!--ticket_sports--> | ✅ | `ticketsports.app/api/events/list` | JSON API | 2026-05-17 02:41 | ❌ | 2026-05-15 18:36 |
| Circuito das Estações<!--circuito_das_estacoes--> | ✅ | `hotsites.nortemkt.com/api/events/circuito-das-estacoes` | JSON API dedicada | 2026-05-17 02:41 | ❌ | 2026-05-15 18:36 |
| Central da Corrida<!--central_da_corrida--> | ✅ | `centraldacorrida.com.br/calendario` | Supabase edge-function API | 2026-05-18 16:34 | ✅ | 2026-05-18 16:34 |
| TF Sports<!--tf_sports--> | ✅ | `painel-website.tfsports.com.br/api` + `tfsports.com.br` | Strapi v4 API + token do bundle Next.js | 2026-05-17 02:41 | ❌ | 2026-05-16 18:47 |
| Yescom<!--yescom--> | ✅ | `yescom.com.br` | HTML (homepage + páginas de evento) | 2026-05-18 16:34 | ✅ | 2026-05-18 16:34 |
| Brasil Corrida<!--brasil_corrida--> | ✅ | `brasilcorrida.com.br/api/src/Site` | JSON API | 2026-05-15 18:38 | ✅ | 2026-05-15 18:38 |
| Iguana Sports<!--iguana_sports--> | ✅ | `iguanasports.com.br/blogs/calendario-corridas-de-rua` | HTML (blog de calendário) | 2026-05-18 16:34 | ✅ | 2026-05-18 16:34 |
| Ativo<!--ativo--> | ✅ | `ativo.com/eventos.json` | JSON API | 2026-05-17 02:41 | ❌ | 2026-05-15 18:36 |
| MKS Esportes<!--mks_esportes--> | ✅ | `mksesportes.com.br` (sitemap + HTML) | HTML | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| Corridas Brasil<!--corridas_brasil--> | ✅ | `corridasbrasil.com.br/calendario/` | HTML | 2026-05-18 16:34 | ✅ | 2026-05-18 16:34 |
| Minhas Inscrições<!--minhas_inscricoes--> | ✅ | `minhasinscricoes.com.br/pt-br/calendario?url=corrida-de-rua` | HTML | 2026-05-18 16:34 | ✅ | 2026-05-18 16:34 |
| Runner Brasil<!--runner_brasil--> | ✅ | `runnerbrasil.com.br` | HTML | 2026-05-18 16:34 | ✅ | 2026-05-18 16:34 |
| Largada Esportiva<!--largada_esportiva--> | ✅ | `largadaesportiva.com.br` | Playwright (intercepção de JSON) + HTML | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |

### Fontes brasileiras — específicas Brasília-DF

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Correr Brasília<!--correr_brasilia--> | ✅ | `correrbrasilia.com.br/calendario/` | HTML | 2026-05-18 16:34 | ✅ | 2026-05-18 16:34 |
| SESC DF<!--sesc_df--> | ✅ | `sescdf.com.br/corridas` | HTML | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |

### Fontes brasileiras — eventos específicos

| Fonte | Em uso | URL de busca | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Maratona do Rio<!--maratona_rio--> | ✅ | `maratonadorio.com.br` | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| Maratona de Porto Alegre<!--maratona_porto_alegre--> | ✅ | `maratonadeportoalegre.com.br` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:37 |
| SP City Marathon<!--sp_city_marathon--> | ✅ | `iguanasports.com.br/products/sp-city-marathon-{ano}` | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| São Silvestre<!--sao_silvestre--> | ✅ | `saosilvestre.com.br` | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| Volta do Lago<!--volta_do_lago--> | ✅ | `largadaesportiva.com.br/api/Events` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |

### Fontes mexicanas

| Fonte | Em uso | URL de busca | Observação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Asdeporte<!--asdeporte--> | ✅ | `asdeporte.com/eventos` | Next.js; extrai `pageProps.recomended` do `__NEXT_DATA__`; ~30 eventos/run | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| FMAA<!--fmaa--> | ✅ | `fmaa.apps-mexico.com/wp-json/tribe/events/v1/events` | The Events Calendar API; nenhum evento publicado atualmente | 2026-05-15 18:36 | ❌ 0 eventos | — |

### Fontes internacionais — plataformas agregadoras

| Fonte | Em uso | URL de busca | Observação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| HalfMarathons.net<!--halfmarathons--> | ✅ | `halfmarathons.net/wp-json/wp/v2/races` | WordPress REST API paginada (EUA); distâncias em milhas como string | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| RunSignup<!--runsignup--> | ✅ | `runsignup.com/Rest/races` | REST API paginada (EUA/global); distâncias em milhas preservadas como string | 2026-05-17 02:26 | ✅ | 2026-05-17 02:26 |
| World Athletics<!--world_athletics--> | ✅ | `worldathletics.org/competitions/world-athletics-label-road-races` | HTML público; `__NEXT_DATA__`; provas com Label IAAF (Platinum/Gold/Silver/Bronze) | 2026-05-16 01:14 | ✅ | 2026-05-16 01:14 |
| Race Roster<!--raceroster--> | ✅ | `search.raceroster.com/search` | REST API pública; paginada por termo de busca; distâncias parseadas de strings como `42km`/`3mi` | 2026-05-16 01:14 | ✅ | 2026-05-16 01:14 |

---

## Grandes corridas internacionais

22 scrapers dedicados em `scraper/sources/majors/`. Cada um retorna 1–2 edições futuras;
quando todas as datas conhecidas já passaram, o scraper aguarda o anúncio da próxima edição.

Os 7 marcados com ⭐ são os **Abbott World Marathon Majors** (as "Six Majors" + Sydney).
Os demais são grandes provas internacionais de destaque mas não pertencem ao grupo WMM.

| Evento | ⭐ WMM | Em uso | URL oficial | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Tokyo Marathon<!--majors/tokyo--> | ⭐ | ✅ | `marathon.tokyo/en` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:36 |
| Boston Marathon<!--majors/boston--> | ⭐ | ✅ | `baa.org/races/boston-marathon` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| TCS London Marathon<!--majors/london--> | ⭐ | ✅ | `tcslondonmarathon.com` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:36 |
| BMW Berlin Marathon<!--majors/berlin--> | ⭐ | ✅ | `bmw-berlin-marathon.com/en` | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| Bank of America Chicago Marathon<!--majors/chicago--> | ⭐ | ✅ | `chicagomarathon.com` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| TCS New York City Marathon<!--majors/nyc--> | ⭐ | ✅ | `nyrr.org/races/tcsnycmarathon` | 2026-05-17 02:40 | ❌ | 2026-05-15 18:37 |
| TCS Sydney Marathon<!--majors/sydney--> | ⭐ | ✅ | `tcssydneymarathon.com` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:36 |
| Schneider Electric Paris Marathon<!--majors/paris--> | | ✅ | `schneiderelectricparismarathon.com/en` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:37 |
| Brighton Marathon<!--majors/brighton--> | | ✅ | `londonmarathonevents.co.uk/brighton-marathon-weekend` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| Volkswagen Prague Marathon<!--majors/prague--> | | ✅ | `runczech.com/en/events` | 2026-05-15 18:36 | ❌ 0 eventos | 2026-05-10 22:35 |
| Copenhagen Marathon<!--majors/copenhagen--> | | ✅ | `copenhagenmarathon.dk/en` | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| Edinburgh Marathon Festival<!--majors/edinburgh--> | | ✅ | `edinburghmarathon.com` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| Stockholm Marathon<!--majors/stockholm--> | | ✅ | `stockholmmarathon.se/eng` | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| Manchester Marathon<!--majors/manchester--> | | ✅ | `manchestermarathon.co.uk` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| Great North Run<!--majors/great_north_run--> | | ✅ | `greatrun.org/events/great-north-run` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| Cardiff Half Marathon<!--majors/cardiff_half--> | | ✅ | `cardiffhalfmarathon.co.uk` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:36 |
| Manchester Half Marathon<!--majors/manchester_half--> | | ✅ | `manchesterhalfmarathon.com` | 2026-05-17 02:40 | ❌ | 2026-05-15 18:36 |
| TCS Amsterdam Marathon<!--majors/amsterdam--> | | ✅ | `tcsamsterdammarathon.nl/en` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:37 |
| Venice Marathon<!--majors/venice--> | | ✅ | `venicemarathon.it/en` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| Dublin City Marathon<!--majors/dublin--> | | ✅ | `irishlifedublinmarathon.ie` | 2026-05-15 18:37 | ✅ | 2026-05-15 18:37 |
| Athens Classic Marathon<!--majors/athens--> | | ✅ | `athensauthenticmarathon.gr/en` | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| Valencia Trinidad Alfonso Marathon<!--majors/valencia--> | | ✅ | `valenciaciudaddelrunning.com/en/marathon` | 2026-05-17 02:41 | ❌ | 2026-05-15 18:37 |

---

## Estratégia de acesso

Cada requisição HTTP passa pela cadeia de fallback implementada em `http_client.py`:

1. **Direto** — request padrão com headers de browser realista
2. **Scrapestack** — proxy reverso (100 req/mês no plano gratuito); ativado via `SCRAPESTACK_KEY`
3. **Apify proxy** — proxy de datacenter; ativado via `APIFY_PROXY_PASSWORD`

Se todos falharem (403/429), o scraper da fonte tenta **Playwright headless** com configurações básicas anti-detecção (desativa `navigator.webdriver`, simula `window.chrome`). Isso funciona para alguns WAFs, mas não para Cloudflare em modo estrito.

Os scrapers de grandes corridas internacionais (`majors/`) têm fallback adicional: quando o HTTP falha, retornam o evento com a data conhecida (`known_date`) em vez de retornar zero resultados.

Buscas de fotos (`fotos.py`) usam `get_direct()` — sem proxy — para não consumir créditos do Scrapestack.

---

## Fontes desativadas

| Fonte | Em uso | URL | Motivo | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Corridas BR<!--corridas_br--> | ❌ | `corridasbr.com.br/df/calendario.asp` | Agrega eventos de outras fontes sem links de inscrição reais. Retorna 403 no CI. | 2026-05-15 18:36 | ✅ | 2026-05-15 18:36 |
| Bora Correr<!--bora_correr--> | ❌ | `coelhodeprograma.com.br/boracorrer` | Implementado mas nunca ativado. Seletores CSS genéricos nunca casaram com o HTML real do site. | 2026-05-11 15:57 | ❌ | — |
| Brasil que Corre<!--brasil_que_corre--> | ❌ | `brasilquecorre.com/distritofederal` | Seletores CSS genéricos não casam com o HTML real do site. | 2026-05-11 15:57 | ❌ | — |
| Portal das Corridas<!--portal_das_corridas--> | ❌ | `portaldascorridas.com.br` | Playwright retorna 0 — SPA com seletores genéricos que não casam com o DOM real. | 2026-05-11 15:57 | ❌ | — |
| Sympla | ❌ | `sympla.com.br/busca?q=corrida` | URL de busca retorna HTTP 404; Playwright redireciona para página de login. | 2026-05-11 15:57 | ❌ | — |

## Fontes testadas e inviáveis

| Fonte | URL | Motivo | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Ahotu | `ahotu.com/pt-br/races` | WAF bloqueia IPs de datacenter em nível de rede. Playwright não resolve. | — | — | — |
| Finishers | `finishers.com/pt-br/races?country=BR` | Mesmo bloqueio que Ahotu. | — | — | — |
| GoDream<!--godream--> | `godream.com.br/corrida-de-rua` | WAF confirmado: 403 direto + Scrapestack 429 + Apify 403 + Playwright `ERR_TUNNEL_CONNECTION_FAILED`. | 2026-05-11 15:57 | ❌ | — |
| Let's Do This<!--lets_do_this--> | `letsdothis.com` | WAF confirmado: 403 direto + Scrapestack 500 + Apify 403 em todas as tentativas. | 2026-05-15 | ❌ | — |
| Road Runners | `roadrunners.run` | WAF confirmado: 403 direto + Scrapestack 429 + Apify 403 em todos os 27 estados. | — | — | — |
| Running in the USA | `runningintheusa.com` | Cloudflare WAF: 403 direto + Scrapestack 429 + Playwright bloqueado. | 2026-05-11 | ❌ | — |
| MarathonGuide | `marathonguide.com` | Retorna HTTP 200, mas busca é client-side (Elasticsearch via JS). Scraping HTML inviável sem execução completa de JS. | 2026-05-11 | ❌ | — |
| RRCA | `rrca.org/resources/races` | 404/403 em todos os endpoints testados. | 2026-05-11 | ❌ | — |

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
│       ├── *.py             # Scrapers brasileiros e internacionais
│       └── majors/          # Scrapers de grandes corridas internacionais
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
