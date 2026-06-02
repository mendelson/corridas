# Corridas — Calendário Global de Corridas de Rua

Agregador multilíngue (pt/en/es/de/fr) de corridas de rua em todo o mundo.
Cobre eventos brasileiros (todas as regiões), latino-americanos, norte-americanos,
britânicos, europeus continentais (Alemanha, França, Itália, Espanha, Holanda etc.),
asiáticos (Tóquio) e oceânicos (Sydney), incluindo todas as World Marathon Majors.
Eventos encontrados em múltiplas fontes são consolidados em um único registro.
Atualizado automaticamente a cada 6 horas via GitHub Actions.

**App:** [mendelson.github.io/corridas](https://mendelson.github.io/corridas) ·
**Stack:** Python (httpx + BeautifulSoup4 + Playwright) · JSON · HTML/CSS/JS puro · GitHub Pages

---

## Fontes ativas

### Fontes brasileiras — calendários gerais

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Ticket Sports<!--ticket_sports--> | ✅ | `ticketsports.app/api/events/list` | JSON API | 2026-05-31 00:16 | ❌ 88/932 eventos sem distâncias | 2026-05-30 22:34 |
| Circuito das Estações<!--circuito_das_estacoes--> | ✅ | `hotsites.nortemkt.com/api/events/circuito-das-estacoes` | JSON API dedicada | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Central da Corrida<!--central_da_corrida--> | ✅ | `centraldacorrida.com.br/calendario` | Supabase edge-function API | 2026-05-31 17:52 | ✅ | 2026-05-31 17:52 |
| TF Sports<!--tf_sports--> | ✅ | `painel-website.tfsports.com.br/api` + `tfsports.com.br` | Strapi v4 API + token do bundle Next.js | 2026-05-31 00:19 | ❌ 0 eventos | 2026-05-30 03:29 |
| Yescom<!--yescom--> | ✅ | `yescom.com.br` | HTML (homepage + páginas de evento) | 2026-05-31 00:17 | ❌ 3/13 eventos sem distâncias | 2026-05-30 22:32 |
| Atletis<!--atletis--> | ✅ | `atletis.com.br/events/coordinates` | GeoJSON + JSON-LD por evento | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Brasil Corrida<!--brasil_corrida--> | ✅ | `brasilcorrida.com.br/api/src/Site` | JSON API | 2026-06-01 12:48 | ❌ | 2026-05-30 22:32 |
| Iguana Sports<!--iguana_sports--> | ✅ | `iguanasports.com.br/blogs/calendario-corridas-de-rua` | HTML (blog de calendário) | 2026-05-31 00:16 | ❌ 2/8 eventos sem distâncias | 2026-05-30 22:31 |
| Ativo<!--ativo--> | ✅ | `ativo.com/eventos.json` | JSON API | 2026-05-31 00:17 | ❌ 6/9 eventos sem distâncias | 2026-05-30 22:31 |
| MKS Esportes<!--mks_esportes--> | ✅ | `mksesportes.com.br` (sitemap + HTML) | HTML | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Corridas Brasil<!--corridas_brasil--> | ✅ | `corridasbrasil.com.br/calendario/` | HTML | 2026-06-01 13:00 | ✅ | 2026-06-01 13:00 |
| Minhas Inscrições<!--minhas_inscricoes--> | ✅ | `minhasinscricoes.com.br/pt-br/calendario?url=corrida-de-rua` | HTML | 2026-05-31 00:18 | ✅ | 2026-05-31 00:18 |
| Runner Brasil<!--runner_brasil--> | ✅ | `runnerbrasil.com.br` | HTML | 2026-05-31 18:26 | ❌ 0 eventos | 2026-05-30 03:28 |
| Largada Esportiva<!--largada_esportiva--> | ✅ | `largadaesportiva.com.br` | Playwright (intercepção de JSON) + HTML | 2026-05-31 13:20 | ✅ | 2026-05-31 13:20 |
| Portal das Corridas<!--portal_das_corridas--> | ✅ | `portaldascorridas.com.br/event-pages-sitemap.xml` | Wix sitemap + páginas individuais (JSON-LD) | 2026-05-31 00:18 | ❌ 15/67 eventos sem distâncias | 2026-05-30 22:34 |

### Fontes brasileiras — específicas Brasília-DF

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Correr Brasília<!--correr_brasilia--> | ✅ | `correrbrasilia.com.br/calendario/` | HTML | 2026-05-31 00:17 | ❌ 26/63 eventos sem distâncias | 2026-05-30 22:32 |
| Bora Correr<!--bora_correr--> | ✅ | `coelhodeprograma.com.br/boracorrer` | HTML (tabela #tabDados) | 2026-06-01 14:09 | ✅ | 2026-06-01 14:09 |
| Brasil que Corre<!--brasil_que_corre--> | ✅ | `brasilquecorre.com/distritofederal` | HTML (cs-text-widget) | 2026-05-31 00:17 | ❌ 0 eventos | 2026-05-30 03:27 |
| SESC DF<!--sesc_df--> | ✅ | `sescdf.com.br/corridas` | HTML | 2026-05-31 00:17 | ❌ 0 eventos | 2026-05-30 03:28 |
| Corrida POUPEX<!--poupex--> | ✅ | `corrida.poupex.com.br` | HTML (OG tags) | — | — | — |

### Fontes brasileiras — eventos específicos

| Fonte | Em uso | URL de busca | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Maratona do Rio<!--maratona_rio--> | ✅ | `maratonadorio.com.br` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Maratona de Porto Alegre<!--maratona_porto_alegre--> | ✅ | `maratonadeportoalegre.com.br` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| SP City Marathon<!--sp_city_marathon--> | ✅ | `iguanasports.com.br/products/sp-city-marathon-{ano}` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| São Silvestre<!--sao_silvestre--> | ✅ | `saosilvestre.com.br` | 2026-05-31 00:16 | ❌ 0 eventos | 2026-05-30 03:28 |
| Volta do Lago<!--volta_do_lago--> | ✅ | `largadaesportiva.com.br/api/Events` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |

### Fontes mexicanas

| Fonte | Em uso | URL de busca | Observação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Asdeporte<!--asdeporte--> | ✅ | `asdeporte.com/eventos` | Next.js; extrai `pageProps.recomended` do `__NEXT_DATA__`; ~30 eventos/run | 2026-06-01 13:59 | ✅ | 2026-06-01 13:59 |

### Fontes internacionais — plataformas agregadoras

| Fonte | Em uso | URL de busca | Observação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| HalfMarathons.net<!--halfmarathons--> | ✅ | `halfmarathons.net/wp-json/wp/v2/races` | WordPress REST API paginada (EUA); distâncias em milhas como string | 2026-05-31 14:41 | ✅ | 2026-05-31 14:41 |
| RunSignup<!--runsignup--> | ✅ | `runsignup.com/Rest/races` | REST API paginada (EUA/global); distâncias em milhas preservadas como string | 2026-05-31 00:19 | ✅ | 2026-05-31 00:19 |
| World Athletics<!--world_athletics--> | ✅ | `worldathletics.org/competitions/world-athletics-label-road-races` | HTML público; `__NEXT_DATA__`; provas com Label IAAF (Platinum/Gold/Silver/Bronze) | 2026-05-31 18:35 | ❌ 0 eventos | 2026-05-30 03:27 |
| Race Roster<!--raceroster--> | ✅ | `search.raceroster.com/search` | REST API pública; paginada por termo de busca; distâncias parseadas de strings como `42km`/`3mi` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |

---

## Grandes corridas internacionais

22 scrapers dedicados em `scraper/sources/majors/`. Cada um retorna 1–2 edições futuras;
quando todas as datas conhecidas já passaram, o scraper aguarda o anúncio da próxima edição.

Os 7 marcados com ⭐ são os **Abbott World Marathon Majors** (as "Six Majors" + Sydney).
Os demais são grandes provas internacionais de destaque mas não pertencem ao grupo WMM.

| Evento | ⭐ WMM | Em uso | URL oficial | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Tokyo Marathon<!--majors/tokyo--> | ⭐ | ✅ | `marathon.tokyo/en` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Boston Marathon<!--majors/boston--> | ⭐ | ✅ | `baa.org/races/boston-marathon` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| TCS London Marathon<!--majors/london--> | ⭐ | ✅ | `tcslondonmarathon.com` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| BMW Berlin Marathon<!--majors/berlin--> | ⭐ | ✅ | `bmw-berlin-marathon.com/en` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Bank of America Chicago Marathon<!--majors/chicago--> | ⭐ | ✅ | `chicagomarathon.com` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| TCS New York City Marathon<!--majors/nyc--> | ⭐ | ✅ | `nyrr.org/races/tcsnycmarathon` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| TCS Sydney Marathon<!--majors/sydney--> | ⭐ | ✅ | `tcssydneymarathon.com` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Schneider Electric Paris Marathon<!--majors/paris--> |  | ✅ | `schneiderelectricparismarathon.com/en` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Brighton Marathon<!--majors/brighton--> |  | ✅ | `londonmarathonevents.co.uk/brighton-marathon-weekend` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Volkswagen Prague Marathon<!--majors/prague--> |  | ✅ | `runczech.com/en/races/volkswagen-prague-marathon` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Copenhagen Marathon<!--majors/copenhagen--> |  | ✅ | `copenhagenmarathon.dk/en` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Edinburgh Marathon Festival<!--majors/edinburgh--> |  | ✅ | `edinburghmarathon.com` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Stockholm Marathon<!--majors/stockholm--> |  | ✅ | `stockholmmarathon.se/eng` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Manchester Marathon<!--majors/manchester--> |  | ✅ | `manchestermarathon.co.uk` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Great North Run<!--majors/great_north_run--> |  | ✅ | `greatrun.org/events/great-north-run` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Cardiff Half Marathon<!--majors/cardiff_half--> |  | ✅ | `cardiffhalfmarathon.co.uk` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Manchester Half Marathon<!--majors/manchester_half--> |  | ✅ | `manchesterhalfmarathon.com` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| TCS Amsterdam Marathon<!--majors/amsterdam--> |  | ✅ | `tcsamsterdammarathon.nl/en` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Venice Marathon<!--majors/venice--> |  | ✅ | `venicemarathon.it/en` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |
| Dublin City Marathon<!--majors/dublin--> |  | ✅ | `irishlifedublinmarathon.ie` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Athens Classic Marathon<!--majors/athens--> |  | ✅ | `athensauthenticmarathon.gr/en` | 2026-05-31 00:17 | ✅ | 2026-05-31 00:17 |
| Valencia Trinidad Alfonso Marathon<!--majors/valencia--> |  | ✅ | `valenciaciudaddelrunning.com/en/marathon` | 2026-05-31 00:16 | ✅ | 2026-05-31 00:16 |

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
| Sympla | ❌ | `sympla.com.br/busca?q=corrida` | URL de busca retorna HTTP 404; Playwright redireciona para página de login. | 2026-05-11 15:57 | ❌ | — |

## Fontes testadas e inviáveis

| Fonte | URL | Motivo | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Corridas BR<!--corridas_br--> | `corridasbr.com.br/df/calendario.asp` | **NÃO REATIVAR.** Agregador de baixa qualidade — informações frequentemente erradas, sem links de inscrição reais (apenas redireciona para outras fontes). Mesmo se voltasse a responder com 200, os dados são pouco confiáveis. Permanentemente removido. | 2026-05-22 19:17 | ❌ | — |
| Ahotu | `ahotu.com/pt-br/races` | WAF bloqueia IPs de datacenter em nível de rede. Playwright não resolve. | — | — | — |
| Finishers | `finishers.com/pt-br/races?country=BR` | Mesmo bloqueio que Ahotu. | — | — | — |
| FMAA<!--fmaa--> | `fmaa.apps-mexico.com/wp-json/tribe/events/v1/events` | (1) WAF: 403 em todos os domínios FMAA (`fmaa.apps-mexico.com`, `fmaa.mx`); domínios secundários (`fmaa.com.mx`, `fmaa.planin.mx`) fora do ar. (2) Escopo incompatível: federação de atletismo competitivo (campeonatos nacionais sub-18/sub-20, pista, cross country), não corridas de participação em massa. Corridas mexicanas de público geral cobertas pelo Asdeporte. | 2026-05-21 20:50 | ❌ | — |
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
