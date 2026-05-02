# REQUIREMENTS — Corridas BR

> Documento de requisitos otimizado para construção autônoma por Claude Code.

---

## 1. Visão Geral

**Objetivo**: Agregar e exibir corridas de rua no Brasil — com foco em Brasília-DF, nas principais maratonas nacionais e nos World Marathon Majors — coletadas automaticamente de múltiplas fontes, acessíveis via PWA mobile-first. Eventos encontrados em múltiplas fontes são mesclados em um único registro consolidado. A interface oferece filtros rápidos por distância, intervalo de datas e estado.

**Stack**:
- Scraper: Python 3.11+ (httpx + BeautifulSoup4)
- Dados: `data/corridas.json` (acumulativo, versionado no repo)
- Frontend: HTML/CSS/JS puro (sem framework), multi-idioma (PT/EN/ES/DE/FR)
- Automação: GitHub Actions (cron a cada 4h)
- Hospedagem: GitHub Pages

**Repositório**: `github.com/mendelson/corridas`
**Branch de deploy**: `gh-pages`

---

## 2. Estrutura de Pastas

```
corridas/
├── .github/
│   └── workflows/
│       └── scrape.yml
├── scraper/
│   ├── main.py                 # Orchestrator: executa scrapers, merge, persistência, serializa
│   ├── models.py               # Dataclasses: Corrida, Distancia, Inscricao, FonteInfo, PeriodoInscricao
│   ├── merger.py               # Deduplicação e merge entre fontes
│   ├── utils.py                # Normalização de datas, strings, slugify, cidade→estado
│   └── sources/
│       ├── __init__.py
│       ├── central_da_corrida.py
│       ├── ticket_sports.py
│       ├── minhas_inscricoes.py
│       ├── brasil_que_corre.py
│       ├── corridas_brasil.py
│       ├── correr_brasilia.py
│       ├── corridas_br.py
│       ├── bora_correr.py
│       ├── brasil_corrida.py
│       ├── portal_das_corridas.py
│       ├── runner_brasil.py
│       ├── liverun.py
│       ├── tf_sports.py
│       ├── sesc_df.py
│       └── majors/
│           ├── __init__.py
│           ├── tokyo.py
│           ├── boston.py
│           ├── london.py
│           ├── berlin.py
│           ├── chicago.py
│           ├── nyc.py
│           └── sydney.py
├── data/
│   └── corridas.json
├── web/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── manifest.json
│   └── service-worker.js
├── requirements.txt
└── README.md
```

---

## 3. Modelo de Dados

### 3.1 Dataclass `FonteInfo`

```python
@dataclass
class FonteInfo:
    nome: str
    link_evento: str
    links_inscricao: list[str]
    inscricoes: list[Inscricao]
```

### 3.2 Dataclass `PeriodoInscricao`

```python
@dataclass
class PeriodoInscricao:
    abertura: str | None      # ISO 8601 — data de abertura das inscrições
    encerramento: str | None  # ISO 8601 — data de encerramento das inscrições
```

### 3.3 Dataclass `Distancia`

```python
@dataclass
class Distancia:
    km: float | str    # 5.0, 10.0, 21.0, 42.0, "Infantil"
    data: str | None   # ISO 8601 — se diferente da data principal do evento
    horario: str | None
```

### 3.4 Dataclass `Inscricao`

```python
@dataclass
class Inscricao:
    descricao: str
    valor: float | None
    disponivel: bool
    link: str | None
```

### 3.5 Dataclass `Corrida`

```python
@dataclass
class Corrida:
    id: str                          # slugify(titulo) + "_" + estado + "_" + first_seen_at[:10]
                                     # Exemplo: "corrida-do-cerrado_df_2025-05-10"
                                     # Estável: não muda se data ou horário do evento forem alterados
    titulo: str
    data_evento: str                 # ISO 8601: "2025-08-10" — pode ser atualizado
    horario: str | None              # "07:00" — pode ser atualizado
    localizacao: str
    cidade: str                      # Ex: "Brasília"
    estado: str                      # Sigla UF: "DF", "SP", "RJ", "INT" etc.
    distancias: list[Distancia]
    imagem_url: str | None
    inscricoes_abertas: bool | None  # True=abertas, False=encerradas, None=desconhecido
    periodo_inscricao: PeriodoInscricao | None
    fontes: list[FonteInfo]
    miss_count: int                  # Nº de execuções consecutivas em que o evento não foi encontrado
    first_seen_at: str               # ISO 8601 — imutável após criação
    updated_at: str                  # ISO 8601 — atualizado sempre que qualquer campo muda
```

