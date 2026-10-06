// Simulador de martingale ("gale") em opções binárias.
// Uma rodada = entrada + até N gales. Acertou em qualquer tentativa: fecha no lucro.
// Errou todas: perde a soma das apostas. Sem dinheiro pra próxima aposta: quebrou.
const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const pct = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });

const css = getComputedStyle(document.documentElement);
const cor = (nome) => css.getPropertyValue(nome).trim();
Chart.defaults.color = cor("--texto-sutil");
Chart.defaults.borderColor = cor("--borda");
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

let grafico = null;

function lerConfig() {
  const f = new FormData(document.getElementById("formSimulador"));
  const n = (campo) => Number(f.get(campo));
  return {
    banca: n("banca"), aposta: n("aposta"), gales: Math.round(n("gales")), mult: n("mult"),
    payout: n("payout") / 100, acerto: n("acerto") / 100,
    rodadas: Math.round(n("rodadas")), dias: Math.round(n("dias")), pessoas: Math.round(n("pessoas")),
  };
}

// Conta exata (sem sorteio) de uma rodada com taxa de acerto p
function contaDaRodada(cfg, p = cfg.acerto) {
  let investido = 0, aposta = cfg.aposta, chanceChegar = 1, media = 0;
  const niveis = [];
  for (let k = 0; k <= cfg.gales; k++) {
    const lucro = aposta * cfg.payout - investido;
    niveis.push({ k, chance: chanceChegar * p, lucro });
    media += chanceChegar * p * lucro;
    investido += aposta;
    chanceChegar *= 1 - p;
    aposta *= cfg.mult;
  }
  media -= chanceChegar * investido;
  return { niveis, chancePerderTudo: chanceChegar, perdaTotal: investido, media };
}

// Taxa de acerto mínima do sinal para a rodada não dar prejuízo, em média
function acertoMinimo(cfg) {
  let baixo = 0.01, alto = 0.99;
  for (let i = 0; i < 40; i++) {
    const meio = (baixo + alto) / 2;
    if (contaDaRodada(cfg, meio).media < 0) baixo = meio; else alto = meio;
  }
  return alto;
}

function simularPessoa(cfg) {
  let banca = cfg.banca, quebrou = false, diaQuebrou = -1;
  const historico = [banca];  // banca dia a dia (repete a última depois de quebrar)
  for (let d = 0; d < cfg.dias; d++) {
    for (let r = 0; r < cfg.rodadas && !quebrou; r++) {
      let aposta = cfg.aposta;
      for (let k = 0; k <= cfg.gales; k++) {
        if (aposta > banca) { quebrou = true; break; }
        if (Math.random() < cfg.acerto) { banca += aposta * cfg.payout; break; }
        banca -= aposta;
        aposta *= cfg.mult;
      }
      if (banca < cfg.aposta) quebrou = true;
    }
    historico.push(banca);
    if (quebrou && diaQuebrou < 0) diaQuebrou = d + 1;
  }
  return { final: banca, quebrou, historico, diaQuebrou };
}

function numero(titulo, valor, classe = "", nota = "") {
  return `<div class="numero"><span class="sutil">${titulo}</span><strong class="${classe}">${valor}</strong>` +
         (nota ? `<span class="sutil pequeno">${nota}</span>` : "") + `</div>`;
}

