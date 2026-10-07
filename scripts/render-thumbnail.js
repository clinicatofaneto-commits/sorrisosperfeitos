// Gera as thumbnails de youtube/dados/thumbnail.js em JPG 1280×720, uma por opção.
//   node scripts/render-thumbnail.js [--saida pasta] [A B ...]
const path = require("path");
const { abrirNavegador, capturar, lerDados, lerArgumentos } = require("./lib/render-frames");

const { opcoes, resto } = lerArgumentos(process.argv.slice(2));
const raiz = path.join(__dirname, "..");
const thumbs = lerDados(path.join(raiz, "youtube/dados/thumbnail.js"), "THUMBS");
const pasta = opcoes.saida || path.join(raiz, "youtube/render/thumbnail");
const escolhidas = resto.length ? thumbs.filter((t) => resto.includes(t.id)) : thumbs;

(async () => {
  const browser = await abrirNavegador();
  for (const t of escolhidas) {
    const saida = path.join(pasta, `thumbnail-${t.id}.jpg`);
    await capturar(browser, { html: path.join(raiz, "youtube/thumbnail.html"), query: "id=" + encodeURIComponent(t.id), saida });
    console.log(`${t.id} → ${saida}`);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
