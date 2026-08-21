"""
sentinela_parser.py

Parser do artigo semanal d'A Sentinela (Edição de Estudo), direto do www.jw.org
(NÃO usa wol.jw.org — que é onde seu scraper estava travando).

Extrai, para cada parágrafo do artigo:
  - o número do parágrafo (int)
  - a(s) pergunta(s) associada(s) a ele (algumas perguntas cobrem 2 parágrafos: "14-15.")
  - o texto do parágrafo (texto-fonte da resposta)
  - se houver imagem referente àquele parágrafo, o texto alt + legenda da imagem
    (é a mesma descrição que seria narrada no áudio com descrição — sem precisar
    transcrever MP3, sem custo extra de API)

Uso típico no seu backend:

    from sentinela_parser import fetch_article, parse_article

    html = fetch_article("https://www.jw.org/pt/biblioteca/revistas/w-estudo/artigo/...")
    artigo = parse_article(html)

    for item in artigo["items"]:
        print(item["numero"], item["pergunta"], item["paragrafo"][:80], item["imagem"])

Dependências: requests, beautifulsoup4
    pip install requests beautifulsoup4
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag


HEADERS = {
    # Um user-agent de navegador comum evita bloqueios bobos por parte do CDN.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Padrões de texto que aparecem no HTML mas não são conteúdo real do artigo.
PLACEHOLDER_PATTERNS = [
    "a sua resposta",
    "your answer",
]


@dataclass
class Imagem:
    alt: str
    legenda: str
    paragrafos: list[int] = field(default_factory=list)


@dataclass
class ItemArtigo:
    numero: int
    pergunta: Optional[str]
    paragrafo: str
    imagem: Optional[str] = None  # alt + legenda concatenados, se aplicável


def fetch_article(url: str, timeout: int = 20) -> str:
    """Baixa o HTML bruto do artigo (usar www.jw.org, não wol.jw.org)."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# Extração de imagens e seus parágrafos associados
# ---------------------------------------------------------------------------

_LEGENDA_PARAGRAFO_RE = re.compile(
    r"veja\s+o?s?\s*parágrafos?\s+([\d\s,e]+)", re.IGNORECASE
)


def _extrair_numeros(texto: str) -> list[int]:
    """De 'Veja os parágrafos 14 e 15' ou 'Veja o parágrafo 5' -> [14, 15] / [5]."""
    numeros = re.findall(r"\d+", texto)
    return [int(n) for n in numeros]


def extrair_imagens(soup: BeautifulSoup) -> list[Imagem]:
    """
    Percorre todas as <img> do corpo do artigo. Cada imagem relevante do
    Sentinela vem dentro de um <figure>, com:
      - alt descritivo na própria <img>
      - <figcaption> (ou <em> logo abaixo) com o texto "(Veja o parágrafo N.)"
    """
    imagens: list[Imagem] = []

    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if not alt:
            continue  # ícones, logos etc. não têm alt de conteúdo

        # A legenda pode estar em <figcaption>, ou em um <em>/<p> logo após
        # o <figure> pai (o HTML do jw.org varia um pouco entre publicações).
        legenda = ""
        figure = img.find_parent("figure")
        container = figure if figure else img

        figcaption = container.find("figcaption") if isinstance(container, Tag) else None
        if figcaption:
            legenda = figcaption.get_text(" ", strip=True)
        else:
            # fallback: primeiro <em> ou <p> irmão logo depois do container
            prox = container.find_next_sibling(["em", "p", "span"])
            if prox:
                texto = prox.get_text(" ", strip=True)
                if "parágrafo" in texto.lower() or "paragraph" in texto.lower():
                    legenda = texto

        paragrafos = _extrair_numeros(legenda) if _LEGENDA_PARAGRAFO_RE.search(legenda) else []

        imagens.append(Imagem(alt=alt, legenda=legenda, paragrafos=paragrafos))

    return imagens


# ---------------------------------------------------------------------------
# Extração de perguntas + parágrafos
# ---------------------------------------------------------------------------

# Pergunta: começa com número(s) em negrito seguido de ponto. Ex: "14." ou "14-15."
_PERGUNTA_NUM_RE = re.compile(r"^(\d+)(?:[-–](\d+))?\.\s*")

# Parágrafo: começa com número em negrito SEM ponto, direto colado ao texto.
# Ex.: "14 Para sermos mesmo felizes..."
_PARAGRAFO_NUM_RE = re.compile(r"^(\d+)\s+(?=\S)")


def _texto_limpo(tag: Tag) -> str:
    txt = tag.get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _eh_placeholder(texto: str) -> bool:
    baixo = texto.strip().lower()
    return any(baixo == p or baixo.startswith(p) for p in PLACEHOLDER_PATTERNS)


