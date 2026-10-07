// Renderiza os títulos de youtube/dados/frases.js, um arquivo por título:
//   "pagina"  → <id>.mp4 (tela cheia)
//   "overlay" → <id>.mov (ProRes 4444 com alfa, vai numa faixa acima do vídeo)
//   node scripts/render-titulos.js [--fps 29.97] [--saida pasta] [T01 T02 ...]
const path = require("path");
const { abrirNavegador, renderizar, lerDados, lerArgumentos } = require("./lib/render-frames");

const { opcoes, resto } = lerArgumentos(process.argv.slice(2));
const raiz = path.join(__dirname, "..");
const frases = lerDados(path.join(raiz, "youtube/dados/frases.js"), "FRASES");
const fps = opcoes.fps || 30;
const pasta = opcoes.saida || path.join(raiz, "youtube/render/titulos");
const escolhidas = resto.length ? frases.filter((f) => resto.includes(f.id)) : frases;

(async () => {
  const browser = await abrirNavegador();
  for (const f of escolhidas) {
    const saida = path.join(pasta, f.id + (f.tipo === "overlay" ? ".mov" : ".mp4"));
    const r = await renderizar(browser, { html: path.join(raiz, "youtube/titulos.html"), query: "id=" + encodeURIComponent(f.id), fps, saida });
    console.log(`${f.id}: ${r.quadros} quadros → ${saida}`);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
