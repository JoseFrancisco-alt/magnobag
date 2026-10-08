"""Cálculos de mercado: download de preços, indicadores e backtests.

Nada aqui é recomendação: o módulo só mede o que teria acontecido no passado.
"""
import os
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf

MEDIA_CURTA = 20
MEDIA_LONGA = 50
TAXA_POR_OPERACAO = 0.001  # 0,1% a cada compra ou venda
CACHE_SEGUNDOS = 15 * 60   # evita baixar o mesmo ativo toda hora

CATALOGO = {
    "Ações B3": {
        "PETR4.SA": "Petrobras",
        "VALE3.SA": "Vale",
        "ITUB4.SA": "Itaú",
        "BBDC4.SA": "Bradesco",
        "BBAS3.SA": "Banco do Brasil",
        "WEGE3.SA": "WEG",
        "ABEV3.SA": "Ambev",
        "MGLU3.SA": "Magazine Luiza",
    },
    "Cripto (em US$)": {
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "SOL-USD": "Solana",
    },
}
NOMES = {ticker: nome for grupo in CATALOGO.values() for ticker, nome in grupo.items()}

_cache = {}

if os.environ.get("VERCEL"):
    yf.set_tz_cache_location(os.path.join(tempfile.gettempdir(), "yfinance"))


def moeda_do_ticker(ticker):
    """Ações da B3 (.SA), câmbio para real e Ibovespa em reais; o resto (cripto, EUA) em dólar."""
    return "BRL" if ticker.endswith(".SA") or ticker.endswith("BRL=X") or ticker == "BRL=X" or ticker == "^BVSP" else "USD"


# ---------- busca de ativos pelo nome ----------

