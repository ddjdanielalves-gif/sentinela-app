"""
main.py — ponto de entrada do backend Sentinela IA.

Estrutura de pastas esperada:

    sentinela-ia/
    ├── main.py                      <- este arquivo
    ├── requirements.txt
    └── app/
        └── services/
            ├── __init__.py          <- vazio, só pra virar pacote Python
            └── sentinela_parser.py  <- o parser que te mandei antes

Rodar localmente:
    python -m venv venv
    venv\\Scripts\\activate        (Windows)  ou  source venv/bin/activate (Mac/Linux)
    pip install -r requirements.txt
    uvicorn main:app --reload

Depois abra http://127.0.0.1:8000/docs no navegador pra testar.
"""

from dotenv import load_dotenv

load_dotenv()  # carrega o .env localmente; no Render, as env vars já vêm configuradas

from fastapi import FastAPI, HTTPException, Query

from app.services.sentinela_parser import fetch_article, parse_article
from app.services.article_finder import encontrar_artigo_estudo_recente
from app.services.gemini_client import gerar_resposta

app = FastAPI(
    title="Sentinela IA",
    description="Backend que busca e processa o artigo semanal d'A Sentinela",
    version="0.1.0",
)


@app.get("/")
def raiz():
    """Rota simples só pra confirmar que o serviço está no ar."""
    return {"status": "ok", "servico": "Sentinela IA"}


@app.get("/artigo")
def obter_artigo(
    url: str = Query(
        ...,
        description="URL completa do artigo no www.jw.org (não usar wol.jw.org)",
        example="https://www.jw.org/pt/biblioteca/revistas/watchtower-study-...",
    )
):
    """
    Busca o artigo no jw.org e devolve título, perguntas, parágrafos
    e imagens já estruturados em JSON — pronto pra alimentar o Gemini
    na etapa seguinte (paráfrase).
    """
    if "wol.jw.org" in url:
        raise HTTPException(
            status_code=400,
            detail="Use uma URL do www.jw.org, não do wol.jw.org.",
        )

    try:
        html = fetch_article(url)
    except Exception as erro:
        raise HTTPException(
            status_code=502, detail=f"Falha ao buscar o artigo: {erro}"
        )

    try:
        artigo = parse_article(html)
    except Exception as erro:
        raise HTTPException(
            status_code=500, detail=f"Falha ao interpretar o artigo: {erro}"
        )

    if not artigo["items"]:
        raise HTTPException(
            status_code=422,
            detail="Nenhuma pergunta/parágrafo foi encontrado nessa URL. "
            "Confira se é mesmo a página de um artigo de estudo.",
        )

    return artigo


@app.get("/semana")
def artigo_da_semana(com_respostas: bool = Query(True, description="Se True, já gera as respostas via Gemini")):
    """
    Pipeline completo: acha sozinho o artigo de estudo da semana atual,
    faz o parsing e (opcionalmente) já gera a resposta parafraseada de
    cada pergunta com o Gemini.
    """
    try:
        url = encontrar_artigo_estudo_recente()
    except Exception as erro:
        raise HTTPException(status_code=502, detail=str(erro))

    html = fetch_article(url)
    artigo = parse_article(html)

    if not artigo["items"]:
        raise HTTPException(
            status_code=422,
            detail=f"Artigo encontrado ({url}) mas sem perguntas/parágrafos reconhecidos.",
        )

    if com_respostas:
        for item in artigo["items"]:
            if item["pergunta"]:
                try:
                    item["resposta_ia"] = gerar_resposta(
                        item["pergunta"], item["paragrafo"], item.get("imagem")
                    )
                except Exception as erro:
                    item["resposta_ia"] = None
                    item["erro_ia"] = str(erro)

    artigo["url"] = url
    return artigo
