# Corridas — Calendário Global de Corridas de Rua

Agregador multilíngue (pt/en/es/de/fr) de corridas de rua em todo o mundo.
Cobre eventos brasileiros (todas as regiões), latino-americanos, norte-americanos,
britânicos, europeus continentais (Alemanha, França, Itália, Espanha, Holanda etc.),
asiáticos (Tóquio) e oceânicos (Sydney), incluindo todas as World Marathon Majors.
Eventos encontrados em múltiplas fontes são consolidados em um único registro.
Atualizado automaticamente a cada 6 horas via GitHub Actions.

**App:** [mendelson.github.io/corridas](https://mendelson.github.io/corridas) ·
**Stack:** Python (httpx + BeautifulSoup4 + Playwright) · JSON · HTML/CSS/JS puro · GitHub Pages

📍 **Mapa do site e rotas:** [`docs/site-map.md`](docs/site-map.md) — domínio, caminhos públicos e assets de `run.mmendelson.com`.

---

## Fontes ativas

### Fontes brasileiras — calendários gerais

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Ticket Sports<!--ticket_sports--> | ✅ | `ticketsports.app/api/events/list` | JSON API | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 839 ev |
| Circuito das Estações<!--circuito_das_estacoes--> | ✅ | `hotsites.nortemkt.com/api/events/circuito-das-estacoes` | JSON API dedicada | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 13 ev |
| Central da Corrida<!--central_da_corrida--> | ✅ | `centraldacorrida.com.br/calendario` | Supabase edge-function API | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 55 ev |
| TF Sports<!--tf_sports--> | ✅ | `painel-website.tfsports.com.br/api` + `tfsports.com.br` | Strapi v4 API + token do bundle Next.js | 2026-07-05 11:09 | ✅ | 2026-07-05 11:09 · 70 ev |
| Yescom<!--yescom--> | ✅ | `yescom.com.br` | HTML (homepage + páginas de evento) | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 7 ev |
| Atletis<!--atletis--> | ✅ | `atletis.com.br/events/coordinates` | GeoJSON + JSON-LD por evento | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 15 ev |
| Brasil Corrida<!--brasil_corrida--> | ✅ | `brasilcorrida.com.br/api/src/Site` | JSON API | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 13 ev |
| Iguana Sports<!--iguana_sports--> | ✅ | `iguanasports.com.br/blogs/calendario-corridas-de-rua` | HTML (blog de calendário) | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 4 ev |
| Ativo<!--ativo--> | ✅ | `ativo.com/eventos.json` | JSON API | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 4 ev |
| MKS Esportes<!--mks_esportes--> | ✅ | `mksesportes.com.br` (sitemap + HTML) | HTML | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Corridas Brasil<!--corridas_brasil--> | ✅ | `corridasbrasil.com.br/calendario/` | HTML | 2026-07-05 11:15 | ✅ | 2026-07-05 11:15 · 939 ev |
| Minhas Inscrições<!--minhas_inscricoes--> | ✅ | `minhasinscricoes.com.br/pt-br/calendario?url=corrida-de-rua` | HTML | 2026-07-05 11:06 | ✅ | 2026-07-05 11:06 · 144 ev |
| Runner Brasil<!--runner_brasil--> | ✅ | `runnerbrasil.com.br` | HTML | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 2 ev |
| Largada Esportiva<!--largada_esportiva--> | ✅ | `largadaesportiva.com.br` | Playwright (intercepção de JSON) + HTML | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 1 ev |
| Portal das Corridas<!--portal_das_corridas--> | ✅ | `portaldascorridas.com.br/event-pages-sitemap.xml` | Wix sitemap + páginas individuais (JSON-LD) | 2026-07-05 11:05 | ✅ | 2026-07-05 11:05 · 58 ev |

### Fontes brasileiras — específicas Brasília-DF

| Fonte | Em uso | URL de busca | Método | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Conta Passos<!--conta_passos--> | ✅ | `contapassos.com.br` | RSC payload da home (Next.js) | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 5 ev |
| Correr Brasília<!--correr_brasilia--> | ✅ | `correrbrasilia.com.br/calendario/` | HTML | 2026-07-05 11:04 | ⚠️ 0 eventos (2/3) | 2026-07-03 11:28 · 60 ev |
| Bora Correr<!--bora_correr--> | ✅ | `coelhodeprograma.com.br/boracorrer` | HTML (tabela #tabDados) | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 6 ev |
| Brasil que Corre<!--brasil_que_corre--> | ✅ | `brasilquecorre.com/distritofederal` | HTML (cs-text-widget) | 2026-07-05 11:06 | ✅ | 2026-07-05 11:06 · 3 ev |
| SESC DF<!--sesc_df--> | ✅ | `sescdf.com.br/corridas` | HTML | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 1 ev |

### Fontes brasileiras — eventos específicos

| Fonte | Em uso | URL de busca | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Maratona do Rio<!--maratona_rio--> | ✅ | `maratonadorio.com.br` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Maratona de Porto Alegre<!--maratona_porto_alegre--> | ✅ | `maratonadeportoalegre.com.br` | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 1 ev |
| SP City Marathon<!--sp_city_marathon--> | ✅ | `iguanasports.com.br/products/sp-city-marathon-{ano}` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| São Silvestre<!--evento_unico/sao_silvestre--> | ✅ | `saosilvestre.com.br` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 0 ev |
| Volta do Lago<!--volta_do_lago--> | ✅ | `largadaesportiva.com.br/api/Events` | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 1 ev |

### Fontes mexicanas

| Fonte | Em uso | URL de busca | Observação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Asdeporte<!--asdeporte--> | ✅ | `asdeporte.com/eventos` | Next.js; extrai `pageProps.recomended` do `__NEXT_DATA__`; ~30 eventos/run | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 27 ev |

### Fontes internacionais — plataformas agregadoras

| Fonte | Em uso | URL de busca | Observação | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| HalfMarathons.net<!--halfmarathons--> | ✅ | `halfmarathons.net/wp-json/wp/v2/races` | WordPress REST API paginada (EUA); distâncias em milhas como string | 2026-07-05 11:03 | ⚠️ 0 eventos (1/3) | 2026-07-04 10:54 · 1890 ev |
| RunSignup<!--runsignup--> | ✅ | `runsignup.com/Rest/races` | REST API paginada (EUA/global); distâncias em milhas preservadas como string | 2026-07-05 11:07 | ✅ | 2026-07-05 11:07 · 10833 ev |
| World Athletics<!--world_athletics--> | ✅ | `worldathletics.org/competitions/world-athletics-label-road-races` | HTML público; `__NEXT_DATA__`; provas com Label IAAF (Platinum/Gold/Silver/Bronze) | 2026-06-05 12:00 | ⚠️ 0 eventos (0/3) | 2026-05-30 03:27 |
| Race Roster<!--raceroster--> | ✅ | `search.raceroster.com/search` | REST API pública; paginada por termo de busca; distâncias parseadas de strings como `42km`/`3mi` | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 624 ev |
| Finishers<!--finishers--> | ✅ | `*.typesense.net/multi_search` (coleção `races`) | Typesense público (chave search-only do bundle JS); `raceDiscipline:=road` global; horário enriquecido da página `/event/{slug}` com cache persistente | 2026-07-05 11:05 | ✅ | 2026-07-05 11:05 · 163 ev |

---

## Grandes corridas internacionais

Scrapers de evento único dedicados, em `scraper/sources/evento_unico/` (a São Silvestre
usa o mesmo scaffold mas está listada acima, nas fontes brasileiras). Cada um retorna 1–2
edições futuras; quando todas as datas conhecidas já passaram, o scraper aguarda o anúncio
da próxima edição.

Os 7 marcados com ⭐ são os **Abbott World Marathon Majors** (as "Six Majors" + Sydney).
Os demais são grandes provas internacionais de destaque mas não pertencem ao grupo WMM.

| Evento | ⭐ WMM | Em uso | URL oficial | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Tokyo Marathon<!--evento_unico/tokyo--> | ⭐ | ✅ | `marathon.tokyo/en` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Boston Marathon<!--evento_unico/boston--> | ⭐ | ✅ | `baa.org/races/boston-marathon` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| TCS London Marathon<!--evento_unico/london--> | ⭐ | ✅ | `tcslondonmarathon.com` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| BMW Berlin Marathon<!--evento_unico/berlin--> | ⭐ | ✅ | `bmw-berlin-marathon.com/en` | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 1 ev |
| Bank of America Chicago Marathon<!--evento_unico/chicago--> | ⭐ | ✅ | `chicagomarathon.com` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 1 ev |
| TCS New York City Marathon<!--evento_unico/nyc--> | ⭐ | ✅ | `nyrr.org/races/tcsnycmarathon` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| TCS Sydney Marathon<!--evento_unico/sydney--> | ⭐ | ✅ | `tcssydneymarathon.com` | 2026-07-05 11:04 | ✅ | 2026-07-05 11:04 · 1 ev |
| Schneider Electric Paris Marathon<!--evento_unico/paris--> |  | ✅ | `schneiderelectricparismarathon.com/en` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 1 ev |
| Brighton Marathon<!--evento_unico/brighton--> |  | ✅ | `londonmarathonevents.co.uk/brighton-marathon-weekend` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 1 ev |
| Volkswagen Prague Marathon<!--evento_unico/prague--> |  | ✅ | `runczech.com/en/races/volkswagen-prague-marathon` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 0 ev |
| Copenhagen Marathon<!--evento_unico/copenhagen--> |  | ✅ | `copenhagenmarathon.dk/en` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Edinburgh Marathon Festival<!--evento_unico/edinburgh--> |  | ✅ | `edinburghmarathon.com` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Stockholm Marathon<!--evento_unico/stockholm--> |  | ✅ | `stockholmmarathon.se/eng` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 0 ev |
| Manchester Marathon<!--evento_unico/manchester--> |  | ✅ | `manchestermarathon.co.uk` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 2 ev |
| Great North Run<!--evento_unico/great_north_run--> |  | ✅ | `greatrun.org/events/great-north-run` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 1 ev |
| Cardiff Half Marathon<!--evento_unico/cardiff_half--> |  | ✅ | `cardiffhalfmarathon.co.uk` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 1 ev |
| Manchester Half Marathon<!--evento_unico/manchester_half--> |  | ✅ | `manchesterhalfmarathon.com` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 2 ev |
| TCS Amsterdam Marathon<!--evento_unico/amsterdam--> |  | ✅ | `tcsamsterdammarathon.nl/en` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Venice Marathon<!--evento_unico/venice--> |  | ✅ | `venicemarathon.it/en` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Dublin City Marathon<!--evento_unico/dublin--> |  | ✅ | `irishlifedublinmarathon.ie` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 1 ev |
| Athens Classic Marathon<!--evento_unico/athens--> |  | ✅ | `athensauthenticmarathon.gr/en` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Valencia Trinidad Alfonso Marathon<!--evento_unico/valencia--> |  | ✅ | `valenciaciudaddelrunning.com/en/marathon` | 2026-07-05 11:03 | ✅ | 2026-07-05 11:03 · 1 ev |
| Comrades Marathon<!--evento_unico/comrades--> |  | ✅ | `comrades.com/race-information` | 2026-07-05 11:02 | ✅ | 2026-07-05 11:02 · 0 ev |

---

## Estratégia de acesso

Cada requisição HTTP é feita diretamente via `httpx` (`http_client.py`), com
headers de browser realista — **sem camada de proxy externo**. (Scrapestack e
Apify foram removidos em 2026-06: as chaves de trial expiraram e todo fallback
por eles retornava 429/403, só adicionando latência sem nunca obter sucesso.)

Quando a requisição direta recebe um status de WAF (403/406/429), o `get()`
lança exceção e o scraper da fonte cai para **Playwright headless** com
configurações básicas anti-detecção (desativa `navigator.webdriver`, simula
`window.chrome`). Isso funciona para alguns WAFs, mas não para Cloudflare em
modo estrito.

Os scrapers de grandes corridas internacionais (`evento_unico/`) têm fallback adicional: quando o HTTP falha, retornam o evento com a data conhecida (`known_date`) em vez de retornar zero resultados.

Buscas de fotos (`fotos.py`) usam `get_direct()`, que não lança exceção em status de WAF — para essas buscas opcionais de imagem.

---

## Fontes desativadas

| Fonte | Em uso | URL | Motivo | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- | --- |
| Sympla | ❌ | `sympla.com.br/busca?q=corrida` | URL de busca retorna HTTP 404; Playwright redireciona para página de login. | 2026-05-11 15:57 | ❌ | — |

## Fontes testadas e inviáveis

| Fonte | URL | Motivo | Testado em | Status | Últ. sucesso |
| --- | --- | --- | --- | --- | --- |
| Corridas BR<!--corridas_br--> | `corridasbr.com.br/df/calendario.asp` | **NÃO REATIVAR.** Agregador de baixa qualidade — informações frequentemente erradas, sem links de inscrição reais (apenas redireciona para outras fontes). Mesmo se voltasse a responder com 200, os dados são pouco confiáveis. Permanentemente removido. | 2026-05-22 19:17 | ❌ | — |
| Ahotu | `ahotu.com` | Cloudflare Managed Challenge bloqueia IPs de datacenter. Reconfirmado no CI (GitHub Actions): `httpx` direto retorna 403 com a página "Just a moment…" (`challenges.cloudflare.com`) em todos os caminhos de conteúdo (`/calendar/running`, `/sitemap/events.xml.gz`, `/api/`); o Playwright do projeto renderiza o interstício ("Um momento…") mas **não resolve o desafio** (0 links de evento, sem `__NEXT_DATA__`). Só `robots.txt` e o `sitemap.xml` índice passam, e não carregam dados de evento. Conteúdo da Ahotu já é coberto indiretamente por `worldsmarathons` (mesmo grupo, sem WAF). | 2026-07-03 | ❌ | — |
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
│   ├── http_client.py       # GET direto (httpx); WAF → exceção → Playwright
│   ├── playwright_client.py # Playwright headless com evasão básica de bot-detection
│   ├── fotos.py             # Busca de fotos em plataformas (desativada temporariamente)
│   └── sources/
│       ├── *.py             # Scrapers brasileiros e internacionais
│       └── evento_unico/          # Scrapers de grandes corridas internacionais
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
