"""
article_finder.py

Localiza automaticamente o artigo de estudo da Sentinela da semana atual
no www.jw.org em português.

A edição de estudo normalmente é publicada aproximadamente 2 meses
antes da semana do estudo.

Exemplo:
    junho-2026 -> estudos em agosto de 2026
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.jw.org"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

MESES_PT = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

MESES_SEM_ACENTO = [
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


# Exemplo:
# Artigo de estudo para a semana de 17 a 23 de agosto
#
# Também aceita:
# Artigo de estudo para a semana de 17 a 23 de agosto de 2026
INTERVALO_MESMO_MES_RE = re.compile(
    r"artigo\s+de\s+estudo\s+para\s+a\s+semana\s+de\s+"
    r"(\d{1,2})\s+a\s+(\d{1,2})\s+de\s+"
    r"([a-zç]+)"
    r"(?:\s+de\s+(\d{4}))?",
    re.IGNORECASE,
)


# Exemplo:
# Artigo de estudo para a semana de 29 de julho a 4 de agosto
#
# Também aceita anos:
# 30 de dezembro de 2024 a 5 de janeiro de 2025
INTERVALO_MESES_RE = re.compile(
    r"artigo\s+de\s+estudo\s+para\s+a\s+semana\s+de\s+"
    r"(\d{1,2})\s+de\s+([a-zç]+)"
    r"(?:\s+de\s+(\d{4}))?"
    r"\s+a\s+"
    r"(\d{1,2})\s+de\s+([a-zç]+)"
    r"(?:\s+de\s+(\d{4}))?",
    re.IGNORECASE,
)


def sem_acento(texto: str) -> str:
    """Remove acentos."""
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def slug_mes_ano(data: date) -> str:
    """Retorna o formato usado na URL do JW.org: junho-2026."""
    return f"{MESES_PT[data.month - 1]}-{data.year}"


def deslocar_mes(data: date, quantidade: int) -> tuple[int, int]:
    """Desloca uma data N meses para trás."""
    indice = data.year * 12 + (data.month - 1) - quantidade

    ano = indice // 12
    mes = indice % 12 + 1

    return ano, mes


def candidatos_edicao(hoje: date) -> list[str]:
    """
    Gera edições candidatas.

    Prioridade:
        2 meses antes
        1 mês antes
        3 meses antes
    """
    candidatos = []

    for delta in (2, 1, 3):
        ano, mes = deslocar_mes(hoje, delta)

        data_edicao = date(ano, mes, 1)

        candidatos.append(slug_mes_ano(data_edicao))

    return candidatos


def numero_mes(nome: str) -> int | None:
    """Converte nome do mês para número."""
    nome = sem_acento(nome.lower().strip())

    if nome not in MESES_SEM_ACENTO:
        return None

    return MESES_SEM_ACENTO.index(nome) + 1


def intervalo_valido(
    inicio: date,
    fim: date,
    hoje: date,
) -> tuple[date, date] | None:
    """
    Confirma se a semana encontrada corresponde à data procurada.

    Mantemos tolerância de 1 dia para pequenas diferenças de calendário.
    """
    if inicio - timedelta(days=1) <= hoje <= fim + timedelta(days=1):
        return inicio, fim

    return None


def texto_para_intervalo_datas(
    texto: str,
    hoje: date,
) -> tuple[date, date] | None:
    """
    Identifica o intervalo de estudo presente em um texto.
    """

    texto = sem_acento(texto.lower())

    # ---------------------------------------------------------
    # Primeiro: intervalo entre meses
    # ---------------------------------------------------------

    match = INTERVALO_MESES_RE.search(texto)

    if match:
        (
            dia1,
            mes1_nome,
            ano1,
            dia2,
            mes2_nome,
            ano2,
        ) = match.groups()

        mes1 = numero_mes(mes1_nome)
        mes2 = numero_mes(mes2_nome)

        if mes1 is None or mes2 is None:
            return None

        ano1_int = int(ano1) if ano1 else hoje.year
        ano2_int = int(ano2) if ano2 else ano1_int

        # Se não foi informado o ano e houve passagem de dezembro
        # para janeiro, o segundo ano é o seguinte.
        if not ano2 and mes2 < mes1:
            ano2_int += 1

        try:
            inicio = date(
                ano1_int,
                mes1,
                int(dia1),
            )

            fim = date(
                ano2_int,
                mes2,
                int(dia2),
            )

        except ValueError:
            return None

        if inicio > fim:
            return None

        return intervalo_valido(inicio, fim, hoje)

    # ---------------------------------------------------------
    # Segundo: intervalo dentro do mesmo mês
    # ---------------------------------------------------------

    match = INTERVALO_MESMO_MES_RE.search(texto)

    if not match:
        return None

    dia1, dia2, mes_nome, ano = match.groups()

    mes = numero_mes(mes_nome)

    if mes is None:
        return None

    ano_int = int(ano) if ano else hoje.year

    try:
        inicio = date(
            ano_int,
            mes,
            int(dia1),
        )

        fim = date(
            ano_int,
            mes,
            int(dia2),
        )

    except ValueError:
        return None

    if inicio > fim:
        return None

    return intervalo_valido(inicio, fim, hoje)


def encontrar_artigo_estudo_recente(
    hoje: date | None = None,
) -> str:
    """
    Encontra automaticamente a URL do artigo de estudo da semana.

    Se hoje não for informado, usa a data atual.
    """

    hoje = hoje or date.today()

    erros = []

    for slug in candidatos_edicao(hoje):

        url_edicao = (
            f"{BASE_URL}/pt/biblioteca/revistas/"
            f"sentinela-estudo-{slug}/"
        )

        try:
            resposta = requests.get(
                url_edicao,
                headers=HEADERS,
                timeout=15,
            )

            if resposta.status_code != 200:
                erros.append(
                    f"{url_edicao} -> HTTP {resposta.status_code}"
                )
                continue

        except requests.RequestException as erro:
            erros.append(
                f"{url_edicao} -> {erro}"
            )
            continue

        soup = BeautifulSoup(
            resposta.text,
            "html.parser",
        )

        # -----------------------------------------------------
        # Procuramos nos links.
        # -----------------------------------------------------

        for link in soup.find_all("a", href=True):

            textos_para_testar = []

            texto_link = link.get_text(
                " ",
                strip=True,
            )

            if texto_link:
                textos_para_testar.append(texto_link)

            # Alguns layouts colocam o texto no elemento pai.
            pai = link.find_parent()

            if pai:
                texto_pai = pai.get_text(
                    " ",
                    strip=True,
                )

                if texto_pai:
                    textos_para_testar.append(texto_pai)

            # Também verifica um nível acima quando necessário.
            if pai and pai.parent:
                texto_avo = pai.parent.get_text(
                    " ",
                    strip=True,
                )

                if texto_avo:
                    textos_para_testar.append(texto_avo)

            for texto in textos_para_testar:

                intervalo = texto_para_intervalo_datas(
                    texto,
                    hoje,
                )

                if not intervalo:
                    continue

                inicio, fim = intervalo

                href = link.get("href")

                if not href:
                    continue

                url_artigo = urljoin(
                    BASE_URL,
                    href,
                )

                return url_artigo

    detalhes = "\n".join(erros)

    raise RuntimeError(
        "Não foi possível encontrar o artigo de estudo "
        f"da semana {hoje.strftime('%d/%m/%Y')} no JW.org.\n"
        f"Edições verificadas: {', '.join(candidatos_edicao(hoje))}\n"
        f"{detalhes}"
    )


if __name__ == "__main__":
    # Teste com a data atual.
    try:
        url = encontrar_artigo_estudo_recente()

        print("Artigo encontrado:")
        print(url)

    except Exception as erro:
        print(f"Erro: {erro}")
