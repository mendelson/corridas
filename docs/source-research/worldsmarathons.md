# World's Marathons (`worldsmarathons.com`) — research notes

**Status:** VIÁVEL (sondado 2026-06-05). Implementação pendente. Fonte
internacional (maratonas/eventos no mundo todo). `tipo` provável =
`"calendario"` (diretório agregador; inscrição via parceiros/`offers`).

## Por que é viável (sondagem)

`worldsmarathons.com` é um **diretório global de maratonas** server-rendered
(Angular `ng-app="wmPub"`), acessível por `httpx` direto (HTTP 200, sem WAF),
com `robots.txt` liberando e sitemaps. **Todos os campos obrigatórios estão em
campos estruturados** (não no título):

| Campo | Origem (estruturada) |
|---|---|
| título | JSON-LD `Event.name` |
| **data** | JSON-LD `Event.startDate` (date-only, ex. `2026-11-01`) |
| **horário** | blob embutido `"local_start_time":"09:00"` (ou `"start_time"`) ← o campo que faltou no World Athletics **existe aqui** |
| **local** | JSON-LD `Event.location.Place` → `addressLocality` / `addressCountry` (ISO-2, ex. `TR`) |
| **distâncias** | blob `raceDistances:[{"distance":42195.0,"distanceStr":"42.20km","raceName":"Marathon","type":"full_marathon"}, …]` — distância em **metros** num campo |
| imagem | JSON-LD `Event.image[0]` (CDN `wmimg.azureedge.net`) |

Exemplo Istanbul:
`Event.startDate=2026-11-01`, `local_start_time=09:00`, `addressCountry=TR`,
`raceDistances` → 42195m (Marathon) + 15500m (15.5k).

## Descoberta (enumeração)

```
robots.txt → index-sitemap-en.xml  (sitemapindex)
           → marathons-sitemap-en.xml   ← lista as URLs /marathon/<slug>
```
(Atenção: é `marathons-sitemap` com "s". `marathon-sitemap` sem "s" devolve a
página de calendário em HTML, não o sitemap.)

## Plano de implementação

1. Fetch `https://worldsmarathons.com/marathons-sitemap-en.xml` → extrair os
   `<loc>` `/marathon/<slug>`.
2. Para cada evento: fetch a página, extrair:
   - JSON-LD `<script type="application/ld+json">` com `@type:"Event"` →
     name, startDate (data), location (cidade/país ISO-2), image.
   - `local_start_time`/`start_time` (regex no blob) → **horário** HH:MM.
   - `raceDistances` (regex/JSON) → distâncias: metros → km
     (42195→42.195, 21097→21.097, 15500→15.5, 10000→10.0, 5000→5.0);
     snap canônico p/ 42.195/21.097.
   - país: `addressCountry` ISO-2 → mapear p/ `web/locations/{pais}.json`;
     `estado`/subdivisão via `geo.resolve(cidade, "", pais)` quando houver.
3. Filtrar futuros (`startDate >= hoje`) e exigir horário + distância + local.
4. `id` estável a partir do slug (`wm_<slug>`). Link = a própria página.

## Custo / cuidado

- Cada página de evento é **grande (~865 KB)**. Se o sitemap tiver muitos
  milhares de URLs, buscar todas por run é caro. Mitigar: usar `<lastmod>` do
  sitemap p/ priorizar recentes e/ou cap por run; o filtro de data do pipeline
  descarta passados de qualquer forma. Avaliar tamanho do `marathons-sitemap`
  antes de buscar tudo.
- Não existe `__NEXT_DATA__`/`__NUXT__`; os dados estão em JSON-LD + um blob
  JSON embutido (objeto grande da maratona). Extrair JSON-LD é trivial;
  `local_start_time`/`raceDistances` saem por regex ancorada no blob.
- `/api/marathons` devolve HTML (não é a API) — não usar.
