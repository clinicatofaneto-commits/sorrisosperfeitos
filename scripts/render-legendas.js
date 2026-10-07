// Renderiza as legendas dos Reels de youtube/dados/legendas.js em MOV com alfa (1080×1920),
// um arquivo por Reel, para ir na faixa acima do vídeo na sequência vertical.
//   node scripts/render-legendas.js [--fps 29.97] [--saida pasta] [R01 R02 ...]
const path = require("path");
const { abrirNavegador, renderizar, lerDados, lerArgumentos } = require("./lib/render-frames");

const { opcoes, resto } = lerArgumentos(process.argv.slice(2));
const raiz = path.join(__dirname, "..");
const legendas = lerDados(path.join(raiz, "youtube/dados/legendas.js"), "LEGENDAS");
const fps = opcoes.fps || 30;
const pasta = opcoes.saida || path.join(raiz, "youtube/render/legendas");
const ids = resto.length ? resto : Object.keys(legendas);

(async () => {
  const browser = await abrirNavegador();
  for (const id of ids) {
    const saida = path.join(pasta, `${id}_legenda.mov`);
    const r = await renderizar(browser, { html: path.join(raiz, "youtube/legendas-reels.html"), query: "id=" + encodeURIComponent(id), fps, saida });
    console.log(`${id}: ${r.quadros} quadros → ${saida}`);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
