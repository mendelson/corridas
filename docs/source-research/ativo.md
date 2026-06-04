# Ativo (`ativo.py`) — research notes

**Status:** ATIVA. Bug de distâncias (e horário) corrigido em 2026-06-04.

---

## Arquitetura da fonte

`ativo.com` é um site **WordPress**. A listagem vem de um JSON público:

```
GET https://www.ativo.com/eventos.json     # ~2500 eventos
```

Cada item da listagem traz `post_title`, `ds_tipo_evento`, `ds_cidade`,
`ds_estado`, `dt_evento`, `id_evento`, `post_json` (URL do `index.json` do evento)
e `thumbnail`. **Mas:**

- `dt_evento` é sempre `'YYYY-MM-DD 00:00:00'` — **meia-noite placeholder**, nunca o
  horário real de largada.
- `distancias` vem **vazio** (`[]`) na maioria dos eventos.
- O `index.json` por evento (`post_json`) tem **exatamente os mesmos dados** da
  listagem — `distancias: []` e `dt_evento` à meia-noite. **É inútil** para
  distâncias e horário (sondado em 2026-06-04: `circuito-de-corridas-vale-sao-luis`
  → 903 bytes, `distancias: []`, `dt_evento: '2026-06-21 00:00:00'`).

## Onde os dados reais estão: a página HTML do evento

A página HTML do evento (`post_json` sem `/index.json`) **não** tem `__NEXT_DATA__`
nem JSON embutido — mas tem *info cards* server-rendered com os valores
autoritativos:

```html
<h3 class="info-title">Distâncias</h3>
  <p>Corrida 5K, Corrida 10K, Família 1km</p>
<h3 class="info-title">Horários</h3>
  <p>5 e 10km - Largada às 5h30<br>Família 1km - Largada às 7h30.</p>
```

E *route cards* por percurso:

```html
<p class="route-distance">Percurso <span>Corrida 5K</span></p>
<p class="route-start">Largada <span> às 5h30</span></p>
```

## Bug corrigido (2026-06-04)

### Sintoma

Fonte retornava 0 (ou poucos) eventos — descartados por falta de **distâncias**
(e/ou horário).

### Causa raiz

Uma sessão anterior já tinha adicionado a busca de **horário** na página HTML
(`_fetch_horario_from_page`), mas as **distâncias** ainda eram buscadas no
`index.json` (sempre vazio) → fallback para distâncias do título → para eventos sem
km no título (ex.: "Circuito de Corridas Vale - São Luís"), distâncias ficavam `[]`
e o evento era descartado.

### Correção

Consolidado num único `_fetch_event_html(url)` que busca a **página HTML uma só vez**
e extrai:

1. **Distâncias** do *info card* "Distâncias" (`<h3 class="info-title">Distâncias</h3>
   <p>…</p>`) e dos *route cards* (`p.route-distance span`). Parsing
   (`_parse_distance_text`) trata listas por token ("5K, 10K") **e** sufixo `km`
   compartilhado ("5 e 10km"), descarta < 3 km (caminhadas/kids) e faz
   *canonical-snap* de 21/42.
2. **Horário** via varredura por palavra-chave ("Largada às 5h30" → `05:30`).

Isto também **reduz o tráfego**: antes eram 2 fetches por evento (index.json +
página HTML para horário); agora é **1** (a página HTML cobre ambos). O `index.json`
deixou de ser buscado por ser comprovadamente inútil.

### Validação (local, sem rede, contra o HTML real)

```
Distâncias card "Corrida 5K, Corrida 10K, Família 1km" → [5.0, 10.0]  ✓ (1km família excluído)
Horários card   "5 e 10km - Largada às 5h30"           → 05:30        ✓
```

## Notas

- `scrape()` parsa eventos em paralelo (`ThreadPoolExecutor`, 10 workers); cada
  `_parse_event` faz no máximo 1 fetch HTML.
- Filtros mantidos: `_RUNNING_TYPES`, `fl_suspenso`, data futura.
- Sem horário **ou** sem distâncias após o fetch → evento descartado (campos
  obrigatórios).
