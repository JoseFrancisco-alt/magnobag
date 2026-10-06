// Página de um ativo: busca a análise na API e desenha os gráficos.
let moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const pct = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1, signDisplay: "always" });
const pctSimples = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 0 });

const css = getComputedStyle(document.documentElement);
const cor = (nome) => css.getPropertyValue(nome).trim();
const CORES = [cor("--serie-1"), cor("--serie-2"), cor("--serie-3")];

Chart.defaults.color = cor("--texto-sutil");
Chart.defaults.borderColor = cor("--borda");
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

function opcoesBase(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: "index", intersect: false },
    elements: { point: { radius: 0 }, line: { borderWidth: 1.5 } },
    scales: { x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } } },
    plugins: { legend: { labels: { boxWidth: 12 } } },
    ...extra,
  };
}

function linha(label, data, corLinha, extra = {}) {
  return { label, data, borderColor: corLinha, backgroundColor: corLinha, ...extra };
}

function numero(titulo, valor, classe = "") {
  return `<div class="numero"><span class="sutil">${titulo}</span><strong class="${classe}">${valor}</strong></div>`;
}

function desenhar(d) {
  const r = d.resumo;
  moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: d.moeda });
  const datas = d.serie.datas.map((s) => s.split("-").reverse().join("/"));

  document.getElementById("numeros").innerHTML = [
    numero(`Fechamento ${r.data}`, moeda.format(r.preco)),
    numero("No dia", pct.format(r.variacao_dia), r.variacao_dia >= 0 ? "positivo" : "negativo"),
    numero("Em 30 dias", pct.format(r.variacao_30d), r.variacao_30d >= 0 ? "positivo" : "negativo"),
    numero("Faixa de 1 ano", `${moeda.format(r.minima_1a)} – ${moeda.format(r.maxima_1a)}`),
    numero("Tendência", r.tendencia),
    numero("RSI", r.rsi.toFixed(0)),
  ].join("");

  new Chart(document.getElementById("graficoPreco"), {
    type: "line",
    data: {
      labels: datas,
      datasets: [
        linha("Preço", d.serie.preco, cor("--texto")),
        linha("Média 20 dias", d.serie.media_curta, CORES[0]),
        linha("Média 50 dias", d.serie.media_longa, CORES[1]),
      ],
    },
    options: opcoesBase(),
  });

  if (d.limitado) return; // plano grátis: o resto da página fica bloqueado

  document.getElementById("leituraRsi").textContent =
    `Hoje: ${r.rsi.toFixed(0)}, ${r.leitura_rsi}. O RSI mede a força das altas e quedas recentes, de 0 a 100.`;
  new Chart(document.getElementById("graficoRsi"), {
    type: "line",
    data: {
      labels: datas,
      datasets: [
        linha("RSI", d.serie.rsi, CORES[2]),
        linha("70", datas.map(() => 70), cor("--negativo"), { borderDash: [4, 4], borderWidth: 1 }),
        linha("30", datas.map(() => 30), cor("--positivo"), { borderDash: [4, 4], borderWidth: 1 }),
      ],
    },
    options: opcoesBase({ scales: { x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } }, y: { min: 0, max: 100 } },
                          plugins: { legend: { display: false } } }),
  });

  document.getElementById("tabelaEstrategias").innerHTML = d.estrategias.map((e) => `
    <tr>
      <td><strong>${e.nome}</strong><br><span class="sutil">${e.descricao}</span></td>
      <td class="${e.retorno >= 0 ? "positivo" : "negativo"}">${moeda.format(1000 * (1 + e.retorno))}<br>
        <span class="sutil">${pct.format(e.retorno)}</span></td>
      <td class="negativo">${pct.format(e.queda_maxima)}</td>
      <td>${e.operacoes}</td>
    </tr>`).join("");

  new Chart(document.getElementById("graficoCapital"), {
    type: "line",
    data: {
      labels: datas,
      datasets: d.estrategias.map((e, i) =>
        linha(e.nome, e.capital.map((v) => (v === null ? null : v * 1000)), CORES[i])),
    },
    options: opcoesBase({
      scales: { x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                y: { ticks: { callback: (v) => moeda.format(v) } } },
      plugins: { tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${moeda.format(c.parsed.y)}` } } },
    }),
  });

  const p = d.palpite;
  document.getElementById("textoPalpite").textContent =
    `Testamos a regra "se a tendência é de alta, amanhã sobe" em ${p.dias} dias. ` +
    `Ela acertou ${pctSimples.format(p.acerto)} das vezes. Para comparar: dizer "sobe" todo santo dia ` +
    `acertaria ${pctSimples.format(p.sempre_sobe)}, e jogar uma moeda acertaria 50%. ` +
    `Por isso este painel mostra dados, não sinais de compra ou venda.`;
  document.getElementById("barrasPalpite").innerHTML = [
    ["Regra da tendência", p.acerto, CORES[0]],
    ["Dizer sempre \"sobe\"", p.sempre_sobe, CORES[1]],
    ["Cara ou coroa", 0.5, cor("--texto-sutil")],
  ].map(([nome, v, c]) => `
    <div class="barra-linha">
      <span>${nome}</span>
      <div class="barra"><div style="width:${v * 100}%;background:${c}"></div></div>
      <strong>${pctSimples.format(v)}</strong>
    </div>`).join("");
}

(async () => {
  try {
    const resposta = await fetch(`/api/analise/${encodeURIComponent(TICKER)}`);
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.erro || "Erro ao carregar.");
    const conteudo = document.getElementById("conteudo");
    conteudo.hidden = false;
    desenhar(dados);
    revelarAoRolar(conteudo);
    mostrarNoticias(document.getElementById("listaNoticias"), [TICKER], false);
  } catch (e) {
    const erro = document.getElementById("erro");
    erro.textContent = e.message;
    erro.hidden = false;
  } finally {
    document.getElementById("carregando").hidden = true;
  }
})();