function rodar(evento) {
  if (evento) evento.preventDefault();
  const cfg = lerConfig();
  const pessoas = Array.from({ length: cfg.pessoas }, () => simularPessoa(cfg));
  const finais = pessoas.map((p) => p.final).sort((a, b) => a - b);
  const noLucro = pessoas.filter((p) => p.final > cfg.banca).length / pessoas.length;
  const quebraram = pessoas.filter((p) => p.quebrou).length / pessoas.length;
  const mediana = finais[Math.floor(finais.length / 2)];
  const conta = contaDaRodada(cfg);

  document.getElementById("numeros").innerHTML = [
    numero("Acerto que o grupo divulga", pct.format(1 - conta.chancePerderTudo), "",
           "contando acerto no gale como acerto"),
    numero(`Terminaram no lucro em ${cfg.dias} dias`, pct.format(noLucro), noLucro >= 0.5 ? "positivo" : "negativo"),
    numero("Quebraram a banca", pct.format(quebraram), "negativo"),
    numero("Banca final (pessoa típica)", moeda.format(mediana), mediana >= cfg.banca ? "positivo" : "negativo",
           `começou com ${moeda.format(cfg.banca)}`),
  ].join("");

  // Gráfico enxuto: faixa onde ficaram 80% das pessoas, a pessoa típica (mediana)
  // e só alguns exemplos individuais, bem apagados.
  const dias = Array.from({ length: cfg.dias + 1 }, (_, i) => `Dia ${i}`);
  const percentil = (valores, p) => valores[Math.min(valores.length - 1, Math.floor(p * valores.length))];
  const porDia = dias.map((_, d) => pessoas.map((p) => p.historico[d]).sort((a, b) => a - b));
  const p10 = porDia.map((v) => percentil(v, 0.1));
  const p50 = porDia.map((v) => percentil(v, 0.5));
  const p90 = porDia.map((v) => percentil(v, 0.9));

  const exemplos = pessoas.slice(0, 8).map((p) => ({
    label: "Exemplo",
    data: p.historico.map((v, d) => (p.diaQuebrou >= 0 && d > p.diaQuebrou ? null : v)),
    borderColor: (p.final > cfg.banca ? cor("--positivo") : cor("--negativo")) + "55",
    borderWidth: 1,
  }));
  const datasets = [
    { label: "10% melhores ficaram abaixo de", data: p90, borderColor: "transparent", backgroundColor: cor("--destaque") + "26", fill: "+1" },
    { label: "10% piores ficaram abaixo de", data: p10, borderColor: "transparent" },
    { label: "Pessoa típica", data: p50, borderColor: cor("--destaque"), borderWidth: 2.5 },
    ...exemplos,
    { label: "Banca inicial", data: dias.map(() => cfg.banca), borderColor: cor("--texto-sutil"), borderDash: [5, 5], borderWidth: 1.2 },
  ];

  if (grafico) grafico.destroy();
  grafico = new Chart(document.getElementById("graficoBancas"), {
    type: "line",
    data: { labels: dias, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      elements: { point: { radius: 0 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: (item) => item.dataset.label !== "Exemplo",
          callbacks: { label: (c) => `${c.dataset.label}: ${moeda.format(c.parsed.y)}` },
        },
      },
      scales: { x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                y: { min: 0, ticks: { callback: (v) => moeda.format(v) } } },
    },
  });

  const linhas = conta.niveis.map((n) => `
    <tr><td>${n.k === 0 ? "Acerta na entrada" : `Acerta no gale ${n.k}`}</td>
        <td>${pct.format(n.chance)}</td><td class="positivo">+${moeda.format(n.lucro)}</td></tr>`).join("");
  const minimo = acertoMinimo(cfg);
  document.getElementById("contaRodada").innerHTML = `
    <div class="tabela-rolagem"><table>
      <thead><tr><th>O que acontece</th><th>Chance</th><th>Resultado da rodada</th></tr></thead>
      <tbody>${linhas}
        <tr><td>Erra tudo</td><td>${pct.format(conta.chancePerderTudo)}</td>
            <td class="negativo">−${moeda.format(conta.perdaTotal)}</td></tr>
      </tbody>
    </table></div>
    <p><strong>Média por rodada: <span class="${conta.media >= 0 ? "positivo" : "negativo"}">
      ${conta.media >= 0 ? "+" : "−"}${moeda.format(Math.abs(conta.media))}</span></strong>.
      Ou seja, a cada 100 rodadas, ${conta.media >= 0 ? "ganha" : "perde"} em média
      ${moeda.format(Math.abs(conta.media * 100))}.</p>
    <p class="sutil">Com payout de ${pct.format(cfg.payout)}, o sinal precisaria acertar pelo menos
      <strong>${pct.format(minimo)}</strong> de cada entrada só para empatar. O gale não resolve isso: ele só troca
      muitos ganhos pequenos por uma perda grande e rara.</p>`;
}

document.getElementById("formSimulador").addEventListener("submit", rodar);
rodar();