# nomes que a busca do Yahoo não entende bem em português
ATALHOS = {
    "dolar": [("BRL=X", "Dólar em reais", "Câmbio")],
    "dólar": [("BRL=X", "Dólar em reais", "Câmbio")],
    "euro": [("EURBRL=X", "Euro em reais", "Câmbio")],
    "libra": [("GBPBRL=X", "Libra em reais", "Câmbio")],
    "ibovespa": [("^BVSP", "Ibovespa (índice da B3)", "Índice")],
    "ouro": [("GC=F", "Ouro (onça, em dólar)", "Commodity")],
    "petroleo": [("BZ=F", "Petróleo Brent (em dólar)", "Commodity")],
    "petróleo": [("BZ=F", "Petróleo Brent (em dólar)", "Commodity")],
    "nubank": [("ROXO34.SA", "Nubank (BDR na B3)", "Ação B3"), ("NU", "Nu Holdings (EUA)", "Ação EUA")],
}
BOLSAS_EUA = {"NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "BTS"}
_cache_busca = {}


def _tipo_ativo(item):
    tipo, bolsa, simbolo = item.get("quoteType"), item.get("exchange"), item.get("symbol", "")
    if bolsa == "SAO" and re.fullmatch(r"[A-Z0-9]{4}\d{1,2}\.SA", simbolo):  # ignora fracionário (F) e variações
        return "Ação B3" if tipo == "EQUITY" else "Fundo B3"
    if tipo == "CRYPTOCURRENCY" and simbolo.endswith("-USD"):
        return "Cripto"
    if tipo == "CURRENCY":
        return "Câmbio"
    if bolsa in BOLSAS_EUA and tipo in ("EQUITY", "ETF"):
        return "Ação EUA" if tipo == "EQUITY" else "ETF EUA"
    return None  # futuros, outras bolsas etc. ficam de fora


def buscar_ativos(texto, limite=8):
    """Ativos pelo nome ou código: [{"ticker", "nome", "tipo"}], com a B3 primeiro."""
    chave = texto.strip().lower()
    if len(chave) < 2:
        return []
    agora = time.time()
    if chave in _cache_busca and agora - _cache_busca[chave][0] < 3600:
        return _cache_busca[chave][1]

    resultado = [{"ticker": t, "nome": n, "tipo": tp} for t, n, tp in ATALHOS.get(chave, [])]
    try:
        itens = yf.Search(texto, max_results=15, news_count=0).quotes
    except Exception:
        itens = []
    ordem = {"Ação B3": 0, "Fundo B3": 1, "Cripto": 2, "Câmbio": 3, "Ação EUA": 4, "ETF EUA": 5}
    achados = []
    for item in itens:
        tipo = _tipo_ativo(item)
        simbolo = item.get("symbol", "")
        if tipo and all(r["ticker"] != simbolo for r in resultado):
            nome = NOMES.get(simbolo) or item.get("longname") or item.get("shortname") or simbolo
            achados.append({"ticker": simbolo, "nome": " ".join(nome.split()), "tipo": tipo})
    achados.sort(key=lambda r: ordem[r["tipo"]])
    resultado = (resultado + achados)[:limite]
    _cache_busca[chave] = (agora, resultado)
    return resultado


# horário de Brasília (o servidor da Vercel roda em UTC; o Brasil não tem mais horário de verão)
BRASILIA = timezone(timedelta(hours=-3))

# De quanto em quanto tempo os dados são buscados de novo, por plano
TEMPO_ATUALIZACAO = {"gratis": 60 * 60, "assinante": 2 * 60}


def baixar(ticker, plano="assinante"):
    """Preços diários de 5 anos (abertura, máxima, mínima e fechamento) e a hora em que foram buscados.

    Cada plano tem o próprio cache: no grátis os dados só são renovados de hora em hora.
    """
    agora = time.time()
    chave = (ticker, plano)
    if chave in _cache and agora - _cache[chave][0] < TEMPO_ATUALIZACAO[plano]:
        return _cache[chave][1]
    df = yf.download(ticker, period="5y", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if not df.empty:
        df = df[["Open", "High", "Low", "Close"]].rename(columns={
            "Open": "abertura", "High": "maxima", "Low": "minima", "Close": "preco"}).dropna()
    df.attrs["buscado_em"] = agora
    _cache[chave] = (agora, df)
    return df


def calcular_rsi(precos, periodo=14):
    variacao = precos.diff()
    ganhos = variacao.clip(lower=0).ewm(alpha=1 / periodo, adjust=False).mean()
    perdas = (-variacao.clip(upper=0)).ewm(alpha=1 / periodo, adjust=False).mean()
    return 100 - 100 / (1 + ganhos / perdas)


def _lista(serie, casas=2):
    return [None if pd.isna(v) else round(float(v), casas) for v in serie]


def _backtest(nome, descricao, sinal, retornos):
    # shift(1): só dá pra agir no dia seguinte ao sinal (não olha o futuro)
    posicao = sinal.shift(1).fillna(0)
    trocas = posicao.diff().abs().fillna(0)
    capital = (1 + posicao * retornos - trocas * TAXA_POR_OPERACAO).cumprod()
    return {
        "nome": nome,
        "descricao": descricao,
        "retorno": float(capital.iloc[-1] - 1),
        "queda_maxima": float((capital / capital.cummax() - 1).min()),
        "operacoes": int(trocas.sum()),
        "capital": _lista(capital, 4),
    }


def _leitura_rsi(rsi):
    if rsi > 70:
        return "acima de 70: subiu rápido demais recentemente"
    if rsi < 30:
        return "abaixo de 30: caiu rápido demais recentemente"
    return "entre 30 e 70: neutro"


def calcular(ticker, plano="assinante"):
    """Devolve o resumo, as séries para gráfico e os backtests, ou None se não houver dados."""
    df = baixar(ticker, plano)
    buscado_em = df.attrs.get("buscado_em", time.time())
    if df.empty or len(df) < MEDIA_LONGA + 10:
        return None
    df = df.copy()
    df["media_curta"] = df["preco"].rolling(MEDIA_CURTA).mean()
    df["media_longa"] = df["preco"].rolling(MEDIA_LONGA).mean()
    df["rsi"] = calcular_rsi(df["preco"])
    df = df.dropna()
    retornos = df["preco"].pct_change().fillna(0)

    tendencia_alta = df["media_curta"] > df["media_longa"]

    sinal_rsi = pd.Series(float("nan"), index=df.index)
    sinal_rsi.loc[df["rsi"] < 30] = 1
    sinal_rsi.loc[df["rsi"] > 70] = 0
    sinal_rsi = sinal_rsi.ffill().fillna(0)

    estrategias = [
        _backtest("Comprar e segurar", "Compra no primeiro dia e nunca vende.",
                  pd.Series(1.0, index=df.index), retornos),
        _backtest("Cruzamento de médias",
                  f"Fica comprado enquanto a média de {MEDIA_CURTA} dias está acima da de {MEDIA_LONGA}.",
                  tendencia_alta.astype(float), retornos),
        _backtest("RSI", "Compra quando o RSI cai abaixo de 30 e vende quando passa de 70.",
                  sinal_rsi, retornos),
    ]

    # "Palpite": se a tendência é de alta, amanhã sobe. Quantas vezes isso acertou?
    subiu_amanha = (df["preco"].shift(-1) > df["preco"]).iloc[:-1]
    acerto = float((tendencia_alta.iloc[:-1] == subiu_amanha).mean())
    dias_de_alta = float(subiu_amanha.mean())

    ultimo = df.iloc[-1]
    ultimo_ano = df["preco"].iloc[-252:]
    return {
        "ticker": ticker,
        "nome": NOMES.get(ticker, ticker),
        "moeda": moeda_do_ticker(ticker),
        "resumo": {
            "data": df.index[-1].strftime("%d/%m/%Y"),
            "preco": float(ultimo["preco"]),
            "variacao_dia": float(retornos.iloc[-1]),
            "variacao_30d": float(df["preco"].iloc[-1] / df["preco"].iloc[-31] - 1),
            "maxima_1a": float(ultimo_ano.max()),
            "minima_1a": float(ultimo_ano.min()),
            "tendencia": "alta" if tendencia_alta.iloc[-1] else "baixa",
            "rsi": float(ultimo["rsi"]),
            "leitura_rsi": _leitura_rsi(ultimo["rsi"]),
            "ultimos_30": _lista(df["preco"].iloc[-30:]),  # mini gráfico dos cartões
            # médias cruzaram no último pregão? ("alta", "baixa" ou None)
            "cruzou_hoje": (None if tendencia_alta.iloc[-1] == tendencia_alta.iloc[-2]
                            else ("alta" if tendencia_alta.iloc[-1] else "baixa")),
        },
        "atualizado_em": datetime.fromtimestamp(buscado_em, BRASILIA).strftime("%H:%M"),
        "proxima_atualizacao_min": round(TEMPO_ATUALIZACAO[plano] / 60),
        "serie": {
            "datas": [d.strftime("%Y-%m-%d") for d in df.index],
            "preco": _lista(df["preco"]),
            "abertura": _lista(df["abertura"]),
            "maxima": _lista(df["maxima"]),
            "minima": _lista(df["minima"]),
            "media_curta": _lista(df["media_curta"]),
            "media_longa": _lista(df["media_longa"]),
            "rsi": _lista(df["rsi"], 1),
        },
        "estrategias": estrategias,
        "palpite": {
            "acerto": acerto,
            "sempre_sobe": dias_de_alta,
            "dias": int(len(subiu_amanha)),
        },
    }


_cache_horarios = {}
CACHE_HORARIOS_SEGUNDOS = 6 * 60 * 60  # padrão de horário muda devagar


def horarios(ticker):
    """Como o ativo se comporta em cada hora do pregão nos últimos ~60 dias (dados de 1 em 1 hora).

    Devolve, por hora: quanto se mexe em média (variação absoluta), volume médio e em quantos % dos dias
    aquela hora fechou em alta. Ou None se não houver dados suficientes.
    """
    agora = time.time()
    if ticker in _cache_horarios and agora - _cache_horarios[ticker][0] < CACHE_HORARIOS_SEGUNDOS:
        return _cache_horarios[ticker][1]

    df = yf.download(ticker, period="60d", interval="1h", auto_adjust=True, progress=False)
    resultado = None
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = df.index.tz_convert("America/Sao_Paulo")
        df = df[df["Open"] > 0]
        retorno = df["Close"] / df["Open"] - 1
        tabela = pd.DataFrame({
            "hora": df.index.hour,
            "movimento": retorno.abs(),
            "subiu": retorno > 0,
            "volume": df["Volume"],
        }).groupby("hora").agg(movimento=("movimento", "mean"), subiu=("subiu", "mean"),
                               volume=("volume", "mean"), dias=("subiu", "size"))
        tabela = tabela[tabela["dias"] >= 20]  # hora com poucos dados não entra
        if len(tabela) >= 3:
            resultado = {
                "abertura": int(tabela.index.min()),
                "fechamento": int(tabela.index.max()) + 1,
                "agitada": int(tabela["movimento"].idxmax()),
                "movimento_agitada": float(tabela["movimento"].max()),
                "calma": int(tabela["movimento"].idxmin()),
                "movimento_calma": float(tabela["movimento"].min()),
                "mais_volume": int(tabela["volume"].idxmax()) if tabela["volume"].sum() > 0 else None,
                "mais_sobe": int(tabela["subiu"].idxmax()),
                "chance_mais_sobe": float(tabela["subiu"].max()),
                "dias": int(tabela["dias"].max()),
                "24h": len(tabela) >= 20,
            }
    _cache_horarios[ticker] = (agora, resultado)
    return resultado
