"""
Bot de resumo diário (projeto de estudo, NÃO é recomendação de investimento).

Para cada ação da lista, monta um resumo com:
  - preço, variação do dia, tendência (médias) e RSI
  - um "palpite" de sobe/desce para amanhã + a TAXA DE ACERTO histórica desse palpite
  - os horários em que a mínima e a máxima do dia costumaram acontecer (últimos 60 pregões)

Envia por Telegram se TELEGRAM_TOKEN e TELEGRAM_CHAT_ID estiverem definidos;
senão, só imprime na tela.

Uso:
  python bot_diario.py                     -> ações da lista ACOES
  python bot_diario.py PETR4.SA ITUB4.SA   -> ações escolhidas
"""
import os
import sys

import pandas as pd
import requests
import yfinance as yf

ACOES = ["PETR4.SA", "VALE3.SA", "ITUB4.SA"]
MEDIA_CURTA = 20
MEDIA_LONGA = 50


def baixar(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def calcular_rsi(precos, periodo=14):
    variacao = precos.diff()
    ganhos = variacao.clip(lower=0).ewm(alpha=1 / periodo, adjust=False).mean()
    perdas = (-variacao.clip(upper=0)).ewm(alpha=1 / periodo, adjust=False).mean()
    return 100 - 100 / (1 + ganhos / perdas)


def analise_diaria(ticker):
    df = baixar(ticker, "5y", "1d")
    if df.empty:
        return None
    df["media_curta"] = df["Close"].rolling(MEDIA_CURTA).mean()
    df["media_longa"] = df["Close"].rolling(MEDIA_LONGA).mean()
    df["rsi"] = calcular_rsi(df["Close"])
    df = df.dropna()

    # Palpite: "sobe" se a tendência é de alta e o RSI não está esticado demais
    df["palpite_sobe"] = (df["media_curta"] > df["media_longa"]) & (df["rsi"] < 70)
    # O que de fato aconteceu no dia seguinte
    df["subiu_amanha"] = df["Close"].shift(-1) > df["Close"]
    historico = df.iloc[:-1]  # último dia ainda não tem "amanhã"

    return {
        "data": df.index[-1],
        "preco": df["Close"].iloc[-1],
        "variacao": df["Close"].pct_change().iloc[-1],
        "tendencia_alta": df["media_curta"].iloc[-1] > df["media_longa"].iloc[-1],
        "rsi": df["rsi"].iloc[-1],
        "palpite_sobe": bool(df["palpite_sobe"].iloc[-1]),
        "acerto": (historico["palpite_sobe"] == historico["subiu_amanha"]).mean(),
        "dias_de_alta": historico["subiu_amanha"].mean(),  # acerto de "chutar sempre sobe"
    }


def horarios_tipicos(ticker):
    """Em que hora do pregão a mínima e a máxima do dia costumaram acontecer."""
    df = baixar(ticker, "60d", "1h")
    if df.empty:
        return None
    df.index = df.index.tz_convert("America/Sao_Paulo")
    dia = df.index.date
    hora_min = df.groupby(dia)["Low"].idxmin().map(lambda t: t.hour)
    hora_max = df.groupby(dia)["High"].idxmax().map(lambda t: t.hour)
    freq_min = hora_min.value_counts(normalize=True)
    freq_max = hora_max.value_counts(normalize=True)
    return {
        "hora_min": freq_min.index[0], "freq_min": freq_min.iloc[0],
        "hora_max": freq_max.index[0], "freq_max": freq_max.iloc[0],
        "dias": len(hora_min),
    }


def montar_texto(ticker):
    a = analise_diaria(ticker)
    if a is None:
        return f"{ticker}: não consegui baixar os dados."
    h = horarios_tipicos(ticker)

    linhas = [
        f"📈 {ticker.replace('.SA', '')} | {a['data']:%d/%m}",
        f"Fechamento: R$ {a['preco']:.2f} ({a['variacao']:+.2%})",
        f"Tendência: {'alta' if a['tendencia_alta'] else 'baixa'} | RSI {a['rsi']:.0f}",
        f"Palpite p/ amanhã: {'SOBE ⬆️' if a['palpite_sobe'] else 'DESCE ⬇️'}",
        f"  acerto histórico desse palpite: {a['acerto']:.0%} "
        f"(chutar 'sobe' todo dia: {a['dias_de_alta']:.0%})",
    ]
    if h:
        linhas += [
            f"Horários típicos ({h['dias']} pregões):",
            f"  mínima do dia: ~{h['hora_min']}h ({h['freq_min']:.0%} dos dias)",
            f"  máxima do dia: ~{h['hora_max']}h ({h['freq_max']:.0%} dos dias)",
        ]
    return "\n".join(linhas)


def enviar_telegram(texto):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat_id, "text": texto}, timeout=30)
    r.raise_for_status()
    return True


def main():
    acoes = sys.argv[1:] or ACOES
    texto = "\n\n".join(montar_texto(t) for t in acoes)
    texto += "\n\n⚠️ Estudo, não recomendação. Acerto perto de 50% = moeda."
    print(texto)
    if enviar_telegram(texto):
        print("\n(enviado no Telegram)")
    else:
        print("\n(Telegram não configurado: só imprimi na tela)")


if __name__ == "__main__":
    main()
