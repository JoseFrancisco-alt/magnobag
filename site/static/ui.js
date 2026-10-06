// Microinterações do site inteiro: blocos que aparecem ao rolar e cartões que inclinam com o mouse.
const reduzMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Blocos .painel-bloco surgem do desfoque quando entram na tela
function revelarAoRolar(raiz = document) {
  // blocos escondidos (ex.: antes dos dados carregarem) ficam para quando aparecerem
  const blocos = [...raiz.querySelectorAll(".painel-bloco:not(.revelar)")].filter((b) => !b.closest("[hidden]"));
  if (reduzMovimento || !("IntersectionObserver" in window)) return;
  const observador = new IntersectionObserver((entradas) => {
    entradas.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("visivel");
        observador.unobserve(e.target);
      }
    });
  }, { threshold: 0.08 });
  blocos.forEach((bloco) => {
    bloco.classList.add("revelar");
    if (bloco.getBoundingClientRect().top < window.innerHeight * 0.95) {
      // já está na tela: aparece logo no próximo quadro, sem esperar rolar
      requestAnimationFrame(() => requestAnimationFrame(() => bloco.classList.add("visivel")));
      setTimeout(() => bloco.classList.add("visivel"), 120);
    } else {
      observador.observe(bloco);
    }
  });
}

// Tilt Card: o cartão inclina na direção do mouse e a luz segue o cursor
function ativarTilt(cartao) {
  if (reduzMovimento) return;
  // a animação de entrada prende o transform; depois que ela acaba, a inclinação assume
  cartao.addEventListener("animationend", () => cartao.classList.remove("blur-reveal"), { once: true });
  cartao.addEventListener("pointermove", (e) => {
    const r = cartao.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    cartao.style.setProperty("--mx", `${x * 100}%`);
    cartao.style.setProperty("--my", `${y * 100}%`);
    cartao.style.setProperty("--ry", `${(x - 0.5) * 8}deg`);
    cartao.style.setProperty("--rx", `${(0.5 - y) * 8}deg`);
  });
  cartao.addEventListener("pointerleave", () => {
    cartao.style.setProperty("--rx", "0deg");
    cartao.style.setProperty("--ry", "0deg");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  revelarAoRolar();
  document.querySelectorAll(".cartao").forEach(ativarTilt);
});
