# Handoff: Galeria de corridas — linha do tempo "Diário escuro"

## Visão geral
Redesign da página **Galeria** (`run.mmendelson.com/gallery`). A galeria lista provas marcantes de corrida ao longo da vida, cada uma com links para **Strava** e para o relógio usado (**Garmin** ou **Polar**).

O design atual exibe cada prova num card com dois botões de logo gigantes (Strava + Garmin/Polar). O problema: os logos têm o mesmo peso visual da prova, os cards ficam vazios e os dados disponíveis (distância, cidade) não aparecem.

**O novo design** transforma a galeria numa **linha do tempo editorial em tema escuro**, organizada em **capítulos por ano**, onde:
- A prova (nome, distância, cidade, data) é a protagonista; os links Strava/Garmin/Polar viram ação secundária discreta.
- Cada ano é uma **régua de tempo jan→dez**: a posição vertical de cada prova é **proporcional ao mês** em que ela aconteceu. Uma corrida em março fica no alto do ano; em outubro, perto do fim.
- A ordem é **cronológica** (ano mais antigo no topo → mais recente embaixo), para a "evolução do ano" ser lida na direção natural (de cima para baixo).

## Sobre os arquivos deste bundle
Os arquivos `Galeria de Corridas.html` e `gallery-app.jsx` são **referências de design feitas em HTML/React** — protótipos que mostram a aparência e o comportamento pretendidos, **não código de produção para copiar diretamente**.

A tarefa é **recriar este design no codebase atual do site** (`run.mmendelson.com`), usando os padrões, componentes e bibliotecas já estabelecidos nele, e **reaproveitando a lista de eventos que já existe no código**. O protótipo usa dados de exemplo (placeholders); a implementação real deve ler as provas existentes.

> Observação: o protótipo apresenta o design dentro de um "design canvas" (com zoom/pan) e mostra também variações de referência (A2 claro, direção B). **Apenas a direção final importa** para a implementação: o componente **`GalleryAnoDark`** dentro de `gallery-app.jsx`. Ignore `DesignCanvas`, `GalleryDiarioLine/Stations/Solid`, `GalleryPodio`, `GalleryMemoria` e `PhotoFill` — são scaffolding e direções descartadas.

## Fidelidade
**Hi-fi (alta fidelidade).** Cores, tipografia, espaçamentos e o algoritmo de posicionamento estão definidos com precisão abaixo. Recrie a UI fielmente usando as bibliotecas/padrões do codebase.

---

## Tela: Galeria (página única, rolável)

### Propósito
O visitante percorre as provas de cima (mais antigas) para baixo (mais recentes), lê os dados de cada prova e clica para abri-la no Strava ou no Garmin/Polar.

### Layout geral (mobile-first; é a forma como a página é consumida)
- **Fundo da página:** `#0f1115` (quase preto azulado).
- **Container de conteúdo:** largura total no mobile; em telas maiores, centralizar com largura máxima ~`420px` (a galeria é uma coluna estreita estilo "feed"). Padding horizontal `28px`.
- Estrutura vertical:
  1. **Header** (não rolável de forma especial; rola junto).
  2. **Linha divisória** `1px solid #20242c`.
  3. **Trilho vertical (a "espinha")** + os **capítulos por ano**.

### Header
- Padding: `38px 28px 18px`.
- **Sobrelinha (nome):** texto em caixa alta, `font-size: 10.5px`, `letter-spacing: .24em`, `text-transform: uppercase`, `color: #6a7080`, `font-weight: 700`. Conteúdo: nome do dono do site (no protótipo: `MAURICIO MENDELSON`).
- **Título:** fonte serifada **Spectral**, `font-weight: 500`, `font-size: 30px`, `line-height: 1.05`, `letter-spacing: -.01em`, `color: #f3efe7`. Texto em duas linhas: `Corridas que` / `marcaram o caminho`.

### O trilho (linha do tempo)
- Uma **linha vertical contínua** corre por toda a área de conteúdo.
- Posição X da linha: `padding-left (28) + 16 = 44px` a partir da borda esquerda do container (ou seja, `16px` dentro da coluna do trilho).
- Largura: `1.5px`. Cor: gradiente vertical `linear-gradient(#2c323d, #191c22)`.
- A linha começa `8px` abaixo do topo da área de conteúdo e termina `16px` antes do fim.

### Capítulo por ano (o conceito central)
Cada ano é uma **banda** de altura fixa que representa o ano inteiro (jan no topo, dez na base).

- **Altura da banda (`PPY`):** `350px` = 1 ano completo.
- A banda é `position: relative`; tudo dentro dela é posicionado de forma absoluta por fração do ano.
- **Marcador do ano:** no topo da banda (posição de janeiro):
  - Nó: círculo `11×11px`, `border-radius: 6px`, `background: #f3efe7`, com "anel" do fundo via `box-shadow: 0 0 0 4px #0f1115`, centrado na linha (`left: RX-5`, `top: 4`, dentro da coluna do trilho).
  - Rótulo do ano: fonte **Spectral**, `font-size: 23px`, `font-weight: 500`, `color: #f3efe7`, à direita do nó (gap `14px`).

