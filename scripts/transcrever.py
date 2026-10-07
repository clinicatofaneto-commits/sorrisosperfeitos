#!/usr/bin/env python3
"""Transcreve o material bruto com tempo por palavra (faster-whisper), para achar takes e cortes.

    pip install faster-whisper
    python scripts/transcrever.py VIDEO_OU_PASTA [...] [--modelo medium] [--dispositivo auto|cpu|cuda] [--saida PASTA]

Para cada vídeo grava (ao lado dele, ou em --saida):
  NOME.palavras.json  segmentos com início/fim, volume (dB) e as palavras com tempo
  NOME.txt            leitura rápida: [mm:ss.s-mm:ss.s] (dB) texto, para escolher os takes
  NOME.srt            legenda do bruto inteiro, só como referência
O volume ajuda a separar quem fala: a voz do Thiago, no microfone dele, vem mais alta que a
de quem lê o roteiro atrás da câmera.
"""
import argparse
import json
from pathlib import Path

VIDEOS = {".mp4", ".mov", ".mxf", ".mts", ".m4v", ".avi", ".wav", ".mp3", ".m4a"}
PROMPT = ("Dr. Thiago Tofaneto, cirurgião-dentista. Lente de contato dental, facetas de porcelana, "
          "resina, planejamento digital do sorriso, harmonização, clínica Sorrisos Perfeitos.")


def mmss(t):
    """75.3 → '01:15.3'"""
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


def srt_tempo(t):
    """75.3 → '00:01:15,300'"""
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def volume_db(trecho):
    import numpy as np
    if len(trecho) == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(trecho, dtype="float64"))))
    return round(20 * np.log10(max(rms, 1e-6)), 1)


def ler_audio(arquivo):
    """Áudio em mono, 16 kHz, float32 — decodificado pelo ffmpeg (mais estável que o PyAV)."""
    import subprocess
    import numpy as np
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-i", str(arquivo), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                           capture_output=True, check=True).stdout
    return np.frombuffer(bruto, dtype=np.float32)


def transcrever(modelo, arquivo, pasta, idioma):
    audio = ler_audio(arquivo)
    segmentos, _ = modelo.transcribe(
        audio, language=idioma, word_timestamps=True, vad_filter=True, beam_size=5,
        condition_on_previous_text=False,  # o roteiro é repetido várias vezes; isso evita o modelo "pular" repetições
        initial_prompt=PROMPT,
    )
    saida = []
    for s in segmentos:
        saida.append({
            "i": round(s.start, 3), "f": round(s.end, 3),
            "db": volume_db(audio[int(s.start * 16000):int(s.end * 16000)]),
            "texto": s.text.strip(),
            "palavras": [{"p": w.word.strip(), "i": round(w.start, 3), "f": round(w.end, 3), "prob": round(w.probability, 3)}
                         for w in (s.words or [])],
        })
        print(f"  [{mmss(s.start)}] {s.text.strip()[:90]}")

    base = Path(pasta) / Path(arquivo).stem
    Path(f"{base}.palavras.json").write_text(json.dumps({"arquivo": str(arquivo), "segmentos": saida}, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(f"{base}.txt").write_text(
        "\n".join(f"[{mmss(s['i'])}-{mmss(s['f'])}] ({s['db']:.0f} dB) {s['texto']}" for s in saida) + "\n", encoding="utf-8")
    Path(f"{base}.srt").write_text(
        "\n".join(f"{n}\n{srt_tempo(s['i'])} --> {srt_tempo(s['f'])}\n{s['texto']}\n" for n, s in enumerate(saida, 1)), encoding="utf-8")
    return len(saida)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("entradas", nargs="+", help="vídeos ou pastas com vídeos")
    ap.add_argument("--modelo", default="medium", help="tiny, base, small, medium, large-v3 (padrão: medium)")
    ap.add_argument("--dispositivo", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--saida", help="pasta para os arquivos gerados (padrão: ao lado de cada vídeo)")
    args = ap.parse_args()

    arquivos = []
    for e in map(Path, args.entradas):
        arquivos += sorted(p for p in e.iterdir() if p.suffix.lower() in VIDEOS) if e.is_dir() else [e]

    from faster_whisper import WhisperModel
    dispositivo = args.dispositivo
    if dispositivo == "auto":
        import ctranslate2
        dispositivo = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
    modelo = WhisperModel(args.modelo, device=dispositivo, compute_type="float16" if dispositivo == "cuda" else "int8")
    for arq in arquivos:
        pasta = Path(args.saida) if args.saida else arq.parent
        pasta.mkdir(parents=True, exist_ok=True)
        print(f"{arq.name} ({dispositivo}, {args.modelo})")
        print(f"  {transcrever(modelo, arq, pasta, args.idioma)} segmentos → {pasta / arq.stem}.txt")


if __name__ == "__main__":
    main()
