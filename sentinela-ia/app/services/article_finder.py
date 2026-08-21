"""
article_finder.py

Encontra a URL do artigo de estudo (A Sentinela) da semana atual, em
português, direto no www.jw.org.

Lógica: a edição da Sentinela usada em Estudo tem sempre ~2 meses de
defasagem em relação ao mês de publicação (edição de janeiro -> estudo
em março, edição de junho -> estudo em agosto etc.). A página de cada
edição lista os artigos com o texto "Artigo de estudo para a semana de
X a Y", em texto simples — é aí que confirmamos qual artigo é o da
semana atual.
"""

import re
import unicodedata
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

_INTERVALO_RE = re.compile(
    r"artigo de estudo para a semana de\s+(\d{1,2})\s+a\s+(\d{1,2})\s+de\s+([a-zç]+)",
    re.IGNORECASE,
)


def _slug_mes_ano(d: date) -> str:
    return f"{MESES_PT[d.month - 1]}-{d.year}"


def _candidatos_slug_edicao(hoje: date) -> list[str]:
    """
    A edição usada em estudo hoje foi publicada ~2 meses antes.
    Gera 3 candidatos (2 meses antes, 1 mês antes, mesmo mês) pra cobrir
    virada de mês/ano com folga.
    """
    candidatos = []
    for delta_meses in (2, 1, 3):
        ano, mes = hoje.year, hoje.month - delta_meses
        while mes <= 0:
            mes += 12
            ano -= 1
        candidatos.append(f"{MESES_PT[mes - 1]}-{ano}")
    return candidatos


def _sem_acento(txt: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c)
    )


def _texto_para_intervalo_datas(texto: str, ano_referencia: int) -> tuple[date, date] | None:
    m = _INTERVALO_RE.search(_sem_acento(texto.lower()))
    if not m:
        return None
    dia_ini, dia_fim, mes_nome = m.groups()
    mes_nome = _sem_acento(mes_nome.lower())
    meses_sem_acento = [_sem_acento(m_) for m_ in MESES_PT]
    if mes_nome not in meses_sem_acento:
        return None
    mes_num = meses_sem_acento.index(mes_nome) + 1
    try:
        inicio = date(ano_referencia, mes_num, int(dia_ini))
        fim = date(ano_referencia, mes_num, int(dia_fim))
    except ValueError:
        return None
    return inicio, fim


def encontrar_artigo_estudo_recente(hoje: date | None = None) -> str:
    """
    Retorna a URL do artigo de estudo cuja semana (mostrada na página da
    edição) contém a data de hoje.
    """
    hoje = hoje or date.today()

    for slug_mes_ano in _candidatos_slug_edicao(hoje):
        url_edicao = f"https://www.jw.org/pt/biblioteca/revistas/sentinela-estudo-{slug_mes_ano}/"
        try:
            resp = requests.get(url_edicao, headers=HEADERS, timeout=15)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        for a in soup.find_all("a", href=True):
            texto_link = a.get_text(" ", strip=True)
            intervalo = _texto_para_intervalo_datas(texto_link, hoje.year)
            if not intervalo:
                # às vezes o intervalo de datas está no elemento pai/irmão,
                # não no próprio texto do link
                pai = a.find_parent()
                if pai:
                    intervalo = _texto_para_intervalo_datas(
                        pai.get_text(" ", strip=True), hoje.year
                    )
            if not intervalo:
                continue

            inicio, fim = intervalo
            # tolerância de 1 dia pra virada de semana
            if inicio - timedelta(days=1) <= hoje <= fim + timedelta(days=1):
                href = a["href"]
                return href if href.startswith("http") else "https://www.jw.org" + href

    raise Exception(
        "Não foi possível encontrar o artigo de estudo da semana atual. "
        "Confira manualmente em https://www.jw.org/pt/biblioteca/revistas/ "
        "e me mande a URL da edição atual pra eu ajustar o parser."
    )