### 3.6 Schema JSON (`data/corridas.json`)

```json
{
  "gerado_em": "2025-07-15T06:30:00-03:00",
  "total": 56,
  "corridas": [
    {
      "id": "corrida-do-cerrado_df_2025-05-10",
      "titulo": "Corrida do Cerrado",
      "data_evento": "2025-08-10",
      "horario": "07:00",
      "localizacao": "Parque da Cidade, Brasília-DF",
      "cidade": "Brasília",
      "estado": "DF",
      "distancias": [
        { "km": 5.0, "data": null, "horario": null },
        { "km": 10.0, "data": null, "horario": "07:30" }
      ],
      "imagem_url": "https://...",
      "inscricoes_abertas": true,
      "periodo_inscricao": {
        "abertura": "2025-05-01",
        "encerramento": "2025-08-05"
      },
      "fontes": [
        {
          "nome": "Central da Corrida",
          "link_evento": "https://centraldacorrida.com.br/...",
          "links_inscricao": ["https://..."],
          "inscricoes": [
            { "descricao": "5km", "valor": 89.90, "disponivel": true, "link": "https://..." }
          ]
        },
        {
          "nome": "Ticket Sports",
          "link_evento": "https://ticketsports.com.br/...",
          "links_inscricao": ["https://..."],
          "inscricoes": []
        }
      ],
      "miss_count": 0,
      "first_seen_at": "2025-05-10T06:30:00-03:00",
      "updated_at": "2025-07-15T06:30:00-03:00"
    }
  ]
}
```

**Regras do JSON:**
- Ordenado por `data_evento` crescente (eventos passados incluídos)
- Eventos passados são preservados indefinidamente — o filtro de data padrão no frontend os oculta

---

## 4. Deduplicação e Merge (`merger.py`)

### 4.1 Princípio Central

> **Similaridade de título é o único sinal confiável de duplicata.** Data e horário idênticos são insuficientes: é comum que múltiplos eventos distintos ocorram no mesmo dia. Data e horário servem apenas como critério de desempate quando a similaridade de título é alta mas não conclusiva.

### 4.2 Identificação de Duplicatas

Dois registros recém-scrapeados (da mesma rodada) são considerados o **mesmo evento** se satisfizerem **todos** os critérios abaixo:

**Critério 1 — Título (obrigatório e primário):**
- Similaridade ≥ 85% via `difflib.SequenceMatcher` após normalização
- Normalização: lowercase → `unidecode` → remover pontuação → remover stop words (`"corrida"`, `"run"`, `"race"`, `"maratona"`, `"meia"`, `"de"`, `"da"`, `"do"`, `"em"`)
- Exemplos que **passam**: "Corrida do Cerrado 2025" × "Corrida Cerrado" → ~88%
- Exemplos que **não passam**: "Corrida do Parque" × "Corrida do Cerrado" → ~55%

**Critério 2 — Estado (obrigatório):**
- `estado` deve ser idêntico
- Impede merge entre "Corrida Cidade" de SP com "Corrida Cidade" de MG

**Critério 3 — Data (tolerância):**
- `data_evento` deve estar dentro de uma janela de ±14 dias entre os dois registros
- Justificativa: eventos às vezes têm datas ligeiramente divergentes entre fontes, ou uma fonte demora a atualizar após remarcação
- Se ambos os registros têm data null → passa (evento sem data confirmada)
- Se apenas um tem data → passa (o outro ainda não publicou a data)

### 4.3 Casos de Borda

| Situação | Comportamento |
|---|---|
| Título ≥ 85%, mesmo estado, datas divergem > 14 dias | **Não merge** — tratar como eventos distintos |
| Título ≥ 85%, estados diferentes | **Não merge** — são eventos em cidades diferentes |
| Título < 85%, mesma data e estado | **Não merge** — coincidência de data, eventos distintos |
| Título ≥ 95%, mesmo estado, datas divergem ≤ 30 dias | **Merge** — alta confiança de ser o mesmo evento remarcado |
| Major vs. corrida brasileira de mesmo nome | **Não merge** — `estado: "INT"` nunca faz merge com UF brasileira |

### 4.4 Algoritmo de Merge (rodada única de scraping)

