// Renderiza index.html em MP4 1920×1080 quadro a quadro (sem perder frames).
// Requer Node, o pacote "playwright" com Chromium e o ffmpeg no PATH.
//   node scripts/render.js                  → video/thiago-tofaneto-insert.mp4 a 30 fps
//   node scripts/render.js 60 saida-60.mp4  → outra taxa de quadros / outro arquivo
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const { pathToFileURL } = require("url");
const path = require("path");
const fs = require("fs");

const FPS = Number(process.argv[2] || 30);
const OUT = path.resolve(process.argv[3] || "video/thiago-tofaneto-insert.mp4");
const DURATION = 15;

(async () => {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(pathToFileURL(path.resolve(__dirname, "../index.html")).href + "?render", { waitUntil: "load" });
  await page.waitForFunction(() => window.renderReady && [...document.images].every((img) => img.complete));

  const ffmpeg = spawn("ffmpeg", [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-c:v", "png", "-framerate", String(FPS), "-i", "-",
    "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
    "-c:v", "libx264", "-preset", "slow", "-crf", "16",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-movflags", "+faststart",
    OUT,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((resolve, reject) =>
    ffmpeg.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg saiu com ${code}`)))));

  const frames = Math.round(DURATION * FPS);
  for (let i = 0; i < frames; i++) {
    await page.evaluate((t) => { window.tl.seek(t, false); }, i / FPS);
    const png = await page.screenshot({ type: "png" });
    if (!ffmpeg.stdin.write(png)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
    if (i % FPS === 0) process.stdout.write(`\r${i}/${frames}`);
  }
  ffmpeg.stdin.end();
  await done;
  await browser.close();
  console.log(`\r${frames}/${frames} → ${OUT}`);
})();
