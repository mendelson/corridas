# Carreras México (`carreras_mexico.py`) — research notes

**Status:** ATIVA. Bug de horário/localização corrigido em 2026-06-04.

---

## Arquitetura da fonte

`carrerasmexico.com` embute um **widget Tiempometa**. O scraper chama a API do
widget diretamente:

```
GET https://www.tiempometa.com/api3/js_site/events
    ?api_key=48513987f33edea8        # público, embutido no div do widget
    &page=<N>&page_size=50
    &target_url=https://carrerasmexico.com/
```

A resposta é JavaScript que embrulha HTML num `.html('…')`. O scraper desfaz o
embrulho (`_extract_html`) e parseia os `.tm_event_list_item`. Daí saem **título,
data e imagem** — mas **não** o horário nem a localização estruturada.

Horário e cidade/UF vêm da **página de convocatória** de cada evento:

```
GET https://carrerasmexico.com/convocatoria.php?event=<hex>&api_key=48513987f33edea8
```

---

## Bug corrigido (2026-06-04): convocatória atrás de desafio anti-bot

### Sintoma

A fonte retornava **0 eventos** — todos descartados por falta de horário (campo
obrigatório).

### Causa raiz

`convocatoria.php` está atrás de um **desafio anti-bot baseado em JavaScript**.
A resposta inicial é **HTTP 200** com uma página "Um momento, por favor…" que faz
`setTimeout(() => location.reload(), 5000)` e só serve o conteúdo real depois que o
navegador passa nas verificações de propriedades (`navigator.webdriver`, dimensões
da janela, protótipos de plugin/mimeType, idioma, etc.).

O código já tinha um fallback para Playwright, **mas a condição estava errada**:

```python
if resp.status_code < 400:      # ← o desafio responde 200!
    html = resp.text            #   então html = página de desafio (sem dados)
# ...                           #   e o Playwright NUNCA era acionado
```

Como o desafio devolve 200, `html` era preenchido com a página de desafio (sem
`SportsEvent` JSON-LD), o extrator não achava nada, e o Playwright — que passaria
no desafio — nunca rodava.

### Correção

1. **Só aceitar a resposta do proxy se ela contiver o schema real**
   (`resp.status_code < 400 and "SportsEvent" in resp.text`); caso contrário, cair
   para o Playwright. Sondado em 2026-06-04: o Playwright (stealth do
   `playwright_client.py`) **passa no desafio** e devolve o HTML real (≈112 KB).

2. **Horário vem da prosa, não do JSON-LD.** O `startDate` do JSON-LD é um
   *placeholder* à meia-noite (`2026-06-06T00:00:00-06:00`). O horário real está no
   corpo da página:

   > "FECHA : 7 de junio de 2026, **9:30 hrs**. SALIDA Y META"

   O extrator já tinha varredura por palavra-chave (`salida`/`inicio`/`largada`/
   `hrs`) do texto visível — agora ela recebe o HTML real e funciona.
   Validado: `22va. Sky Race La Malinche` → `09:30`.

3. **Normalização de UF Tiempometa → ISO-3166-2.** A localização do JSON-LD vem como
   `"Centro Vacacional Malintzi, TLX"`. `TLX` **não** é um código MX válido — o ISO
   de Tlaxcala é `TLA`. Adicionado `_NORMALIZE_UF` cobrindo as divergências conhecidas
   (`TLX→TLA`, `DIF/CDMX→CMX`, `AGS→AGU`, `DGO→DUR`, `GTO→GUA`, `HGO→HID`,
   `QRO→QUE`, `QROO→ROO`, `NL→NLE`, `BC→BCN`, …). Toda UF é então **validada contra
   `web/locations/MX.json`** via `_geo.validate_estado`; se inválida, faz-se
   `_geo.resolve(cidade)`. Um código desconhecido nunca chega aos dados como UF
   inválida.

4. **Emissão só de eventos completos.** `scrape()` agora descarta eventos sem
   `horario`, sem `cidade` ou com UF inválida — em vez de armazená-los inválidos.

### Validação (local, sem rede)

```
_state_to_code('TLX')  → 'TLA'  validate('MX','TLA')='TLA'   ✓
_state_to_code('QROO') → 'ROO'  validate='ROO'               ✓
_state_to_code('XX')   → 'XX'   validate=''  (→ geo / drop)   ✓
HTML real La Malinche  → ('Centro Vacacional Malintzi','TLA','09:30')  ✓
```

---

## Custo / cuidado

- Toda a lista do Tiempometa **não** traz horário, então **todo** evento exige uma
  busca de convocatória. Quando o proxy entrega só o desafio, cada uma vira um
  lançamento de Playwright (`ThreadPoolExecutor`, 3 workers). O carrerasmexico nunca
  lista mais que algumas dezenas de eventos, então o custo é limitado, mas é o
  trecho mais pesado da fonte.
- A API do widget (`/api3/js_site/events`) é pública e estável; `event_search`
  retorna 500 (quebrado upstream) — não usar.
