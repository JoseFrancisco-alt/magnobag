"""Manchetes recentes sobre cada ativo, via RSS do Google News (só título, fonte e link)."""
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

import analise

CACHE_SEGUNDOS = 15 * 60
MAX_NOTICIAS = 20
_cache = {}


def termo_de_busca(ticker):
    codigo = ticker.replace(".SA", "").split("-")[0]
    nome = analise.NOMES.get(ticker)
    if ticker.endswith(".SA"):
        return f"{nome} {codigo}" if nome else codigo
    return nome or codigo  # cripto: "Bitcoin" acha mais notícia que "BTC"


def buscar(ticker):
    agora = time.time()
    if ticker in _cache and agora - _cache[ticker][0] < CACHE_SEGUNDOS:
        return _cache[ticker][1]

    resposta = requests.get(
        "https://news.google.com/rss/search",
        params={"q": f"{termo_de_busca(ticker)} when:7d", "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    resposta.raise_for_status()

    noticias, titulos_vistos = [], set()
    for item in ET.fromstring(resposta.content).iter("item"):
        fonte = item.findtext("source") or ""
        titulo = item.findtext("title") or ""
        if fonte and titulo.endswith(f" - {fonte}"):  # o Google repete a fonte no título
            titulo = titulo[: -len(f" - {fonte}")]
        if titulo.lower() in titulos_vistos:  # mesma manchete republicada por outro site
            continue
        titulos_vistos.add(titulo.lower())
        try:
            data = parsedate_to_datetime(item.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        noticias.append({
            "ticker": ticker,
            "titulo": titulo,
            "fonte": fonte,
            "link": item.findtext("link"),
            "data": data.isoformat(),
        })

    noticias.sort(key=lambda n: n["data"], reverse=True)
    noticias = noticias[:MAX_NOTICIAS]
    _cache[ticker] = (agora, noticias)
    return noticias