- **Régua de meses (12 marcas por ano):** para cada mês `mi` de 0 a 11, posição vertical `top = (mi / 12) * PPY`.
  - **Tick (marca):** retângulo `7×1px`, `background: #2b313b`, cruzando a linha (`left: RX-3.5`). **Não desenhar tick no mês 0** (o nó do ano já marca janeiro).
  - **Rótulo:** à esquerda da linha (`left: 0`, `width: RX-5`, `text-align: right`).
    - Meses de trimestre (`mi` 0, 3, 6, 9 → `JAN`, `ABR`, `JUL`, `OUT`): `font-size: 8.5px`, `letter-spacing: .08em`, `font-weight: 700`, `color: #565c68`.
    - Demais meses: inicial única (`F M A M J J A S O N D`...): `font-size: 8px`, `font-weight: 700`, `color: #363c46`.

- **Provas dentro do ano:** cada prova é posicionada absolutamente em `top = fração_do_ano * PPY - 6`.
  - `fração_do_ano = (índice_do_mês + (dia - 1) / 31) / 12`, onde índice do mês: JAN=0 … DEZ=11.
  - Layout da prova: linha flex com gap `14px`: `[coluna trilho 34px][conteúdo flex:1]`.
  - **Nó da prova:** círculo `9×9px`, `border-radius: 5px`, cor por **tipo de prova** (ver tokens), anel `box-shadow: 0 0 0 3.5px #0f1115`, posicionado em `left: RX-4`, `top: 3` na coluna do trilho — fica sobre a linha, no ponto exato do mês.
  - **Conteúdo:**
    - **Linha de meta** (flex, `align-items: baseline`, gap `8px`):
      - Data: `{dia} {MÊS}` (ex.: `07 JUN`), `font-size: 10px`, `letter-spacing: .16em`, `text-transform: uppercase`, `font-weight: 700`, cor = cor do tipo de prova.
      - Tipo + distância: `{Tipo} · {dist} km` (ex.: `MARATONA · 42,2 KM`), `font-size: 10px`, `letter-spacing: .14em`, `uppercase`, `font-weight: 600`, `color: #5e6472`.
    - **Nome da prova:** **Spectral**, `font-weight: 500`, `font-size: 18px`, `line-height: 1.2`, `letter-spacing: -.005em`, `color: #f3efe7`, `margin-top: 4px`.
    - **Local:** `{cidade} · {UF}`, `font-size: 12.5px`, `color: #8b91a0`, `margin-top: 3px`.
    - **Links** (ver "Links de plataforma"), `margin-top: 12px`.

### Espaçamento entre capítulos (evitar sobreposição)
Como provas em meses tardios (ex.: outubro) ficam perto da base da banda, o card pode invadir o ano seguinte. Calcular a margem superior do próximo capítulo dinamicamente:

```
CARD = 84            // altura aproximada de um card de prova, em px
PPY  = 350
// para cada ano (em ordem cronológica), seja lastF a maior fração de prova do ano:
overflow_do_ano = max(0, lastF * PPY + CARD - PPY) + 16
margem_superior_do_proximo_ano = max(16, overflow_do_ano_anterior)
// o primeiro capítulo usa margem superior = 2
```

## Links de plataforma (Strava + Garmin/Polar)
Renderizados como **ações de texto discretas** (não botões grandes), lado a lado, gap `16px`, `margin-top: 12px`. Cada link:
- `display: inline-flex; align-items: center; gap: 6px`.
- `font-size: 12px`, `font-weight: 600`, `color: #dad6cd`, `text-decoration: none`.
- `border-bottom: 1px solid #363c47`, `padding-bottom: 2px` (sublinhado sutil).
- Conteúdo:
  - **Strava:** ícone do chevron Strava (`14px`, ver Assets) + texto `Strava` + seta `↗`.
  - **Garmin/Polar:** wordmark da marca (ver Assets) renderizado em tom claro (`#aeb4c0`) + seta `↗`.
- O `href` de cada link deve apontar para a URL real da atividade (no protótipo são `#`).
- **Seta `↗`:** SVG `10×10`, `stroke: currentColor`, `stroke-width: 1.6`, path `M3.5 8.5 L8.5 3.5 M4.5 3.5 h4 v4`.

## Interações & comportamento
- **Clique nos links:** abrem a atividade no Strava / Garmin Connect / Polar Flow. Recomenda-se `target="_blank" rel="noopener"`.
- **Hover nos links** (sugestão, não no protótipo): clarear `color` para `#fff` e a `border-bottom` para `#4a5260`. Transição `.15s`.
- **Sem filtros, sem busca, sem estatísticas** — decisão de produto: a página é uma vitrine enxuta.
- **Responsivo:** no desktop, manter a coluna estreita centralizada (~`420px`); não esticar os cards. A régua e o trilho permanecem iguais.
- **A página inteira rola** (o protótipo mostra só os 3 anos mais recentes por ser um recorte; a implementação real deve renderizar **todos os anos** com provas).

