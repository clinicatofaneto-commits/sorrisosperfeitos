// Títulos do vídeo. Um item por título; cada um vira um arquivo em scripts/render-titulos.js.
//   tipo:    "pagina"  → tela cheia, sem o Thiago (MP4)
//            "overlay" → fundo transparente, por cima do vídeo (MOV ProRes 4444 com alfa)
//   texto:   "\n" quebra a linha; *palavra* vira o itálico serifado dentro do bloco invertido
//   duracao: segundos (casar com o tempo da fala)
//   fundo:   só em "pagina": "branco" (padrão) ou "preto"
//   lado:    só em "overlay": "esquerda" (padrão), "direita", "centro" ou "baixo"
//   saida:   anima a saída no fim (padrão: sim no overlay, não na página)
// As frases abaixo são exemplos de estilo; troque pelas falas reais do vídeo.
window.FRASES = [
  { id: "T01", tipo: "pagina", duracao: 3.5, texto: "Um sorriso bonito\nnão é *cópia*." },
  { id: "T02", tipo: "pagina", fundo: "preto", duracao: 3.5, texto: "Cada rosto pede\num *desenho*." },
  { id: "T03", tipo: "overlay", lado: "esquerda", duracao: 3.5, texto: "Lente de contato\né *planejamento*." },
];
