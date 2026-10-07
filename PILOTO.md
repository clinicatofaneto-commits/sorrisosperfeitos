# Piloto: vídeo do YouTube do Dr. Thiago

Roteiro de trabalho para montar o primeiro vídeo (piloto) e repetir nos próximos.
Quem executa: uma sessão do Claude rodando **no PC de edição**, aberta na pasta
`C:\Users\User\Desktop\GABRIELFILMMAKER\2026\10 - OUTUBRO\TOFA\YTBE`, que é onde estão o
material bruto e o roteiro.

## O que o piloto entrega

- **Projeto do Premiere em `YTBE\PROJETO`**, importado de um XML gerado aqui:
  - `TOFA_YT_PILOTO_16x9`: a montagem do YouTube, dinâmica, **sem legenda**, com o material em
    **log** (sem LUT) e faixas de áudio vazias para a música e os efeitos.
  - `REELS_XX_9x16`: uma sequência vertical para cada sugestão de recorte do roteiro, **com
    legenda** palavra a palavra.
  - Gráficos em preto e branco no estilo da vinheta: a vinheta de apresentação, os títulos 3D
    (página branca ou por cima do vídeo) e os elementos do gancho.
- **`YTBE\PROJETO\ENTREGA.md`**: sugestões de título, thumbnail (PNG) e copy.

## Pastas

```
YTBE\
  (material bruto e roteiro, como estão)
  PROJETO\
    FERRAMENTAS\           ← este repositório
    TRANSCRICAO\           ← .txt / .palavras.json / .srt de cada arquivo bruto
    GRAFICOS\
      vinheta.mp4
      titulos\             ← T01.mp4 (página), T02.mov (overlay com alfa)...
      legendas\            ← REELS_01_9x16_legenda.mov, .srt
      thumbnail\
    montagem.json          ← todas as decisões de corte; o XML sai dele
    TOFA_YT_PILOTO.xml     ← importar no Premiere
    TOFA_YT_PILOTO.prproj  ← salvo pelo Premiere depois da importação
    ENTREGA.md
```

## Preparar o PC (uma vez)

```powershell
winget install Git.Git
winget install OpenJS.NodeJS.LTS
winget install Python.Python.3.12
winget install Gyan.FFmpeg
cd "C:\Users\User\Desktop\GABRIELFILMMAKER\2026\10 - OUTUBRO\TOFA\YTBE\PROJETO"
git clone -b claude/thiago-presentation-video-cm3phk https://github.com/clinicatofaneto-commits/sorrisosperfeitos FERRAMENTAS
cd FERRAMENTAS
npm install
npx playwright install chromium
pip install faster-whisper
```

A transcrição roda na CPU. Com placa NVIDIA ela fica bem mais rápida: siga as instruções de
GPU do faster-whisper e use `--dispositivo cuda`.

Nos comandos abaixo, `$P` é a pasta `PROJETO`:
`$P = "C:\Users\User\Desktop\GABRIELFILMMAKER\2026\10 - OUTUBRO\TOFA\YTBE\PROJETO"`.

## Passo a passo

### 1. Ler o roteiro

Separe o gancho, a apresentação, os blocos do meio, as frases de destaque, as sugestões de
Reels e a chamada final. O vídeo segue a ordem do roteiro, mas o que vale é o que o Thiago
**falou**: o texto do roteiro serve para achar os takes, não para corrigir a fala.

### 2. Transcrever o bruto

```powershell
python scripts\transcrever.py "<pasta do bruto>" --saida "$P\TRANSCRICAO"
```

O `.txt` de cada arquivo mostra `[mm:ss.s-mm:ss.s] (dB) texto`. Na gravação, quem dirige lê a
frase e o Thiago repete. A voz de quem dirige aparece com volume bem menor (fora do microfone
dele) e vem logo antes da repetição. **Corte sempre a voz de quem dirige.**

### 3. Escolher os takes e cortar os respiros

Para cada fala do roteiro, ache as repetições do Thiago e fique com a melhor tomada completa,
que costuma ser a última. Cada corte vira um item do `v1` no `montagem.json`:

- `entrada`: cerca de 0,08 s antes da primeira palavra (use o `.palavras.json`).
- `saida`: de 0,12 a 0,2 s depois da última palavra, para o respiro ficar limpo, sem
  inspiração, "é...", repetição nem olhar para o roteiro.
- Frases da mesma tomada que fluem bem ficam num corte só.

### 4. Ritmo da montagem

- **Gancho (0 a 30 s)**, a parte mais dinâmica:
  - cortes de 1 a 3 s;
  - zoom alternado a cada corte (`1`, `1.15`, `1.25`);
  - zoom animado (`[1, 1.12]`) nas frases de impacto;
  - uma página branca com a frase principal do gancho;
  - títulos por cima do vídeo (overlay) acompanhando as palavras-chave, que são os
    "elementos que conduzem a fala".
