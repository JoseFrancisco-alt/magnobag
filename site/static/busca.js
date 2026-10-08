// Busca de ativos pelo nome no painel: mostra sugestões enquanto digita e adiciona com um clique.
(() => {
  const campo = document.getElementById("buscaCampo");
  if (!campo) return;
  const lista = document.getElementById("buscaLista");
  const form = document.getElementById("buscaForm");
  let resultados = [];
  let marcado = -1;
  let espera = null;
  let ultimaBusca = "";

  function escolher(item) {
    document.getElementById("buscaTicker").value = item.ticker;
    document.getElementById("buscaNome").value = item.nome;
    campo.disabled = true;
    lista.innerHTML = '<li class="busca-info">Adicionando…</li>';
    form.submit();
  }

  function marcar(i) {
    marcado = i;
    [...lista.children].forEach((li, j) => li.setAttribute("aria-selected", j === i ? "true" : "false"));
  }

  function mostrar(itens, texto) {
    resultados = itens;
    marcado = -1;
    lista.replaceChildren();
    if (!itens.length) {
      const vazio = document.createElement("li");
      vazio.className = "busca-info";
      vazio.textContent = `Nada encontrado para "${texto}". Tente outro nome.`;
      lista.append(vazio);
    }
    itens.forEach((item, i) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      const codigo = document.createElement("b");
      codigo.textContent = item.ticker.replace(".SA", "");
      const nome = document.createElement("span");
      nome.textContent = item.nome;
      const tipo = document.createElement("small");
      tipo.textContent = item.tipo;
      li.append(codigo, nome, tipo);
      li.addEventListener("mousedown", (e) => { e.preventDefault(); escolher(item); });
      li.addEventListener("mousemove", () => marcar(i));
      lista.append(li);
    });
    lista.hidden = false;
  }

  async function buscar() {
    const texto = campo.value.trim();
    if (texto.length < 2) { lista.hidden = true; return; }
    if (texto === ultimaBusca) return;
    ultimaBusca = texto;
    lista.innerHTML = '<li class="busca-info">Procurando…</li>';
    lista.hidden = false;
    try {
      const r = await fetch(`/api/buscar?q=${encodeURIComponent(texto)}`);
      const itens = await r.json();
      if (campo.value.trim() === texto) mostrar(Array.isArray(itens) ? itens : [], texto);
    } catch {
      lista.innerHTML = '<li class="busca-info">Não consegui buscar agora. Tente de novo.</li>';
    }
  }

  campo.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(buscar, 300);  // espera parar de digitar
  });
  campo.addEventListener("keydown", (e) => {
    if (lista.hidden || !resultados.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); marcar((marcado + 1) % resultados.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); marcar((marcado - 1 + resultados.length) % resultados.length); }
    else if (e.key === "Enter") { e.preventDefault(); escolher(resultados[Math.max(marcado, 0)]); }
    else if (e.key === "Escape") { lista.hidden = true; }
  });
  campo.addEventListener("blur", () => setTimeout(() => { lista.hidden = true; }, 150));
  campo.addEventListener("focus", () => { if (resultados.length && campo.value.trim().length >= 2) lista.hidden = false; });
})();
