# Fontes — Status e Limitações

> Última atualização: 2026-05-02

---

## Nota sobre WAF / Cloudflare

Muitos sites brasileiros de corridas utilizam Cloudflare ou WAF similar.
O bloqueio funciona em dois níveis distintos:

- **Nível de IP ("Host not in allowlist"):** A requisição é rejeitada antes mesmo de
  chegar ao servidor. Nem Playwright resolve — o IP do runner ainda é bloqueado.
  GoDream e Ahotu operam nesse nível.

- **Nível de fingerprint de browser (bot detection):** O servidor responde, mas exige
  JavaScript e cookies gerados por um browser real. Playwright resolve esses casos.

Os testes manuais deste documento foram feitos a partir de uma VM cloud (IP de datacenter),
que é bloqueada por muitos sites. Os números de eventos registrados no `data/corridas.json`
refletem execuções reais do GitHub Actions, cujos IPs possuem acesso mais amplo.

---

## Nota sobre Playwright

Playwright foi **removido** do `requirements.txt` numa sessão anterior com o objetivo de
corrigir uma falha no CI (a versão `1.44.0` era de 2024 e possivelmente incompatível).
A solução correta seria atualizar a versão, não remover a dependência.

A versão atual disponível é **1.59.0**.

**Playwright resolve:** sites SPA que requerem renderização JS (ex: `portal_das_corridas`).

**Playwright NÃO resolve:** bloqueio por IP ("Host not in allowlist") — GoDream, Ahotu,
e quaisquer outros sites que rejeitem IPs de datacenter independentemente do cliente HTTP.

Recomendação: **reintroduzir `playwright==1.59.0`** no `requirements.txt` e no step
`playwright install chromium` do `scrape.yml`, o que desbloquearia `portal_das_corridas`.

---

## Fontes Brasileiras — Ativas

| Fonte | Arquivo | Método | Eventos no JSON | Observações |
|---|---|---|---|---|
| Ticket Sports | `ticket_sports.py` | JSON API | **844** | Maior fonte; usa API interna do app. Retorna 403 de IPs de datacenter. |
| Circuito das Estações | `circuito_das_estacoes.py` | API dedicada | **97** | API própria do evento; estável. |
| Central da Corrida | `central_da_corrida.py` | HTML scraping | **74** | Funciona no CI; WAF bloqueia IPs de datacenter. |
| TF Sports | `tf_sports.py` | HTML scraping | **51** | Funciona no CI. |
| Live Run | `liverun.py` | HTML scraping | **44** | Funciona no CI. |
| Yescom | `yescom.py` | HTML scraping | **10** | Funciona no CI. |
| Brasil Corrida | `brasil_corrida.py` | HTML scraping | **7** | Funciona no CI. |
| Iguana Sports | `iguana_sports.py` | HTML scraping | **6** | Funciona no CI. |
| Ativo | `ativo.py` | HTML scraping | **3** | Funciona no CI. |
| MKS Esportes | `mks_esportes.py` | HTML scraping | **3** | Funciona no CI. |
| SESC DF | `sesc_df.py` | HTML scraping | **2** | Específico DF; funciona no CI. |
| Corridas Brasil | `corridas_brasil.py` | HTML scraping | — | Funciona no CI. |
| Minhas Inscrições | `minhas_inscricoes.py` | HTML scraping | — | Funciona no CI. |
| Runner Brasil | `runner_brasil.py` | HTML scraping | — | Funciona no CI. |
| Brasil que Corre | `brasil_que_corre.py` | HTML scraping | — | Específico DF; funciona no CI. |
| Correr Brasília | `correr_brasilia.py` | HTML scraping | — | Específico DF; funciona no CI. |
| GoDream | `godream.py` | HTML + Next.js | — | **Sempre 403 "Host not in allowlist"** — bloqueado em nível de IP mesmo no CI. Está registrado em SOURCES mas nunca retorna eventos. |

---

## Fontes Brasileiras — Eventos Específicos (Ativas)

| Fonte | Arquivo | Eventos no JSON |
|---|---|---|
| Maratona do Rio | `maratona_rio.py` | 1 |
| Maratona de Porto Alegre | `maratona_porto_alegre.py` | 1 |
| SP City Marathon | `sp_city_marathon.py` | 1 |
| São Silvestre | `sao_silvestre.py` | 1 |
| Volta do Lago | `volta_do_lago.py` | — |

---

## Fontes Internacionais — Ativas

| Fonte | Arquivo | Eventos | Método |
|---|---|---|---|
| Let's Do This | `lets_do_this.py` | — | HTML scraping — calendário UK |
| World Marathons | `world_marathons.py` | — | HTML scraping — calendário mundial |

