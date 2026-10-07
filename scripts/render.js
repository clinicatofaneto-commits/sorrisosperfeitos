// Renderiza a vinheta de apresentação (index.html) em MP4 1920×1080.
// Requer Node, o pacote "playwright" com Chromium e o ffmpeg no PATH (veja PILOTO.md).
//   node scripts/render.js                  → video/thiago-tofaneto-insert.mp4 a 30 fps
//   node scripts/render.js 29.97 saida.mp4  → outra taxa de quadros / outro arquivo
const path = require("path");
const { abrirNavegador, renderizar } = require("./lib/render-frames");

const fps = process.argv[2] || 30;
const saida = process.argv[3] || "video/thiago-tofaneto-insert.mp4";

(async () => {
  const browser = await abrirNavegador();
  const r = await renderizar(browser, { html: path.join(__dirname, "../index.html"), fps, saida });
  await browser.close();
  console.log(`${r.quadros} quadros → ${saida}`);
})().catch((e) => { console.error(e); process.exit(1); });
