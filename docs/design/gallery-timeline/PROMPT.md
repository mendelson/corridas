# Prompt para o Claude Code

Copie o texto abaixo (entre as linhas) e cole no Claude Code, na raiz do repositório do site `run.mmendelson.com`. Coloque a pasta `design_handoff_gallery_timeline/` dentro do repo (ou ao lado dele) para que o Claude Code consiga ler os arquivos.

---

Quero redesenhar a página **Galeria** (`/gallery`) do site. A nova UX está totalmente especificada num pacote de handoff: leia **`design_handoff_gallery_timeline/README.md`** por completo antes de começar — ele contém a especificação pixel-perfect, os design tokens e o algoritmo da linha do tempo. Há também um protótipo de referência em **`design_handoff_gallery_timeline/gallery-app.jsx`** (o componente relevante é `GalleryAnoDark`; o resto é scaffolding/variações e deve ser ignorado).

Contexto do que muda:
- Hoje cada prova é um card com dois botões de logo gigantes (Strava + Garmin/Polar). Isso vai embora.
- A nova galeria é uma **linha do tempo editorial em tema escuro**, em **capítulos por ano**, em ordem **cronológica crescente** (ano mais antigo no topo).
- Cada ano é uma **régua jan→dez**; a posição vertical de cada prova é **proporcional ao mês** em que ela ocorreu. Há marcas em todos os meses, com rótulos nos trimestres (JAN/ABR/JUL/OUT).
- Os links Strava e Garmin/Polar viram **ações de texto discretas**, não botões.

Tarefas:
1. **Não copie o HTML do protótipo.** Recrie o design no nosso stack atual, usando os componentes, padrões e bibliotecas que já existem no repositório. Identifique primeiro o framework e o sistema de estilos em uso e siga-os.
2. **Reaproveite a lista de eventos que já existe no código** (não crie dados novos). Localize a estrutura de dados das provas e mapeie-a para os campos que o design precisa: `nome`, `distância`, `tipo` (Maratona/Meia/10K…), `cidade`, `uf`, `dia`, `mês`, `ano`, URL do Strava, plataforma do relógio (Garmin/Polar) e a URL dela.
3. Se a lista atual não tiver `tipo`, `cidade/uf` ou a **data com dia/mês**, me avise: o posicionamento proporcional depende de mês+dia, e a cor do nó depende do tipo. Proponha como enriquecer os dados (ou onde eu devo preenchê-los).
4. Implemente as transformações: ordenar cronologicamente, agrupar por ano, calcular a fração do ano por prova e renderizar os capítulos com o cálculo de margem para evitar sobreposição (tudo no README, seção "Espaçamento entre capítulos").
5. Renderize **todos os anos** com provas (o protótipo mostra só os 3 mais recentes por ser um recorte) e garanta que a **página inteira role** bem no mobile.
6. Use os logos/SVGs oficiais de Strava/Garmin/Polar que o repo já tiver; se não houver, recrie como no protótipo (especificado em "Assets").
7. Respeite os tokens de cor, tipografia (Spectral + Archivo) e métricas (`PPY=350`, `RX=16`, etc.) do README. Se o site já tem fontes/escala próprias, me proponha a melhor adaptação antes de divergir.

Ao terminar, me mostre a página rodando e aponte quais arquivos do repo você criou/alterou.

---

## Dicas para você (dono do site)
- Garanta que cada prova no seu código tenha **data completa (dia/mês/ano)** — sem o mês, a linha do tempo proporcional não funciona.
- Confirme o **tipo** de cada prova (Maratona / Meia / 10K) para as cores dos nós ficarem corretas.
- Tenha à mão as **URLs reais** de Strava e Garmin/Polar de cada atividade.
