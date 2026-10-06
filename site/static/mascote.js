// Magninho: mascote do dono do site. Busca avisos em /api/mascote e fala um de cada vez.
(() => {
  const mascote = document.getElementById("mascote");
  if (!mascote) return;
  const corpo = document.getElementById("mascoteCorpo");
  const balao = document.getElementById("balao");
  const texto = document.getElementById("balaoTexto");
  const link = document.getElementById("balaoLink");
  const contador = document.getElementById("balaoContador");
  const bolinha = document.getElementById("mascoteBolinha");

  // ---------- pixel art do Mimikyu (28x28, gerada por tools/gerar_mascote.py) ----------
  // . vazio  Y pano  S sombra  D barra  O contorno  K preto  R bochecha  B/b rabo  E ponta da orelha  W branco
  const DESENHO = [
    "....OOEEO...................",
    "...OEEEEO.......OOOO........",
    "...OEEEEEO.....OYYYSOO......",
    "...OYYYYYYO...OYYYYSSSO.....",
    "....OYYYYYYOOOYYYYYSSSEO....",
    "....OYYYYYYYYYYYYYYSSSEEO...",
    "....OYYYYYYYYYYYYYYSOSEEEO..",
    "....OYYYYYYYYYYYYSOO.OEEEO..",
    "....OYYYYYYYYYYYYSSO..OEEEO.",
    ".....OYYYKKYYYYKKSSO...OOO..",
    ".....OYYYKKYYYYKKSSO.....OO.",
    ".....OYYYYYYYYYYYSSO...OObbO",
    ".....OYRRYYYYYYYYRRO..ObbbO.",
    "......OYYYYYYYYYYSO..ObbbO..",
    "......OYYYYYYYYYYSO...ObbO..",
    ".....OYYYYYYYYYYSSSO.ObbbO..",
    ".....OYYYYYYYYYYSSSOOBbOO...",
    ".....OYYYYYYYYYYYSSOBBO.....",
    "....OYYYYYYYYYYYYSSSOBbO....",
    "....OYYYYYYYYYYYYYSSBBO.....",
    "....OYYYYYYYYYYYYYSSBO......",
    "....OYYYYYYYYYYYYYYSSO......",
    "....OYYYYYYYYYYYYYYSSO......",
    "....ODDDDDDDDDDDDDDDDO......",
    "....ODOODDOODDOODDOODO......",
    ".....O..OO..OO..OO..O.......",
    "............................",
    "............................",
  ];
  const CORES = { Y: "#ecd27a", S: "#c9a957", D: "#a88a45", O: "#241c1a", K: "#15131a", R: "#d9443a",
                  B: "#8a5a31", b: "#5c3a1f", E: "#2a2730", W: "#ffffff", L: "#8fd3ff", A: "#ff5a4e" };
  const EXCLAMACAO = [[1, 3, "A"], [1, 4, "A"], [1, 5, "A"], [1, 6, "A"], [1, 8, "A"]];
  const RELOGIO = [[0, 12, "W"], [1, 12, "W"], [2, 12, "W"], [0, 13, "W"], [1, 13, "K"], [2, 13, "W"],
                   [0, 14, "W"], [1, 14, "W"], [2, 14, "W"]];
  // boca e detalhes de cada humor: [x, y, cor]
  const BOCA_CALMA = [[11, 13, "K"], [12, 12, "K"], [13, 13, "K"], [14, 12, "K"]];
  const BOCA_FELIZ = [[11, 12, "K"], [14, 12, "K"], [12, 13, "K"], [13, 13, "K"]];
  const BOCAS = {
    calmo: BOCA_CALMA,
    feliz: BOCA_FELIZ,
    noticia: [...BOCA_FELIZ, ...EXCLAMACAO],
    triste: [[12, 12, "K"], [13, 12, "K"], [11, 13, "K"], [14, 13, "K"],
             [9, 9, "Y"], [10, 9, "Y"], [15, 9, "Y"], [16, 9, "Y"], [21, 10, "L"], [21, 11, "L"]],
    alerta: [[12, 12, "K"], [13, 12, "K"], [12, 13, "K"], [13, 13, "K"], ...EXCLAMACAO],
    relogio: [...BOCA_CALMA, ...RELOGIO],
  };
  const svgPixels = document.getElementById("mascotePixels");

  const seloHumor = document.getElementById("mascoteHumor");
  const SELOS = { feliz: "📈", triste: "📉", alerta: "❗", noticia: "📰", relogio: "⏰", calmo: "" };

  function desenhar(nomeHumor) {
    // com imagem própria, o humor aparece num selinho em vez de mudar a cara
    if (!svgPixels) {
      if (seloHumor) seloHumor.textContent = SELOS[nomeHumor] || "";
      return;
    }
    const grade = DESENHO.map((linha) => linha.split(""));
    (BOCAS[nomeHumor] || BOCAS.calmo).forEach(([x, y, c]) => { grade[y][x] = c; });
    const ns = "http://www.w3.org/2000/svg";
    svgPixels.replaceChildren();
    grade.forEach((linha, y) => linha.forEach((c, x) => {
      if (c === ".") return;
      const px = document.createElementNS(ns, "rect");
      px.setAttribute("x", x); px.setAttribute("y", y);
      px.setAttribute("width", 1); px.setAttribute("height", 1);
      px.setAttribute("fill", CORES[c]);
      svgPixels.append(px);
    }));
  }

  const INTERVALO = 5 * 60 * 1000;  // procura novidades a cada 5 minutos
  const CHAVE_NOTICIAS = "magnobag-noticias-vistas";
  const CHAVE_DIA = "magnobag-avisos-do-dia";
  let fila = [];
  let posicao = 0;

  // guarda no navegador o que já foi mostrado, pra não repetir a mesma coisa toda hora
  function ler(chave) {
    try { return JSON.parse(localStorage.getItem(chave)) || {}; } catch { return {}; }
  }
  function salvar(chave, valor) {
    try { localStorage.setItem(chave, JSON.stringify(valor)); } catch { /* modo privado */ }
  }
  const hoje = new Date().toISOString().slice(0, 10);

  function eNovo(aviso) {
    if (aviso.tipo === "noticia") {
      const vistas = ler(CHAVE_NOTICIAS);
      return !vistas[aviso.ticker] || aviso.data > vistas[aviso.ticker];
    }
    const dia = ler(CHAVE_DIA);
    return !(dia.data === hoje && (dia.textos || []).includes(aviso.texto));
  }

  function marcarVisto(aviso) {
    if (aviso.tipo === "noticia") {
      const vistas = ler(CHAVE_NOTICIAS);
      vistas[aviso.ticker] = aviso.data;
      salvar(CHAVE_NOTICIAS, vistas);
    } else {
      const dia = ler(CHAVE_DIA);
      const textos = dia.data === hoje ? dia.textos || [] : [];
      if (!textos.includes(aviso.texto)) textos.push(aviso.texto);
      salvar(CHAVE_DIA, { data: hoje, textos });
    }
  }

  function humor(nome) {
    mascote.classList.remove("feliz", "triste", "alerta", "noticia", "calmo", "relogio");
    mascote.classList.add(nome || "calmo");
    desenhar(nome || "calmo");
    // pulinho a cada fala
    mascote.classList.remove("pulando");
    void mascote.offsetWidth;
    mascote.classList.add("pulando");
  }

  function mostrar(i) {
    const aviso = fila[i];
    if (!aviso) return;
    posicao = i;
    humor(aviso.humor);
    texto.textContent = aviso.texto;
    link.hidden = !aviso.link;
    if (aviso.link) link.href = aviso.link;
    contador.textContent = fila.length > 1 ? `${i + 1} de ${fila.length} · toque em mim pro próximo` : "";
    balao.hidden = false;
    marcarVisto(aviso);
    bolinha.hidden = !fila.slice(i + 1).some(eNovo);
  }

  async function atualizar(abrirSeTiverNovidade) {
    try {
      const r = await fetch("/api/mascote");
      if (!r.ok) return;
      fila = await r.json();
    } catch {
      return;
    }
    if (!fila.length) {
      fila = [{ humor: "calmo", texto: "Adicione ativos no painel que eu fico de olho neles pra você." }];
    }
    const primeiroNovo = fila.findIndex(eNovo);
    bolinha.hidden = primeiroNovo < 0;
    if (abrirSeTiverNovidade && primeiroNovo >= 0) mostrar(primeiroNovo);
    else humor(fila[0].humor);
  }

  corpo.addEventListener("click", () => {
    if (balao.hidden) mostrar(fila.findIndex(eNovo) >= 0 ? fila.findIndex(eNovo) : 0);
    else mostrar((posicao + 1) % fila.length);
  });
  document.getElementById("balaoFechar").addEventListener("click", () => { balao.hidden = true; });

  desenhar("calmo");
  atualizar(true);
  setInterval(() => atualizar(true), INTERVALO);
})();
