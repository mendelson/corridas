# World Athletics (`world_athletics.py`) — research notes

**Status:** DESATIVADA em 2026-06-04 (não removida — o módulo `.py` permanece para retomada).
**Motivo:** o horário de largada (campo obrigatório) é indisponível em qualquer fonte
pública do World Athletics, e as páginas de competição individuais retornam HTTP 404
no formato de URL que o scraper consegue construir.

---

## O que a fonte é

Página pública Next.js SSR das *World Athletics Label Road Races*:

```
https://worldathletics.org/competitions/world-athletics-label-road-races
```

O `__NEXT_DATA__` da página embute `props.pageProps.calendarEvents.results` — uma
lista de objetos `CalendarEvent`. Na sondagem de 2026-06-03: **275 competições**, das
quais **140 futuras** (a partir de hoje), distribuídas em selos
`Label (79) / Elite (33) / Gold (19) / Platinum (9)`.

### Campos de um `CalendarEvent` (sondado)

```
__typename, id, iaafId, hasResults, hasStartlist, hasApiResults,
hasCompetitionInformation, disciplines, rankingCategory, competitionSubgroup,
undeterminedCompetitionPeriod, name, venue, country, startDate, endDate,
dateRange, countryCode, venueWithoutCountry
```

Exemplo:

```json
{
  "id": 7236068,
  "name": "40. OPTIMA Dreikönigslauf in Schwäbisch Hall",
  "startDate": "2026-01-06",          // SOMENTE data — nunca hora
  "endDate": "2026-01-06",
  "competitionSubgroup": "Label",
  "rankingCategory": "E",
  "venue": "Schwäbisch Hall (GER)",
  "country": "GER",
  "countryCode": "GER",
  "venueWithoutCountry": "Schwäbisch Hall ",
  "hasCompetitionInformation": true
}
```

**`startDate` é date-only (`YYYY-MM-DD`).** Não existe nenhum campo de horário
(`startTime`, `time`, `startDateTime`, …) em `CalendarEvent`. O horário precisaria vir
da página de competição individual de cada evento.

---

## Por que está quebrada — a página de competição individual retorna 404

O scraper monta a URL do evento como:

```
https://worldathletics.org/competitions/road-running/{name-slug}-{calendarEventId}
```

e tenta extrair o horário dela (`_fetch_horario`). **Essa URL retorna 404.** Sondado
em 2026-06-03 via Playwright (render JS completo):

```
GET .../competitions/road-running/mastercard-new-york-mini-10k-women-s-race-7241746/competition-information
→ __NEXT_DATA__.props.pageProps:
    competition = null
    statusCode  = 404
    apolloState.ROOT_QUERY['getWawCompetition({"urlSlug":"road-running"})'] = null
```

Ou seja, o roteamento Next.js da WA usa um **slug interno (`urlSlug`)** que **não é**
derivável do nome nem do `CalendarEvent.id`. A query GraphQL interna
(`getWawCompetition`) recebeu `urlSlug="road-running"` (o segmento errado da URL) e
devolveu `null`.

### A página de competição usa um ID diferente (WAWEvent), que não temos

O `apolloState` da própria página de label races contém apenas **1** objeto
`WAWEvent` (`WAWEvent:8453`, o evento em destaque) — e ele vem **vazio** (`{}`).

Existe também `props.pageProps.schedules` (3106 entradas `ScheduleType`), cada uma com:

```json
{"countryId":"ALB","eventId":"8583","eventId_WA":"7206650"}
```

onde `eventId_WA` = `CalendarEvent.id` e `eventId` = **WAWEvent ID interno** (o ID que
a URL de competição realmente precisa). **Porém esse mapeamento cobre apenas 21
CalendarEvent IDs, e NENHUM deles está entre os 275 da lista de label races** (e zero
dos 140 futuros). O `schedules` é o cronograma de TV/transmissão de outra competição
em destaque, não o índice das label races.

Conclusão: a partir da página pública de label races **não há como obter o WAWEvent ID
necessário** para montar a URL da página de competição da maioria dos eventos — e sem
essa página não há horário.

---

## URLs sondadas (2026-06-03)

| URL | Resultado |
|---|---|
| `/competitions/world-athletics-label-road-races` | 200 — 275 CalendarEvents, sem horário |
| `/competitions/road-running/{slug}-{calEventId}/competition-information` | **404** (`competition: null`) |
| `/competition/calendar-results/results/{calEventId}` | 200 — SSR de **resultados** (eventos passados), sem horário de largada futura |

---

## Caminhos ainda não esgotados (pontos de partida para retomar)

1. **Descobrir o slug/`urlSlug` correto da página de competição.** A página de label
   races pode ter, em algum nível do `__NEXT_DATA__` ou via uma chamada GraphQL
   secundária, o `urlSlug` ou o WAWEvent ID de cada `CalendarEvent`. Vale dumpar o
   `apolloState` completo e `pageProps` inteiros e procurar por `nameUrlSlug`,
   `urlSlug`, `wawId`, `eventId` casando com cada `CalendarEvent.id`.
2. **Endpoint GraphQL `getWawCompetition`.** Se for possível chamá-lo diretamente com
   o `urlSlug` certo (ou por `CalendarEvent.id`), a resposta provavelmente traz o
   horário. Requer descobrir o endpoint, headers e se há credencial rotativa (a WA
   historicamente embute chaves rotativas no bundle JS — ver nota no CLAUDE.md).
3. **Fonte de horário alternativa por evento.** Muitos desses eventos são majors/
   label races grandes com site próprio (ex.: Houston, Valencia, Xiamen). Um
   enriquecimento de horário via OG/JSON-LD do site oficial — como `majors/_base.py`
   faz — poderia preencher o campo, mas exigiria um mapeamento nome→site por evento.

## Por que NÃO foi simplesmente "dropada"

Não há evidência de bloqueio WAF: a página principal responde 200 e entrega todos os
dados estruturados. O problema é puramente de **completude de campo obrigatório
(horário)**, não de acessibilidade. Por isso a fonte fica **desativada** (módulo
preservado), não removida — a lista de 140 corridas de elite futuras é valiosa e a
reativação depende apenas de encontrar o horário (caminhos 1–3 acima).