```
função merge_rodada(registros: list[Corrida]) -> list[Corrida]:
    1. Normalizar títulos de todos os registros
    2. Para cada par (A, B) não ainda agrupado:
       a. Se critérios 4.2 satisfeitos → são duplicatas
    3. Para cada grupo de duplicatas:
       a. Eleger campeão = registro com maior score de completude (ver 4.5)
       b. corrida_final = cópia do campeão
       c. Para cada fonte adicional no grupo:
          - Append FonteInfo em corrida_final.fontes
          - Se imagem_url ausente no campeão → copiar da fonte adicional
          - Mesclar distancias: union por valor de km, sem duplicatas
          - Se inscricoes_abertas null no campeão e não-null na fonte → copiar
          - Se periodo_inscricao null no campeão e não-null na fonte → copiar
       d. Deduplicar links_inscricao por URL exata dentro de cada FonteInfo
    4. Retornar lista sem duplicatas
```

### 4.5 Score de Completude (eleger campeão)

```python
def score(c: Corrida) -> int:
    return (
        bool(c.titulo) * 2 +
        bool(c.data_evento) * 2 +
        bool(c.horario) +
        bool(c.localizacao) +
        bool(c.imagem_url) * 2 +
        len(c.distancias) +
        bool(c.inscricoes_abertas is not None) +
        bool(c.periodo_inscricao) +
        bool(c.periodo_inscricao and c.periodo_inscricao.encerramento) +
        len(c.fontes[0].inscricoes) * 2 +
        len(c.fontes[0].links_inscricao)
    )
```

---

## 5. Scraper

### 5.1 Comportamento Geral e Persistência

- Cada `sources/*.py` expõe `scrape() -> list[Corrida]`
- `main.py` executa todos em paralelo (ThreadPoolExecutor), consolida via `merger.py`, então aplica a lógica de persistência abaixo
- Falha em uma fonte não interrompe o processo — log de erro em stdout (visível no GitHub Actions) e continua
- Timeout por fonte: 30s
- User-Agent: Chrome mais recente

**Fluxo de persistência em `main.py`:**

```
1. Carregar corridas.json existente → dict {id: Corrida}  [estado_anterior]
2. Executar todos os scrapers → list[Corrida]
3. Rodar merger.merge_rodada() → list[Corrida]            [estado_atual]
4. Reconciliar estado_anterior com estado_atual:

   Para cada corrida em estado_atual:
     a. Calcular id candidato: slugify(titulo) + "_" + estado + "_" + hoje
     b. Buscar match em estado_anterior por id OU por similaridade de título
        (mesmo critério da seção 4.2 — para detectar evento já cadastrado com data diferente)
     c. Se match encontrado:
        - Atualizar campos que mudaram: data_evento, horario, localizacao,
          distancias, imagem_url, inscricoes_abertas, periodo_inscricao, fontes
        - Preservar id e first_seen_at originais
        - Atualizar updated_at = agora se qualquer campo mudou
        - Resetar miss_count = 0
     d. Se sem match → inserir como novo:
        - id = slugify(titulo) + "_" + estado + "_" + hoje
        - first_seen_at = agora, updated_at = agora, miss_count = 0

   Para cada corrida em estado_anterior NÃO encontrada em estado_atual:
     a. Se data_evento < hoje → manter como está (evento passado, encerrado)
     b. Se data_evento >= hoje → incrementar miss_count
        - Se miss_count >= 3 → remover do JSON (provavelmente cancelado/removido das fontes)
        - Se miss_count < 3 → manter (pode ser falha temporária da fonte)

5. Serializar JSON completo ordenado por data_evento crescente
```

**Nota sobre `miss_count`:** este campo é de controle interno do scraper. É incluído no JSON para transparência, mas o frontend não o exibe.

### 5.2 Escopo Geográfico

O scraper coleta **três conjuntos** de dados:

**A) Corridas de Brasília-DF** — via fontes da seção 5.4, filtradas por localização:
- `localizacao` ou título contém: "Brasília", "DF", "Distrito Federal", "Plano Piloto", "Taguatinga", "Ceilândia", "Sobradinho", "Gama", "Samambaia", "Águas Claras", "Guará"
- Fontes específicas de BSB (Correr Brasília, SESC DF) aceitas sem filtro geográfico

**B) Principais maratonas do Brasil** — busca ativa por nome nas fontes genéricas:

