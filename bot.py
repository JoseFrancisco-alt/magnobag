"""
Bot de análise de ações - versão 1 (projeto de estudo, NÃO é recomendação de investimento).

O que faz:
  1. Baixa 5 anos de preços de uma ação da B3 (yfinance)
  2. Calcula indicadores: médias móveis (20 e 50 dias) e RSI (14 dias)
  3. Faz um backtest da regra "cruzamento de médias" e compara com comprar e segurar
  4. Gera um gráfico (grafico.png) e imprime o resumo do dia

Uso:
  python bot.py            -> analisa PETR4.SA
  python bot.py VALE3.SA   -> analisa outra ação
"""
import sys

import matplotlib
matplotlib.use("Agg")  # salva o gráfico em arquivo, sem abrir janela
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

TICKER = sys.argv[1] if len(sys.argv) > 1 else "PETR4.SA"
MEDIA_CURTA = 20
MEDIA_LONGA = 50
TAXA_POR_OPERACAO = 0.001  # 0,1% de custo a cada compra ou venda


def baixar_dados(ticker):
    df = yf.download(ticker, period="5y", auto_adjust=True, progress=False)
    if df.empty:
        sys.exit(f"Não encontrei dados para {ticker}. Confira o código (ex.: PETR4.SA).")
    if isinstance(df.columns, pd.MultiIndex):  # yfinance às vezes devolve colunas em 2 níveis
        df.columns = df.columns.get_level_values(0)
    return df[["Close"]].rename(columns={"Close": "preco"})


def calcular_rsi(precos, periodo=14):
    variacao = precos.diff()
    ganhos = variacao.clip(lower=0).ewm(alpha=1 / periodo, adjust=False).mean()
    perdas = (-variacao.clip(upper=0)).ewm(alpha=1 / periodo, adjust=False).mean()
    return 100 - 100 / (1 + ganhos / perdas)


def calcular_indicadores(df):
    df["media_curta"] = df["preco"].rolling(MEDIA_CURTA).mean()
    df["media_longa"] = df["preco"].rolling(MEDIA_LONGA).mean()
    df["rsi"] = calcular_rsi(df["preco"])
    return df.dropna()


def backtest(df):
    # Sinal: 1 = comprado (média curta acima da longa), 0 = fora do mercado
    df["sinal"] = (df["media_curta"] > df["media_longa"]).astype(int)
    # shift(1): só posso agir no dia SEGUINTE ao sinal (evita "olhar o futuro")
    df["posicao"] = df["sinal"].shift(1).fillna(0)

    df["retorno_acao"] = df["preco"].pct_change().fillna(0)
    trocas = df["posicao"].diff().abs().fillna(0)
    df["retorno_estrategia"] = df["posicao"] * df["retorno_acao"] - trocas * TAXA_POR_OPERACAO

    df["capital_estrategia"] = (1 + df["retorno_estrategia"]).cumprod()
    df["capital_buy_hold"] = (1 + df["retorno_acao"]).cumprod()
    return df, int(trocas.sum())


def queda_maxima(capital):
    return (capital / capital.cummax() - 1).min()


def gerar_grafico(df, ticker):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True,
                                        gridspec_kw={"height_ratios": [3, 1, 2]})
    ax1.plot(df.index, df["preco"], label="Preço", color="black", linewidth=1)
    ax1.plot(df.index, df["media_curta"], label=f"Média {MEDIA_CURTA}d", linewidth=1)
    ax1.plot(df.index, df["media_longa"], label=f"Média {MEDIA_LONGA}d", linewidth=1)
    ax1.set_title(f"{ticker} - preço e médias móveis")
    ax1.legend()

    ax2.plot(df.index, df["rsi"], color="purple", linewidth=1)
    ax2.axhline(70, color="red", linestyle="--", linewidth=0.8)
    ax2.axhline(30, color="green", linestyle="--", linewidth=0.8)
    ax2.set_title("RSI (acima de 70 = 'caro', abaixo de 30 = 'barato')")

    ax3.plot(df.index, df["capital_estrategia"], label="Estratégia (cruzamento de médias)")
    ax3.plot(df.index, df["capital_buy_hold"], label="Comprar e segurar")
    ax3.set_title("Backtest: quanto R$ 1 teria virado")
    ax3.legend()

    plt.tight_layout()
    plt.savefig("grafico.png", dpi=110)


def main():
    df = calcular_indicadores(baixar_dados(TICKER))
    df, n_operacoes = backtest(df)
    gerar_grafico(df, TICKER)

    hoje = df.iloc[-1]
    tendencia = "ALTA (média curta acima da longa)" if hoje["sinal"] else "BAIXA (média curta abaixo da longa)"
    if hoje["rsi"] > 70:
        leitura_rsi = "sobrecomprado"
    elif hoje["rsi"] < 30:
        leitura_rsi = "sobrevendido"
    else:
        leitura_rsi = "neutro"

    print(f"\n===== {TICKER} | {df.index[-1]:%d/%m/%Y} =====")
    print(f"Preço de fechamento: R$ {hoje['preco']:.2f}")
    print(f"Tendência pelas médias: {tendencia}")
    print(f"RSI(14): {hoje['rsi']:.1f} -> {leitura_rsi}")
    print(f"\n--- Backtest ({df.index[0]:%m/%Y} a {df.index[-1]:%m/%Y}) ---")
    print(f"Estratégia:        {df['capital_estrategia'].iloc[-1] - 1:+.1%} "
          f"| pior queda {queda_maxima(df['capital_estrategia']):.1%} | {n_operacoes} operações")
    print(f"Comprar e segurar: {df['capital_buy_hold'].iloc[-1] - 1:+.1%} "
          f"| pior queda {queda_maxima(df['capital_buy_hold']):.1%}")
    print("\nGráfico salvo em grafico.png")
    print("Aviso: projeto de estudo. Resultado passado não garante resultado futuro.")


if __name__ == "__main__":
    main()
