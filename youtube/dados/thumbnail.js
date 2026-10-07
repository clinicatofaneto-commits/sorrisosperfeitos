// Thumbnails do vídeo. Um item por opção; cada um vira um JPG 1280×720 em scripts/render-thumbnail.js.
//   texto: "\n" quebra a linha; *palavra* vira o itálico serifado dentro do bloco invertido (máx. ~4 palavras)
//   foto:  caminho relativo a youtube/ (ex.: um quadro do bruto exportado com o ffmpeg)
//   foco:  ponto da foto que fica no centro do recorte, em % [x, y]
//   tag:   texto pequeno no canto (opcional)
// A opção abaixo é só um exemplo de estilo; troque pelo tema do vídeo.
window.THUMBS = [
  { id: "A", texto: "Não copie\no *sorriso*", foto: "../assets/thiago.jpg", foco: [45, 40], tag: "DR. THIAGO TOFANETO" },
];