---

## World Marathon Majors — Ativos (22 scrapers)

Todos usam o helper `scrape_major()` de `majors/_base.py`. Retornam 1–2 edições futuras
(ano atual + próximo), com projeção automática para +1 ano se todas as datas conhecidas
já passaram.

| Evento | Arquivo | Datas conhecidas |
|---|---|---|
| Tokyo Marathon | `tokyo.py` | 2027-03-07 |
| Boston Marathon | `boston.py` | 2027-04-19 |
| Paris Marathon | `paris.py` | 2027-04-11 |
| Brighton Marathon | `brighton.py` | 2027-04-04 |
| TCS London Marathon | `london.py` | 2027-04-25 |
| Prague Marathon | `prague.py` | 2026-05-03 · 2027-05-09 |
| Copenhagen Marathon | `copenhagen.py` | 2026-05-17 · 2027-05-16 |
| Edinburgh Marathon | `edinburgh.py` | 2026-05-24 · 2027-05-30 |
| Stockholm Marathon | `stockholm.py` | 2026-05-30 · 2027-05-30 |
| TCS Sydney Marathon | `sydney.py` | 2026-08-30 · 2027-08-29 |
| Great North Run | `great_north_run.py` | 2026-09-06 · 2027-09-12 |
| BMW Berlin Marathon | `berlin.py` | 2026-09-27 · 2027-09-26 |
| Cardiff Half Marathon | `cardiff_half.py` | 2026-10-04 · 2027-10-03 |
| Manchester Half Marathon | `manchester_half.py` | 2026-10-04 · 2027-10-03 |
| Manchester Marathon | `manchester.py` | 2027-04-18 |
| Bank of America Chicago Marathon | `chicago.py` | 2026-10-11 · 2027-10-10 |
| Amsterdam Marathon | `amsterdam.py` | 2026-10-18 · 2027-10-17 |
| Venice Marathon | `venice.py` | 2026-10-25 · 2027-10-24 |
| Dublin City Marathon | `dublin.py` | 2026-10-25 · 2027-10-31 |
| TCS New York City Marathon | `nyc.py` | 2026-11-01 · 2027-11-07 |
| Athens Classic Marathon | `athens.py` | 2026-11-08 · 2027-11-14 |
| Valencia Marathon | `valencia.py` | 2026-12-06 · 2027-12-05 |

---

## Fontes com Arquivo mas Desativadas (não em SOURCES)

### `corridas_br.py` — Desativado intencionalmente

- **Site:** corridasbr.com.br
- **Motivo:** Agrega eventos de outras fontes sem links de inscrição reais. Os ~37 eventos
  DF que apareciam exclusivamente nessa fonte (incluindo Circuito das Estações) foram
  substituídos por fontes com dados mais completos.
- **Status atual:** Retorna `403` mesmo no CI.

### `bora_correr.py` — Nunca ativado

- **Site:** coelhodeprograma.com.br/boracorrer
- **Motivo:** Arquivo existe, está exportado em `sources/__init__.py`, mas nunca foi
  adicionado ao SOURCES em `main.py`. Retorna `403` no CI.

### `portal_das_corridas.py` — Requer Playwright

- **Site:** portaldascorridas.com.br
- **Motivo:** SPA que exige renderização JavaScript. O scraper já usa Playwright
  (`sync_playwright`) com fallback gracioso (`return []` se Playwright não estiver
  instalado). Com Playwright no `requirements.txt`, funcionaria.
- **Status atual:** Playwright removido do projeto → sempre retorna `[]`.
- **Ação recomendada:** Reintroduzir `playwright==1.59.0` e ativar esta fonte.

---

## Fontes Testadas e Inviáveis

### GoDream — `godream.py` (em SOURCES, sempre falha)

- **Site:** godream.com.br
- **Testado em:** 2026-05-02
- **Resultado:** `403 "Host not in allowlist"` em todos os endpoints, incluindo
  `/corrida-de-rua`, `/api/events`, sitemap e robots.txt.
- **Diagnóstico:** WAF bloqueia IPs de datacenter/cloud em nível de rede.
  Playwright não resolve (bloqueio é por IP, não por fingerprint de browser).
- **Workaround possível:** IP residencial/proxy, ou chave de API fornecida pelo GoDream.

### Ahotu

- **Site:** ahotu.com
- **Testado em:** 2026-05-02
- **Resultado:** `403 "Host not in allowlist"` em todos os endpoints.
- **Diagnóstico:** Mesmo WAF do GoDream. Arquivo de scraper nunca criado.
- **Workaround possível:** Idem GoDream.
