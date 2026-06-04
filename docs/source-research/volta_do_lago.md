# volta_do_lago — Notas de Pesquisa

**Módulo:** `scraper/sources/volta_do_lago.py`  
**Status:** Desativado em 2026-06-04 (fontes de dados esgotadas)  
**Evento coberto:** 20ª Volta do Lago Paranoá (Brasília, DF)

---

## Arquitetura original

O scraper tinha duas fontes independentes:

1. **Largada Esportiva REST API** (`https://largadaesportiva.com.br/api/Events`) — fonte primária
2. **Ticket Sports API** (`https://www.ticketsports.app/api/events/list`) — fallback

E o site oficial do evento (`https://www.voltadolago.com.br`) era uma SPA JS que não poderia ser scrapeada diretamente.

---

## Resultado das sondagens (2026-06-04)

### 1. Largada Esportiva REST API

Todas as variantes da API LE retornaram timeout ou erro:

| URL | Resultado |
|-----|-----------|
| `https://largadaesportiva.com.br/api/Events` | Timeout |
| `https://largadaesportiva.com.br/api/events` | Timeout |
| `https://largadaesportiva.com.br/api/Events?name=volta` | Timeout |
| `https://largadaesportiva.com.br/api/events/13` | Timeout |

A API da LE retornou timeout consistentemente, mesmo via Scrapestack e Apify.

**Nota:** O evento **ID `le_13`** aparece nos dados do `largada_esportiva.py` (que usa Playwright para interceptar chamadas de rede na página web da LE). Este scraper captura a "20ª Volta do Lago Paranoá" com sucesso via a interface web da LE.

### 2. voltadolago.com.br (site oficial)

`https://www.voltadolago.com.br` e `https://voltadolago.com.br` retornaram timeout em todas as tentativas (direct, Scrapestack, Apify).

O site oficial do evento está inacessível da infraestrutura de CI.

### 3. Ticket Sports API

`https://www.ticketsports.app/api/events/list?quantity=50&atlheteId=0&term=volta+lago` retornou uma lista vazia `[]`. Pesquisas com `"volta do lago"` e `"lago paranoa"` também retornaram `[]`.

---

## Decisão

**Fonte desativada** (não removida) pois:

1. Todas as 3 fontes de dados estão esgotadas do ponto de vista do CI
2. O evento já é capturado adequadamente pelo `largada_esportiva.py` (evento `le_13`), que usa Playwright para navegar na interface web da LE e interceptar as chamadas de API
3. Não há bloqueio WAF — os timeouts são infraestrutura (LE API não responde, voltadolago.com.br não responde para IPs de datacenter)

O módulo `volta_do_lago.py` é preservado para referência e possível reativação futura.

---

## Caminhos não esgotados (para retomar)

Se a LE API eventualmente voltar a responder, ou se o voltadolago.com.br ficar acessível:

1. **Abordagem Playwright na LE** (como `largada_esportiva.py`): usar `page.on("response", _on_response)` para interceptar JSON da API de eventos enquanto navega em `https://largadaesportiva.com.br/eventos` ou similar. O evento `le_13` já existe nos dados.

2. **voltadolago.com.br com Playwright**: se o site oficial voltar a responder, usar Playwright + `wait_until="networkidle"` + extração de JSON embutido ou JSON-LD.

3. **Ticket Sports** direct fetch: a API pode estar respondendo com dados diferentes dependendo da região/token. Investigar se há endpoint alternativo com autenticação.

---

## ID estável no scraper atual

O evento é identificado como `le_13` no `largada_esportiva.py`. O ID `volta-do-lago_df_2026` seria o ID gerado por `volta_do_lago.py` se estivesse ativo.
