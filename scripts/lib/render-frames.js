// Renderiza páginas HTML animadas com GSAP quadro a quadro e entrega os PNGs ao ffmpeg.
// Contrato da página (aberta com "?render"): window.renderReady, window.tl (timeline GSAP)
// e window.renderInfo = { width, height, duration, alpha }.
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const { pathToFileURL } = require("url");
const path = require("path");
const fs = require("fs");
const vm = require("vm");

const NTSC = { "23.976": "24000/1001", "29.97": "30000/1001", "59.94": "60000/1001" };
const fpsRatio = (fps) => NTSC[String(fps)] || String(fps);
const fpsNumber = (fps) => { const [n, d = 1] = fpsRatio(fps).split("/").map(Number); return n / d; };

// A extensão do arquivo de saída escolhe o codec.
const CODEC = {
  // H.264 para telas cheias (páginas, vinheta)
  ".mp4": ["-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-movflags", "+faststart"],
  // ProRes 4444 com canal alfa para o que vai por cima do vídeo
  ".mov": ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"],
};

function abrirNavegador() {
  return chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
}

// Lê um arquivo de dados do navegador (window.NOME = ...) sem abrir o navegador.
function lerDados(arquivo, nome) {
  const ctx = { window: {} };
  vm.runInNewContext(fs.readFileSync(arquivo, "utf8"), ctx, { filename: arquivo });
  return ctx.window[nome];
}

// Lê "--chave valor" e devolve { opcoes, resto }.
function lerArgumentos(argv) {
  const opcoes = {}, resto = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) opcoes[argv[i].slice(2)] = argv[++i];
    else resto.push(argv[i]);
  }
  return { opcoes, resto };
}

async function renderizar(browser, { html, query = "", fps = 30, saida }) {
  const codec = CODEC[path.extname(saida).toLowerCase()];
  if (!codec) throw new Error(`extensão não suportada: ${saida} (use .mp4 ou .mov)`);
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  try {
    await page.goto(pathToFileURL(path.resolve(html)).href + "?render" + (query ? "&" + query : ""), { waitUntil: "load" });
    await page.waitForFunction(() => window.renderReady && [...document.images].every((img) => img.complete));
    const info = await page.evaluate(() =>
      window.renderInfo || { width: 1920, height: 1080, duration: window.tl.duration(), alpha: false });
    await page.setViewportSize({ width: info.width, height: info.height });

    fs.mkdirSync(path.dirname(path.resolve(saida)), { recursive: true });
    const ffmpeg = spawn("ffmpeg", [
      "-y", "-loglevel", "error",
      "-f", "image2pipe", "-c:v", "png", "-framerate", fpsRatio(fps), "-i", "-",
      ...codec, saida,
    ], { stdio: ["pipe", "inherit", "inherit"] });
    const fim = new Promise((resolve, reject) =>
      ffmpeg.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg saiu com ${code}`)))));

    const quadros = Math.round(info.duration * fpsNumber(fps));
    for (let i = 0; i < quadros; i++) {
      await page.evaluate((t) => { window.tl.seek(t, false); }, i / fpsNumber(fps));
      const png = await page.screenshot({ type: "png", omitBackground: info.alpha });
      if (!ffmpeg.stdin.write(png)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
    }
    ffmpeg.stdin.end();
    await fim;
    return { quadros, ...info };
  } finally {
    await page.close();
  }
}

// Captura um único quadro (thumbnail). A extensão de `saida` escolhe o formato (.jpg ou .png).
async function capturar(browser, { html, query = "", saida }) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  try {
    await page.goto(pathToFileURL(path.resolve(html)).href + "?render" + (query ? "&" + query : ""), { waitUntil: "load" });
    await page.waitForFunction(() => window.renderReady && [...document.images].every((img) => img.complete));
    const info = await page.evaluate(() => window.renderInfo);
    await page.setViewportSize({ width: info.width, height: info.height });
    fs.mkdirSync(path.dirname(path.resolve(saida)), { recursive: true });
    const jpg = /\.jpe?g$/i.test(saida);
    await page.screenshot({ path: saida, type: jpg ? "jpeg" : "png", ...(jpg ? { quality: 92 } : {}) });
  } finally {
    await page.close();
  }
}

module.exports = { abrirNavegador, renderizar, capturar, lerDados, lerArgumentos, fpsRatio, fpsNumber };
