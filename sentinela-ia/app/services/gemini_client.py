"""
gemini_client.py

Cliente do Gemini para gerar a resposta parafraseada da pergunta,
com base no parágrafo-fonte extraído pelo sentinela_parser.

IMPORTANTE: o pacote antigo "google.generativeai" está deprecado e os
modelos "gemini-1.5-*" já foram desligados pelo Google. Este arquivo usa
o SDK novo, unificado: "google-genai".

Instalar:
    pip install google-genai

Variável de ambiente necessária:
    GEMINI_API_KEY=sua_chave_aqui
"""

import os
from google import genai

_client: genai.Client | None = None

MODELO_PADRAO = "gemini-3.5-flash"  # ajuste aqui se quiser trocar de modelo


def _get_client() -> genai.Client:
    """Cria o client uma única vez (lazy init) e reaproveita nas próximas chamadas."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Variável de ambiente GEMINI_API_KEY não definida. "
                "No Render, configure em Environment > Environment Variables."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def gerar_resposta(
    pergunta: str,
    texto_paragrafo: str,
    imagem: str | None = None,
    modelo: str = MODELO_PADRAO,
) -> str:
    """
    Usa o Gemini para gerar uma resposta curta, PARAFRASEADA (com outras
    palavras, não copiada ao pé da letra) para a pergunta, com base no
    parágrafo-fonte. Se houver descrição de imagem associada (vinda do
    alt/legenda extraídos pelo parser), ela é incluída no contexto.
    """
    contexto_imagem = f"\n\nDescrição da imagem relacionada: {imagem}" if imagem else ""

    prompt = (
        "Com base no texto abaixo, responda à pergunta de forma clara, direta e "
        "com SUAS PRÓPRIAS PALAVRAS — não copie frases inteiras do texto original, "
        "faça uma paráfrase natural.\n\n"
        f"Texto: {texto_paragrafo}"
        f"{contexto_imagem}\n\n"
        f"Pergunta: {pergunta}\n\n"
        "Resposta:"
    )

    client = _get_client()
    response = client.models.generate_content(model=modelo, contents=prompt)
    return response.text.strip()