| Evento | Estado |
|---|---|
| Maratona de São Paulo | SP |
| Maratona do Rio de Janeiro | RJ |
| Maratona de Porto Alegre | RS |
| Maratona de Florianópolis | SC |
| Maratona de Curitiba | PR |
| Maratona de Belo Horizonte | MG |
| Maratona de Fortaleza | CE |
| Maratona de Salvador | BA |
| Maratona de Recife | PE |
| Maratona de Manaus | AM |
| Maratona CAIXA de São Paulo | SP |
| Maratona de Brasília | DF |

> Se uma maratona não for encontrada em nenhuma fonte, **não criar registro** — omitir e logar.

**C) World Marathon Majors** — scrapers dedicados por evento (`sources/majors/`):

| Evento | Estado | Site oficial | URL de inscrição |
|---|---|---|---|
| Tokyo Marathon | INT | `marathon.tokyo/en` | `marathon.tokyo/en/participants/` |
| Boston Marathon | INT | `baa.org` | `baa.org/races/boston-marathon/` |
| TCS London Marathon | INT | `tcslondonmarathon.com` | `tcslondonmarathon.com/enter/` |
| BMW Berlin Marathon | INT | `bmw-berlin-marathon.com` | `bmw-berlin-marathon.com/en/register/` |
| Bank of America Chicago Marathon | INT | `chicagomarathon.com` | `chicagomarathon.com/register/` |
| TCS New York City Marathon | INT | `nyrr.org` | `nyrr.org/races/tcsnycmarathon` |
| TCS Sydney Marathon | INT | `tcssydneymarathon.com.au` | `tcssydneymarathon.com.au/enter/` |

- `cidade` = nome da cidade + país (ex: "Tóquio, Japão")
- Majors sempre geram registro, mesmo com inscrições encerradas
- Majors nunca fazem merge com eventos brasileiros (`estado: "INT"` ≠ qualquer UF)

### 5.3 Extração de `estado`

Prioridade:
1. Campo explícito na fonte (ex: "Estado: SP")
2. Inferência pelo campo `localizacao` via dicionário de cidades → UF
3. Fontes específicas de BSB → sempre `"DF"`
4. Majors → sempre `"INT"`
5. Se não determinável → `"??"` (fallback; o registro é mantido)

### 5.4 Estratégia por Fonte (Brasília + Maratonas BR)

| Fonte | Método | Observação |
|---|---|---|
| Central da Corrida | BeautifulSoup | Filtrar por estado DF + busca maratonas |
| Ticket Sports | httpx + BS4 | API interna |
| Minhas Inscrições | BeautifulSoup | URL já filtrada |
| Brasil que Corre | BeautifulSoup | URL já filtrada por DF |
| Corridas Brasil | BeautifulSoup | Filtrar calendário |
| Correr Brasília | BeautifulSoup | Específico de BSB |
| Corridas BR | BeautifulSoup | URL já filtrada por DF |
| Bora Correr | BeautifulSoup | — |
| Brasil Corrida | BeautifulSoup | — |
| Portal das Corridas | httpx + BS4 | — |
| Runner Brasil | BeautifulSoup | — |
| LiveRun | BeautifulSoup | — |
| TF Sports | BeautifulSoup | — |
| SESC DF | BeautifulSoup | Específico de BSB |

### 5.5 Normalização

- Datas: "DD/MM/YYYY", "DD de mês de YYYY", "YYYY-MM-DD" → ISO 8601
- Distâncias: "5K", "5 km", "5 quilômetros" → `5.0`
- Valores: remover "R$", vírgulas → `float`
- Títulos: strip, title case, remover emojis
- Estado: sempre sigla maiúscula de 2 letras ou `"INT"`

---

## 6. Frontend (PWA Mobile-First)

### 6.1 Filtros

Os filtros ficam fixos no topo da tela (sticky), sempre visíveis. São **3 controles independentes**, aplicados simultaneamente em tempo real.

**Persistência:** filtros de distância e estado são salvos em `localStorage`. O filtro de período **não é persistido** — inicia sempre em "A partir de hoje" a cada abertura do app.

**Contador:** "12 corridas encontradas" — atualizado em tempo real. Botão "Limpar filtros" aparece quando qualquer filtro está ativo.

---

#### 6.1.1 Filtro de Distância

Opera em **dois modos**, trocados por toggle:

```
[● Selecionar]  [  Intervalo  ]
```