def parse_article(html: str) -> dict:
    """
    Retorna um dicionário:
        {
            "titulo": str,
            "items": [ItemArtigo, ...]  (como dicts, via asdict)
        }

    Cada item representa um parágrafo numerado, com a pergunta que o precede
    (quando existir) e a imagem associada (quando a legenda referenciar aquele
    número de parágrafo).
    """
    soup = BeautifulSoup(html, "html.parser")

    titulo_tag = soup.find(["h1", "h2"])
    titulo = _texto_limpo(titulo_tag) if titulo_tag else ""

    imagens = extrair_imagens(soup)

    # Pega todos os parágrafos de texto candidatos (tag <p>), na ordem em que
    # aparecem no documento. Isso cobre tanto blocos de pergunta quanto de
    # resposta, porque no jw.org ambos costumam vir em <p> soltos ou <strong>.
    candidatos = soup.find_all(["p"])

    pergunta_pendente: Optional[str] = None
    numeros_pendentes: list[int] = []
    items: list[ItemArtigo] = []

    for p in candidatos:
        texto = _texto_limpo(p)
        if not texto or _eh_placeholder(texto):
            continue

        m_pergunta = _PERGUNTA_NUM_RE.match(texto)
        m_paragrafo = _PARAGRAFO_NUM_RE.match(texto)

        # Heurística: se o <p> tem um <strong>/<b> no início contendo só o
        # número (com ou sem ponto), usamos isso como sinal mais forte.
        primeiro_strong = p.find(["strong", "b"])
        num_strong = None
        tem_ponto_strong = False
        if primeiro_strong:
            txt_strong = _texto_limpo(primeiro_strong)
            m = re.match(r"^(\d+)(?:[-–](\d+))?(\.?)$", txt_strong)
            if m:
                num_strong = (m.group(1), m.group(2))
                tem_ponto_strong = bool(m.group(3))

        eh_pergunta = tem_ponto_strong or bool(m_pergunta)
        eh_paragrafo = (num_strong and not tem_ponto_strong) or (
            m_paragrafo and not eh_pergunta
        )

        if eh_pergunta:
            # Guarda a pergunta e os números de parágrafo que ela cobre
            # (pode ser 1 ou um intervalo, ex: "14-15.").
            if num_strong:
                ini, fim = num_strong
            elif m_pergunta:
                ini, fim = m_pergunta.group(1), m_pergunta.group(2)
            else:
                continue

            ini_i = int(ini)
            fim_i = int(fim) if fim else ini_i
            numeros_pendentes = list(range(ini_i, fim_i + 1))

            # Remove o prefixo numérico do texto da pergunta
            pergunta_texto = _PERGUNTA_NUM_RE.sub("", texto).strip()
            if not pergunta_texto and primeiro_strong:
                pergunta_texto = texto.replace(_texto_limpo(primeiro_strong), "", 1).strip()
            pergunta_pendente = pergunta_texto or texto

        elif eh_paragrafo:
            if num_strong:
                numero = int(num_strong[0])
                corpo = texto
                prefixo_strong = _texto_limpo(primeiro_strong)
                if corpo.startswith(prefixo_strong):
                    corpo = corpo[len(prefixo_strong):].strip()
            else:
                numero = int(m_paragrafo.group(1))
                corpo = _PARAGRAFO_NUM_RE.sub("", texto, count=1).strip()

            # Pergunta associada: se este número está entre os pendentes, usa
            # a mesma pergunta para todos os parágrafos daquele intervalo.
            pergunta_deste = pergunta_pendente if numero in numeros_pendentes else None

            # Imagem associada: procura entre as imagens já extraídas alguma
            # cuja legenda cite este número de parágrafo.
            imagem_texto = None
            if pergunta_deste and re.search(r"veja\s+(também\s+)?a\s+imagem", pergunta_deste, re.I):
                for img in imagens:
                    if numero in img.paragrafos:
                        imagem_texto = f"{img.alt}. {img.legenda}".strip()
                        break

            items.append(
                ItemArtigo(
                    numero=numero,
                    pergunta=pergunta_deste,
                    paragrafo=corpo,
                    imagem=imagem_texto,
                )
            )

    return {
        "titulo": titulo,
        "items": [asdict(item) for item in items],
    }


# ---------------------------------------------------------------------------
# Uso direto via linha de comando (teste rápido)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Uso: python sentinela_parser.py <url-do-artigo-no-www.jw.org>")
        sys.exit(1)

    url = sys.argv[1]
    html = fetch_article(url)
    resultado = parse_article(html)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
