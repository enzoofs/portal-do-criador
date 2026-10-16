// Portal do Criador — modo apresentação do radar (slides 16:9).
// Navegação: setas, espaço, Page Up/Down, Home/End; clique na metade direita avança, na esquerda volta.
const palco = document.getElementById("palco");
const slides = [...document.querySelectorAll(".slide")];
const barra = document.getElementById("progresso");
let atual = Math.min(slides.length, Math.max(1, parseInt(location.hash.slice(1), 10) || 1)) - 1;

function escala() {
  const k = Math.min(innerWidth / 1600, innerHeight / 900);
  palco.style.transform = `scale(${k})`;
}
function mostrar(n) {
  atual = Math.max(0, Math.min(slides.length - 1, n));
  slides.forEach((s, i) => s.classList.toggle("ativo", i === atual));
  barra.style.width = `${(100 * (atual + 1)) / slides.length}%`;
  history.replaceState(null, "", `#${atual + 1}`);
}
document.addEventListener("keydown", (ev) => {
  if (["ArrowRight", "PageDown", " ", "Enter"].includes(ev.key)) { ev.preventDefault(); mostrar(atual + 1); }
  else if (["ArrowLeft", "PageUp", "Backspace"].includes(ev.key)) { ev.preventDefault(); mostrar(atual - 1); }
  else if (ev.key === "Home") mostrar(0);
  else if (ev.key === "End") mostrar(slides.length - 1);
  else if (ev.key.toLowerCase() === "f") {
    if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen();
  } else if (ev.key === "Escape" && !document.fullscreenElement) location.href = document.querySelector(".sair").href;
});
document.addEventListener("click", (ev) => {
  if (ev.target.closest("a")) return;
  mostrar(ev.clientX > innerWidth * 0.4 ? atual + 1 : atual - 1);
});
addEventListener("resize", escala);
escala();
mostrar(atual);
