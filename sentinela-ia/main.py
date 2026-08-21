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
from urllib.parse import urlparse

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
    version="0.3.0",
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def validar_url_jw(url: str) -> None:
    """
    Valida se a URL informada pertence ao www.jw.org.

    Não aceita wol.jw.org.
    """

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="URL inválida.",
        )

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="A URL precisa usar http ou https.",
        )

    hostname = (parsed.hostname or "").lower()

    if hostname == "wol.jw.org":
        raise HTTPException(
            status_code=400,
            detail=(
                "O sistema não utiliza wol.jw.org. "
                "Use uma URL do www.jw.org."
            ),
        )

    if hostname not in (
        "www.jw.org",
        "jw.org",
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "A URL precisa pertencer ao www.jw.org."
            ),
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

    Uso com data específica:

        GET /artigo?data=2026-08-20

    Uso manual:

        GET /artigo?url=https://www.jw.org/...
    """

    # ========================================================
    # 1. DETERMINAR A DATA
    # ========================================================

    data_busca = data or date.today()


    # ========================================================
    # 2. DETERMINAR A URL DO ARTIGO
    # ========================================================

    if url:

        # ----------------------------------------------------
        # URL fornecida manualmente
        # ----------------------------------------------------

        validar_url_jw(url)

        url_artigo = url

    else:

        # ----------------------------------------------------
        # Busca automática
        # ----------------------------------------------------

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
    # 3. BAIXAR O ARTIGO
    # ========================================================

    try:

        html = fetch_article(
            url_artigo
        )

    except Exception as erro:

        raise HTTPException(
            status_code=502,
            detail={
                "erro": (
                    "Não foi possível acessar "
                    "o artigo no JW.org."
                ),
                "detalhes": str(erro),
                "url": url_artigo,
            },
        )


    # ========================================================
    # 4. INTERPRETAR O ARTIGO
    # ========================================================

    try:

        artigo = parse_article(
            html
        )

    except Exception as erro:

        raise HTTPException(
            status_code=500,
            detail={
                "erro": (
                    "O artigo foi baixado, "
                    "mas não foi possível interpretá-lo."
                ),
                "detalhes": str(erro),
                "url": url_artigo,
            },
        )


    # ========================================================
    # 5. VALIDAR RESULTADO
    # ========================================================

    if not isinstance(artigo, dict):

        raise HTTPException(
            status_code=500,
            detail={
                "erro": (
                    "O parser retornou um formato inválido."
                ),
                "url": url_artigo,
            },
        )


    items = artigo.get(
        "items",
        [],
    )


    if not isinstance(items, list):

        raise HTTPException(
            status_code=500,
            detail={
                "erro": (
                    "O campo 'items' retornado "
                    "pelo parser é inválido."
                ),
                "url": url_artigo,
            },
        )


    if not items:

        raise HTTPException(
            status_code=422,
            detail={
                "erro": (
                    "O artigo foi encontrado, "
                    "mas nenhuma pergunta ou parágrafo "
                    "foi identificado."
                ),
                "url": url_artigo,
            },
        )


    # ========================================================
    # 6. NORMALIZAR OS ITEMS
    # ========================================================

    items_normalizados = []

    for item in items:

        if not isinstance(item, dict):
            continue

        numero = item.get(
            "numero"
        )

        pergunta = item.get(
            "pergunta"
        )

        paragrafo = item.get(
            "paragrafo"
        )

        imagem = item.get(
            "imagem"
        )

        items_normalizados.append(
            {
                "numero": numero,
                "pergunta": pergunta,
                "paragrafo": paragrafo,
                "imagem": imagem,
            }
        )


    if not items_normalizados:

        raise HTTPException(
            status_code=422,
            detail={
                "erro": (
                    "Nenhum item válido foi encontrado "
                    "no artigo."
                ),
                "url": url_artigo,
            },
        )


    # ========================================================
    # 7. RETORNAR JSON
    # ========================================================

    return {
        "status": "ok",

        "data_consulta": (
            data_busca.isoformat()
        ),

        "url": url_artigo,

        "titulo": artigo.get(
            "titulo",
            "",
        ),

        "items": items_normalizados,
    }


# ============================================================
# ROTA DE SAÚDE
# ============================================================

@app.get("/health")
def health():
    """
    Endpoint utilizado pelo Render
    para verificar a saúde da aplicação.
    """

    return {
        "status": "healthy",
    }
