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

from fastapi import FastAPI, HTTPException, Query

from app.services.sentinela_parser import fetch_article, parse_article

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