**Modo Seleção (padrão):**
- Pills: `5K` · `10K` · `21K` · `42K` · `Outras`
- Multi-select: múltiplas pills ativas simultaneamente
- Lógica OR: evento passa se qualquer distância sua corresponde a qualquer pill ativa
- "Outras" captura km não listados nas outras pills (3K, 7K, 50K, 100K etc.)
- Nenhuma pill ativa = sem filtro de distância

**Modo Intervalo:**
- Dois inputs numéricos: `De: __ km` / `Até: __ km`
- Ambos opcionais (só mínimo, só máximo, ou ambos)
- Evento passa se qualquer distância sua cai dentro do intervalo

Ao trocar de modo, os valores do modo anterior são resetados.

---

#### 6.1.2 Filtro de Período

| Opção | Comportamento |
|---|---|
| **A partir de hoje** *(padrão, não persistido)* | `data_evento >= hoje` |
| Próximos 30 dias | `hoje <= data_evento <= hoje+30` |
| Próximos 3 meses | `hoje <= data_evento <= hoje+90` |
| Próximos 6 meses | `hoje <= data_evento <= hoje+180` |
| Todo o período | Sem filtro de data (inclui passados) |
| Intervalo customizado | Dois date pickers: `De` / `Até` |

---

#### 6.1.3 Filtro de Estado

Dropdown populado dinamicamente a partir dos estados presentes no JSON.

Opções fixas no topo: `Todos` · `Internacionais`
Demais opções: siglas UF em ordem alfabética conforme aparecem no JSON.

---

### 6.2 Conteúdo do Card

**Colapsado:**
- Imagem de capa (fallback: placeholder com cor derivada do estado)
- Título
- Data e horário em PT-BR ("Sáb, 10 de ago • 07h00")
- Cidade · Estado
- Pills de distâncias (`5K` `10K` `21K`)
- Badge de status de inscrição (tabela abaixo)
- Badge "N fontes" se > 1 fonte

**Badge de status — lógica de derivação:**

| Condição | Badge |
|---|---|
| `data_evento < hoje` | 🏁 Realizado |
| `inscricoes_abertas: true` | 🟢 Inscrições abertas |
| `inscricoes_abertas: false` e evento futuro | 🔴 Inscrições encerradas |
| `inscricoes_abertas: null` e evento futuro | ⚪ Em breve |

> A condição "Realizado" tem prioridade sobre as demais.

**Expandido (adicional):**
- Tabela de distâncias com datas/horários por percurso (se houver)
- **"Período de inscrição"**: "Abertura: DD/MM/YYYY · Encerramento: DD/MM/YYYY" (se disponível)
- **"Onde se inscrever"**: cada fonte com seu `link_evento` e botões de inscrição
- **"Valores"**: tabela unificada com descrição, preço, status e link direto (de todas as fontes)

### 6.3 Layout Mobile

```
┌─────────────────────────────┐
│  🏃 Corridas BR       [↻]   │  ← header sticky
├─────────────────────────────┤
│ [5K][10K][21K][42K][Outras] │  ← distância (pills, modo Seleção)
│ [Período ▾]   [Estado ▾]   │  ← período + estado
│ 12 corridas encontradas     │
├─────────────────────────────┤
│  ┌───────────────────────┐  │
│  │ [imagem]              │  │
│  │ Título do Evento      │  │
│  │ Sáb, 10 ago • 07h00  │  │
│  │ Parque da Cidade · DF │  │
│  │ [5K][10K] · 2 fontes  │  │
│  │ 🟢 Inscrições abertas │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

### 6.4 PWA

- `web/manifest.json`: nome "Corridas BR", ícones, `display: standalone`, `theme_color: "#FF6B35"`
- `web/service-worker.js`: cache do shell (HTML/CSS/JS) offline; `corridas.json` sempre buscado da rede
- Meta tags: `viewport`, `apple-mobile-web-app-capable`, `theme-color`

### 6.5 Design

- **Tema**: dark, accent laranja (#FF6B35) — legível sob sol em tela de celular
- **Tipografia**: display bold para títulos, mono para distâncias e horários
- **Touch targets**: mínimo 44px
- **Performance**: CSS custom properties, sem JS frameworks, no máximo 1 Google Font externa
- **Acessibilidade**: contraste WCAG AA, `aria-labels` em todos os controles interativos

---

## 7. GitHub Actions (`scrape.yml`)

```yaml
name: Scrape Corridas
on:
  schedule:
    - cron: '0 9 * * *'   # 06:00 BRT (UTC-3)
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scraper
        run: python -m scraper.main

      - name: Copy JSON to web folder
        run: cp data/corridas.json web/corridas.json

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/corridas.json
          git diff --staged --quiet || git commit -m "chore: atualiza corridas $(date -u +%Y-%m-%d)"
          git push

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./web
          keep_files: false
