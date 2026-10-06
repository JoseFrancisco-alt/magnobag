// Lista de manchetes: usada na página de notícias e na página de cada ativo.
const tempoRelativo = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });

function haQuanto(iso) {
  const minutos = Math.round((new Date(iso) - Date.now()) / 60000);
  if (Math.abs(minutos) < 60) return tempoRelativo.format(minutos, "minute");
  const horas = Math.round(minutos / 60);
  if (Math.abs(horas) < 24) return tempoRelativo.format(horas, "hour");
  return tempoRelativo.format(Math.round(horas / 24), "day");
}

function itemNoticia(n, mostrarTicker) {
  const li = document.createElement("li");
  li.className = "noticia";
  li.dataset.ticker = n.ticker;
  const link = document.createElement("a");
  link.href = n.link;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = n.titulo;
  const meta = document.createElement("div");
  meta.className = "sutil pequeno";
  meta.textContent = [mostrarTicker ? n.ticker.replace(".SA", "") : null, n.fonte, haQuanto(n.data)]
    .filter(Boolean).join(" · ");
  li.append(link, meta);
  return li;
}

async function buscarNoticias(ticker) {
  const r = await fetch(`/api/noticias/${encodeURIComponent(ticker)}`);
  const dados = await r.json();
  if (!r.ok) throw new Error(dados.erro);
  return dados;
}

// Preenche <ul> com as notícias de vários ativos, misturadas e da mais nova para a mais velha
async function mostrarNoticias(lista, tickers, mostrarTicker) {
  lista.innerHTML = '<li class="sutil">Buscando notícias…</li>';
  const resultados = await Promise.allSettled(tickers.map(buscarNoticias));
  const todas = resultados.filter((r) => r.status === "fulfilled").flatMap((r) => r.value)
    .sort((a, b) => b.data.localeCompare(a.data));
  lista.innerHTML = "";
  if (!todas.length) {
    lista.innerHTML = '<li class="sutil">Nenhuma notícia encontrada nos últimos 7 dias.</li>';
    return;
  }
  todas.forEach((n) => lista.append(itemNoticia(n, mostrarTicker)));
}