- **Depois do gancho**: um corte por ideia; zoom de pontuação (`1.12`) nas frases fortes; uma
  página ou título a cada 20 a 40 s, nas frases de destaque do roteiro.
- **Apresentação**: a vinheta de 15 s entra na faixa 2, por cima da fala em que ele se
  apresenta, e o áudio dele continua. Renderize na taxa de quadros do projeto:
  `node scripts\render.js 29.97 "$P\GRAFICOS\vinheta.mp4"`.
- **Sem legenda no YouTube.** Sem transições de dissolver: os cortes são secos, e as
  transições (íris e wipe) ficam por conta dos gráficos.

### 5. Títulos 3D e páginas

Edite `youtube\dados\frases.js` com as frases reais. O comentário no topo do arquivo explica
os campos. Use `*palavra*` para a palavra em itálico no bloco invertido e coloque a duração
igual ao tempo da fala. Para ver uma prévia, abra `youtube\titulos.html?id=T01` no navegador.
Depois renderize:

```powershell
node scripts\render-titulos.js --fps 29.97 --saida "$P\GRAFICOS\titulos"
```

- `pagina` (MP4): vai na faixa 2 e cobre o Thiago enquanto a voz dele continua.
- `overlay` (MOV com alfa): vai na faixa 3, por cima dele.

### 6. Reels

Faça uma sequência vertical (`"largura": 1080, "altura": 1920`) para cada sugestão de recorte
do roteiro, de 30 a 60 s, abrindo com a frase mais forte. Liste em `destaques` as palavras que
devem sair em itálico. Depois:

```powershell
python scripts\legendas_reels.py "$P\montagem.json" --srt "$P\GRAFICOS\legendas"
node scripts\render-legendas.js --fps 29.97 --saida "$P\GRAFICOS\legendas"
```

Coloque cada `<nome>_legenda.mov` na faixa 2 do seu Reel (`"em": 0`). A vinheta de inscrição
no canal não entra nos Reels.

### 7. Gerar o projeto

```powershell
python scripts\premiere_xml.py "$P\montagem.json" "$P\TOFA_YT_PILOTO.xml"
```

No Premiere: **Arquivo > Importar** o XML e salve o projeto como
`$P\TOFA_YT_PILOTO.prproj`. Veja um exemplo completo de `montagem.json` em
`youtube\dados\montagem-exemplo.json`. Nas mídias, basta o caminho do `arquivo`; resolução,
taxa de quadros, duração e canais o script lê sozinho.

### 8. Conferir na primeira importação (só no piloto)

- **Zoom animado**: deve começar e terminar no corte certo. Se aparecer deslocado, gere o XML
  de novo com `--kf-base clipe`.
- **Reels**: confira se o enquadramento ficou centrado. Se o Thiago ficar fora do quadro,
  ajuste a `posicao` do corte.
- **Áudio**: a voz deve sair nos dois canais.
- **Gráficos com transparência**: os MOV devem aparecer por cima do vídeo, sem fundo preto.

Anote neste arquivo o que precisou mudar, para os próximos vídeos já saírem certos.

### 9. Cor e música (ficam com o editor)

- O material fica em **log**. Aplique a LUT no clipe mestre: no painel Projeto, abra o arquivo
  bruto no Controle de Efeitos e aplique a Lumetri, que passa a valer para todos os cortes dele.
  Também dá para aplicar clipe a clipe na faixa 1. Não use camada de ajuste por cima: os
  gráficos estão da faixa 2 para cima e **não** podem receber a LUT.
- As duas faixas de áudio vazias abaixo da voz ficam para a música e os efeitos sonoros.

### 10. Título, thumbnail e copy

Entregue tudo em `ENTREGA.md`:

- **Título**: até cerca de 60 caracteres, com a promessa do vídeo e sem entregar a resposta.
  Dê três opções.
- **Thumbnail**: uma ideia só, de no máximo 4 palavras, com o rosto do Thiago em close.
  Use preto e branco no estilo da vinheta. Exporte um quadro forte do bruto
  (`ffmpeg -ss <segundos> -i <video> -frames:v 1 youtube\thumb.jpg`), preencha
  `youtube\dados\thumbnail.js` com duas ou três opções e gere as imagens:
  `node scripts\render-thumbnail.js --saida "$P\GRAFICOS\thumbnail"`.
- **Copy**: as duas primeiras linhas fazem o gancho, seguidas de um resumo do que o vídeo
  responde, capítulos com minutagem tirada da montagem, a chamada para se inscrever e
  ativar o sino, e o @thiagotofaneto.

## Replicar nos próximos vídeos

1. Crie a pasta `PROJETO` do novo vídeo e repita os passos 2 a 7.
2. Reaproveite o `montagem.json` e o `frases.js` do piloto como ponto de partida.
3. A vinheta só precisa ser renderizada de novo se mudar o texto ou a taxa de quadros.