```

> O JSON é copiado para `web/corridas.json` antes do deploy. O frontend faz `fetch('./corridas.json')` com caminho relativo.

---

## 8. Requisitos Não-Funcionais

| Atributo | Requisito |
|---|---|
| Tempo de scraping total | < 5 minutos |
| Tamanho do JSON | < 500 KB |
| First Contentful Paint (mobile 4G) | < 2s |
| Disponibilidade | 99%+ (GitHub Pages SLA) |
| Falha em fonte individual | Isolada — não bloqueia deploy |
| Desatualização máxima | 24h |
| Taxa de falso merge | < 5% (eventos distintos mesclados incorretamente) |
| Taxa de falso negativo | < 5% (mesmo evento não reconhecido como duplicata) |

---

## 9. `requirements.txt`

```
beautifulsoup4==4.12.3
httpx==0.27.0
lxml==5.2.2
python-dateutil==2.9.0
unidecode==1.3.8
```

---

## 10. Ordem de Construção Recomendada

1. `models.py` — todos os dataclasses
2. `utils.py` — normalização de datas, strings, slugify, cidade→estado
3. `merger.py` — algoritmo de deduplicação e merge (seção 4)
4. 2–3 scrapers BeautifulSoup simples para validar o pipeline end-to-end
5. `main.py` — orchestrator + lógica de persistência + serialização JSON
6. Frontend (`index.html` + `style.css` + `app.js`) com os 3 filtros
7. `manifest.json` + `service-worker.js`
8. Scrapers restantes das fontes brasileiras
10. Scrapers dos Majors (`sources/majors/`)
11. `scrape.yml` + teste end-to-end do workflow

---

## 11. Critérios de Aceite

**Scraper / Dados:**
- [ ] `python scraper/main.py` gera `data/corridas.json` válido com ≥ 1 corrida de Brasília, ≥ 1 maratona brasileira e ≥ 1 Major
- [ ] Todo registro possui `estado` preenchido (nunca campo ausente; `"??"` é valor válido de fallback)
- [ ] Mesmo evento encontrado em N fontes → 1 único registro com N entradas em `fontes[]`
- [ ] Dois eventos distintos no mesmo dia e estado não são mesclados (título diferente)
- [ ] Alteração de `data_evento` ou `horario` de evento futuro → atualiza registro existente, mantém mesmo `id` e `first_seen_at`
- [ ] Eventos passados preservados no JSON entre execuções
- [ ] Evento futuro ausente das fontes por < 3 execuções → mantido com `miss_count` incrementado
- [ ] Evento futuro ausente das fontes por ≥ 3 execuções → removido do JSON
- [ ] `first_seen_at` nunca alterado após criação
- [ ] JSON ordenado por `data_evento` crescente

**Frontend:**
- [ ] Filtro de período inicia sempre em "A partir de hoje" (não persiste em `localStorage`)
- [ ] Filtros de distância e estado persistem em `localStorage`
- [ ] Filtro de distância modo Seleção: OR lógico entre pills ativas
- [ ] Filtro de distância modo Intervalo: min e/ou max funcionam corretamente
- [ ] Toggle entre modos de distância reseta valores do modo anterior
- [ ] Filtros combinados (distância + período + estado) funcionam simultaneamente
- [ ] Contador de resultados atualiza em tempo real
- [ ] Badge de status exibe os 4 estados corretamente, com "Realizado" tendo prioridade
- [ ] Card expandido exibe período de inscrição quando disponível
- [ ] Card expandido exibe seção "Onde se inscrever" com links por fonte
- [ ] Eventos passados ficam ocultos por padrão e visíveis ao selecionar "Todo o período"
- [ ] `fetch('./corridas.json')` funciona corretamente no deploy do GitHub Pages
- [ ] PWA instalável na home screen (Android e iOS)

**CI/CD:**
- [ ] GitHub Actions executa sem erros
- [ ] `data/corridas.json` commitado apenas se houve mudança
- [ ] `web/corridas.json` sempre presente no deploy
- [ ] Falha em qualquer fonte individual não impede o deploy
