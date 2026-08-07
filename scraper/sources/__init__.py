from . import (
    atletis,
    correr_brasilia,
    bora_correr,
    # brasil_que_corre,  # desativada 2026-08-07: o site responde 503 desde 2026-07-10 (30 falhas seguidas)
    portal_das_corridas,
    central_da_corrida,
    conta_passos,
    minhas_inscricoes,
    corridas_brasil,
    brasil_corrida,
    runner_brasil,
    teniscerto_provas,
    tf_sports,
    tf_sports_app,
    sesc_df,
    ticket_sports,
    maratona_rio,
    maratona_porto_alegre,
    sp_city_marathon,
    yescom,
    ativo,
    mks_esportes,
    circuito_das_estacoes,
    largada_esportiva,
    volta_do_lago,
    runsignup,
    # halfmarathons,  # desativada 2026-08-07: Cloudflare 403 em TODO o site (até /robots.txt)
    asdeporte,
    carreras_mexico,
    raceroster,
    usroadrunning,
    # letsdothis,    # inviável: WAF bloqueia todos os proxies (direct 403, Scrapestack 500, Apify 403)
    worldsmarathons,
    finishers,
    # letsdothis,    # inviável: WAF bloqueia o acesso direto (HTTP 403) e o Playwright
    # world_athletics,  # desativada 2026-06-04: páginas de competição retornam 404 e o
    #                    # horário (campo obrigatório) é indisponível em qualquer fonte pública.
    #                    # Ver docs/source-research/world_athletics.md
)
