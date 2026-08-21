"""
main.py

Ponto de entrada do backend Sentinela IA.
"""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query

from app.services.article_finder import (
    encontrar_artigo_estudo_recente,
)

from app.services.sentinela_parser import (
    fetch_article,
    parse_article,
)


app = FastAPI(
    title="Sentinela IA",
    description=(
        "Backend que localiza e processa automaticamente "
        "o artigo semanal d'A Sentinela."
    ),
    version="0.2.0",
)


@app.get("/")
def raiz():
    """Confirma que o backend está funcionando."""
    return {
        "status": "ok",
        "servico": "Sentinela IA",
    }


@app.get("/artigo")
def obter_artigo(
    url: str | None = Query(
        default=None,
        description=(
            "URL opcional do artigo no www.jw.org. "
            "Se não informar, o sistema encontra "
            "automaticamente o artigo da semana."
        ),
    ),
    data: date | None = Query(
        default=None,
        description=(
            "Data opcional para testes. "
            "Exemplo: 2026-08-20."
        ),
    ),
):
    """
    Busca e processa o artigo da Sentinela.

    Modos:

    1. Automático:
       GET /artigo

    2. Teste com uma data:
       GET /artigo?data=2026-08-20

    3. URL manual:
       GET /artigo?url=https://www.jw.org/...
    """

    # ---------------------------------------------------------
    # 1. Determina a URL
    # ---------------------------------------------------------

    if url:

        if "wol.jw.org" in url.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Use uma URL do www.jw.org, "
                    "não do wol.jw.org."
                ),
            )

        if "jw.org" not in url.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "A URL precisa pertencer ao jw.org."
                ),
            )

        url_artigo = url

    else:

        try:
            url_artigo = encontrar_artigo_estudo_recente(
                data or date.today()
            )

        except Exception as erro:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Não foi possível localizar "
                    "automaticamente o artigo da semana: "
                    f"{erro}"
                ),
            )

    # ---------------------------------------------------------
    # 2. Baixa o artigo
    # ---------------------------------------------------------

    try:
        html = fetch_article(url_artigo)

    except Exception as erro:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Falha ao buscar o artigo: {erro}"
            ),
        )

    # ---------------------------------------------------------
    # 3. Faz o parsing
    # ---------------------------------------------------------

    try:
        artigo = parse_article(html)

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Falha ao interpretar o artigo: {erro}"
            ),
        )

    # ---------------------------------------------------------
    # 4. Validação
    # ---------------------------------------------------------

    if not artigo.get("items"):
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma pergunta/parágrafo foi encontrado "
                "nessa página. Confira se é realmente "
                "um artigo de estudo."
            ),
        )

    # ---------------------------------------------------------
    # 5. Retorno
    # ---------------------------------------------------------

    return {
        "data_consulta": (
            data or date.today()
        ).isoformat(),

        "url": url_artigo,

        "titulo": artigo.get(
            "titulo",
            "",
        ),

        "items": artigo.get(
            "items",
            [],
        ),
    }
