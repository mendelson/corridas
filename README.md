# Corridas BR

Agrega e exibe corridas de rua no Brasil — com foco em Brasília-DF, nas principais
maratonas nacionais e nos World Marathon Majors. Eventos encontrados em múltiplas fontes
são consolidados em um único registro. Atualizado automaticamente a cada 4 horas via
GitHub Actions.

**App:** [mendelson.github.io/corridas](https://mendelson.github.io/corridas) ·
**Stack:** Python (httpx + BeautifulSoup4 + Playwright) · JSON · HTML/CSS/JS puro · GitHub Pages

---

## Fontes

### Nota sobre WAF / Cloudflare

Muitos sites de corridas utilizam Cloudflare ou WAF similar. O bloqueio opera em dois
níveis distintos:

- **Nível de IP ("Host not in allowlist"):** A requisição é rejeitada antes de chegar ao
  servidor. Playwright não resolve — o IP do runner ainda é bloqueado. GoDream e Ahotu
  operam nesse nível.
- **Nível de fingerprint de browser (bot detection):** O servidor responde, mas requer
  JavaScript e cookies de um browser real. Playwright resolve esses casos.

---

### Fontes Brasileiras — Ativas

| Fonte | Método | Eventos | Observações |
|---|---|---|---|
| Ticket Sports | JSON API | **~844** | Maior fonte; usa API interna do app. |
| Circuito das Estações | API dedicada | **~97** | API própria do evento; estável. |
| Central da Corrida | HTML | **~74** | |
| TF Sports | HTML | **~51** | |
| Live Run | HTML | **~44** | |
| Yescom | HTML | **~10** | |
| Brasil Corrida | HTML | **~7** | |
| Iguana Sports | HTML | **~6** | |
| Ativo | HTML | **~3** | |
| MKS Esportes | HTML | **~3** | |
| SESC DF | HTML | **~2** | Específico DF. |
| Corridas Brasil | HTML | — | |
| Minhas Inscrições | HTML | — | |
| Runner Brasil | HTML | — | |
| Brasil que Corre | HTML | — | Específico DF. |
| Correr Brasília | HTML | — | Específico DF. |
| Portal das Corridas | Playwright | — | SPA; requer renderização JS. |
| GoDream | HTML + Next.js | — | **Sempre bloqueado (IP-level WAF).** Registrado mas nunca retorna eventos. |

### Fontes Brasileiras — Eventos Específicos

| Fonte | Site |
|---|---|
| Maratona do Rio | maratona.rio |
| Maratona de Porto Alegre | maratonadeportoalegre.com.br |
| SP City Marathon | spcitymarathon.com.br |
| São Silvestre | saosilvestre.com.br |
| Volta do Lago | voltadolago.com.br |

### Fontes Internacionais

| Fonte | Cobertura |
|---|---|
| Let's Do This | Calendário UK |
| World Marathons | Calendário mundial |

### World Marathon Majors (22 scrapers dedicados)

Cada evento tem scraper próprio em `scraper/sources/majors/`. Retornam 1–2 edições futuras
com projeção automática para o ano seguinte quando todas as datas conhecidas já passaram.

| Evento | Próximas edições |
|---|---|
| Tokyo Marathon | 2027-03-07 |
| Boston Marathon | 2027-04-19 |
| Brighton Marathon | 2027-04-04 |
| Paris Marathon | 2027-04-11 |
| TCS London Marathon | 2027-04-25 |
| Manchester Marathon | 2027-04-18 |
| Prague Marathon | 2026-05-03 · 2027-05-09 |
| Copenhagen Marathon | 2026-05-17 · 2027-05-16 |
| Edinburgh Marathon Festival | 2026-05-24 · 2027-05-30 |
| Stockholm Marathon | 2026-05-30 · 2027-05-30 |
| TCS Sydney Marathon | 2026-08-30 · 2027-08-29 |
| Great North Run | 2026-09-06 · 2027-09-12 |
| BMW Berlin Marathon | 2026-09-27 · 2027-09-26 |
| Cardiff Half Marathon | 2026-10-04 · 2027-10-03 |
| Manchester Half Marathon | 2026-10-04 · 2027-10-03 |
| Bank of America Chicago Marathon | 2026-10-11 · 2027-10-10 |
| Amsterdam Marathon | 2026-10-18 · 2027-10-17 |
| Venice Marathon | 2026-10-25 · 2027-10-24 |
| Dublin City Marathon | 2026-10-25 · 2027-10-31 |
| TCS New York City Marathon | 2026-11-01 · 2027-11-07 |
| Athens Classic Marathon | 2026-11-08 · 2027-11-14 |
| Valencia Marathon | 2026-12-06 · 2027-12-05 |

---

## Fontes Desativadas

| Fonte | Arquivo | Motivo |
|---|---|---|
| Corridas BR | `corridas_br.py` | Agrega eventos de outras fontes sem links de inscrição reais. Retorna 403 no CI. |
| Bora Correr | `bora_correr.py` | Arquivo existe mas nunca foi ativado. Retorna 403 no CI. |

## Fontes Testadas e Inviáveis

| Fonte | Motivo |
|---|---|
| **Ahotu** (ahotu.com) | `403 "Host not in allowlist"` em todos os endpoints. WAF bloqueia IPs de datacenter em nível de rede. Playwright não resolve. |

---

## Estrutura

```
corridas/
├── .github/workflows/
│   ├── scrape.yml          # CI: roda a cada 4h, commita JSON atualizado
│   └── debug-scraper.yml   # Workflow manual para debug de fonte individual
├── scraper/
│   ├── main.py             # Orquestrador: executa scrapers, merge, persistência
│   ├── models.py           # Dataclasses: Corrida, Distancia, FonteInfo, etc.
│   ├── merger.py           # Deduplicação e merge entre fontes
│   ├── utils.py            # Normalização de datas, strings, slugify, cidade→estado
│   ├── http_client.py      # httpx com headers de browser
│   └── sources/
│       ├── *.py            # Scrapers brasileiros
│       └── majors/         # Scrapers dos World Marathon Majors
├── data/
│   └── corridas.json       # Base acumulativa (versionada no repo)
└── web/
    ├── index.html          # Redirect para /pt ou /en conforme idioma do browser
    ├── pt/ en/ es/ de/ fr/ # Páginas por idioma
    ├── app.js              # Lógica do app (filtros, cards, i18n)
    ├── style.css
    └── manifest.json       # PWA
```