## Gerenciamento de estado
- Nenhum estado de UI complexo. A página é essencialmente estática a partir da lista de provas.
- **Dados:** ler a **lista de eventos já existente no código do site**. Cada prova precisa de: `nome`, `distância` (string, ex.: `"42,2"`), `tipo` (`Maratona` | `Meia` | `10K` | etc.), `cidade`, `uf`, `dia`, `mês`, `ano`, URL do Strava, plataforma do relógio (`Garmin` | `Polar`) e URL dela.
- **Transformações necessárias no código:**
  1. Ordenar as provas em ordem **cronológica crescente** (mais antiga primeiro).
  2. Agrupar por ano.
  3. Para cada prova, calcular `fração_do_ano` a partir de mês+dia.
  4. Renderizar capítulos com o algoritmo de margens acima.
- Se a lista atual não tiver `tipo`, `cidade`/`uf` ou `dia` exato, será preciso enriquecê-la (o design depende de mês/dia para o posicionamento e de tipo para a cor do nó).

## Design tokens

### Cores
| Token | Hex | Uso |
|---|---|---|
| Fundo | `#0f1115` | fundo da página + anel dos nós |
| Texto claro / títulos | `#f3efe7` | títulos serifados, ano, nomes de prova |
| Texto secundário | `#8b91a0` | cidade/UF |
| Texto terciário | `#5e6472` | tipo+distância |
| Sobrelinha / muted | `#6a7080` | nome no header |
| Linha divisória | `#20242c` | borda sob o header |
| Trilho (gradiente) | `#2c323d → #191c22` | linha vertical |
| Tick de mês | `#2b313b` | marcas de mês |
| Rótulo trimestre | `#565c68` | JAN/ABR/JUL/OUT |
| Rótulo mês menor | `#363c46` | iniciais de mês |
| Link (texto) | `#dad6cd` | links de plataforma |
| Link (borda) | `#363c47` | sublinhado do link |
| Link device (mark) | `#aeb4c0` | wordmark Garmin/Polar mono |

### Cores por tipo de prova (cor do nó + data)
| Tipo | Hex |
|---|---|
| Maratona | `#E4572E` (laranja) |
| Meia (21k) | `#3A7CA5` (azul) |
| Outras (10K, 5K…) | `#2A9D5C` (verde) |

### Tipografia
- **Serifada (títulos, ano, nomes de prova):** `Spectral`, pesos 400/500/600.
- **Sans (todo o resto):** `Archivo`, pesos 400/500/600/700/800.
- Importação Google Fonts usada no protótipo:
  `Archivo:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400` + `Spectral:wght@400;500;600`.
  (A direção B/Pódio usa `Saira Condensed`, mas **não é necessária** para esta tela.)

### Métricas-chave
- `PPY` (altura de 1 ano): `350px`
- `CARD` (altura estimada do card p/ cálculo de overflow): `84px`
- Eixo X da linha dentro do trilho (`RX`): `16px`
- Largura da coluna do trilho (`RAIL`): `34px`
- Padding horizontal do container: `28px`
- Gap entre coluna do trilho e conteúdo: `14px`

### Border radius / shadow
- Nós: círculos (`border-radius: 5–6px` em elementos de 9–11px).
- "Anel" dos nós: `box-shadow: 0 0 0 3.5–4px #0f1115` (recorta a linha atrás do nó).

## Assets (marcas)
Recriadas inline no protótipo (ver `gallery-app.jsx`). Use os logos/SVGs oficiais que o codebase já tiver; caso contrário:
- **Strava:** marca do chevron duplo, cor oficial `#FC4C02` (na versão escura pode ficar colorida). SVG no protótipo (componente `Strava`).
- **Garmin:** wordmark `GARMIN`, `Archivo` 700, `letter-spacing: .07em`. Azul oficial `#0B7BBF`; nos links escuros é renderizado em `currentColor`/`#aeb4c0` (monocromático).
- **Polar:** wordmark `POLAR` itálico, `Archivo` 800; o "O" em vermelho `#E2001A`; versão monocromática nos links escuros.
- Componente `DeviceMark({ name, mono })` escolhe Garmin ou Polar.

## Arquivos
- `Galeria de Corridas.html` — documento do protótipo (carrega React + o app). Só para referência visual.
- `gallery-app.jsx` — todo o código React. **Componente relevante: `GalleryAnoDark`.** Helpers relevantes: `RACES` (formato dos dados de exemplo), `fracOfYear`, `dateKey`, `distColor`, `EditorialLinksDark`, `Strava`, `GarminMark`, `PolarMark`, `DeviceMark`, `ArrowUpRight`. O resto (`DesignCanvas`, demais `Gallery*`, `PhotoFill`) é scaffolding/variações e deve ser ignorado.
