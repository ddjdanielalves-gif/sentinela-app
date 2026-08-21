"""
main.py

Backend da Sentinela IA.

Funções:
- verifica se a API está funcionando;
- encontra automaticamente o artigo de estudo da semana;
- permite informar uma URL manualmente para testes;
- baixa e interpreta o artigo;
- retorna perguntas, parágrafos e imagens em JSON.
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


# ============================================================
# APLICAÇÃO
# ============================================================

app = FastAPI(
    title="Sentinela IA",
    description=(
        "API para localizar e interpretar automaticamente "
        "o artigo semanal da Sentinela no JW.org."
    ),
    version="0.2.0",
)


# ============================================================
# ROTA PRINCIPAL
# ============================================================

@app.get("/")
def raiz():
    """
    Verifica se a API está funcionando.
    """

    return {
        "status": "ok",
        "servico": "Sentinela IA",
    }


# ============================================================
# ROTA DO ARTIGO
# ============================================================

@app.get("/artigo")
def obter_artigo(
    url: str | None = Query(
        default=None,
        description=(
            "URL opcional do artigo no JW.org. "
            "Se não informar, o sistema encontra "
            "automaticamente o artigo da semana."
        ),
    ),
    data: date | None = Query(
        default=None,
        description=(
            "Data opcional para testes. "
            "Formato: YYYY-MM-DD."
        ),
    ),
):
    """
    Obtém o artigo de estudo da Sentinela.

    Uso automático:

        GET /artigo

    Uso com uma data específica:

        GET /artigo?data=2026-08-20

    Uso manual com URL:

        GET /artigo?url=https://www.jw.org/...
    """

    # ========================================================
    # 1. DETERMINAR A URL DO ARTIGO
    # ========================================================

    if url:

        # Não permitir WOL nessa rota.
        if "wol.jw.org" in url.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Use uma URL do www.jw.org, "
                    "não do wol.jw.org."
                ),
            )

        # Garantir que seja uma URL do JW.org.
        if "jw.org" not in url.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "A URL precisa pertencer ao jw.org."
                ),
            )

        url_artigo = url

    else:

        # ----------------------------------------------------
        # Busca automática
        # ----------------------------------------------------

        data_busca = data or date.today()

        try:

            url_artigo = encontrar_artigo_estudo_recente(
                data_busca
            )

        except Exception as erro:

            raise HTTPException(
                status_code=502,
                detail={
                    "erro": (
                        "Não foi possível localizar "
                        "automaticamente o artigo da semana."
                    ),
                    "detalhes": str(erro),
                    "data": data_busca.isoformat(),
                },
            )

    # ========================================================
    # 2. BAIXAR O ARTIGO
    # ========================================================

    try:

        html = fetch_article(
            url_artigo
        )

    except Exception as erro:

        raise HTTPException(
            status_code=502,
            detail={
                "erro": "Falha ao acessar o artigo.",
                "detalhes": str(erro),
                "url": url_artigo,
            },
        )

    # ========================================================
    # 3. INTERPRETAR O ARTIGO
    # ========================================================

    try:

        artigo = parse_article(
            html
        )

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail={
                "erro": "Falha ao interpretar o artigo.",
                "detalhes": str(erro),
                "url": url_artigo,
            },
        )

    # ========================================================
    # 4. VALIDAR RESULTADO
    # ========================================================

    items = artigo.get(
        "items",
        [],
    )

    if not items:

        raise HTTPException(
            status_code=422,
            detail={
                "erro": (
                    "O artigo foi encontrado, "
                    "mas nenhuma pergunta/parágrafo "
                    "foi identificado."
                ),
                "url": url_artigo,
            },
        )

    # ========================================================
    # 5. RETORNAR JSON
    # ========================================================

    return {
        "status": "ok",

        "data_consulta": (
            data or date.today()
        ).isoformat(),

        "url": url_artigo,

        "titulo": artigo.get(
            "titulo",
            "",
        ),

        "items": items,

    }


# ============================================================
# ROTA DE SAÚDE
# ============================================================

@app.get("/health")
def health():
    """
    Endpoint simples para o Render verificar a aplicação.
    """

    return {
        "status": "healthy",
    }
