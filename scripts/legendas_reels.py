#!/usr/bin/env python3
"""Monta as legendas palavra a palavra dos Reels a partir da transcrição e da montagem.

    python scripts/legendas_reels.py montagem.json [--js youtube/dados/legendas.js] [--srt PASTA]

Cada sequência vertical (mais alta que larga) de montagem.json é um Reel. As palavras da
transcrição de cada mídia (campo "transcricao" da mídia: o NOME.palavras.json gerado por
scripts/transcrever.py) que caem dentro dos cortes do v1 são recolocadas no tempo do Reel.
Grava o arquivo lido por youtube/legendas-reels.html e um .srt por Reel, caso prefira
editar como legenda no Premiere. Palavras listadas em "destaques" na sequência saem no
itálico serifado. Depois: node scripts/render-legendas.js
"""
import argparse
import json
import re
from fractions import Fraction
from pathlib import Path

from premiere_xml import completar, quadros, taxa


def palavras(midia, cache):
    arquivo = midia.get("transcricao")
    if not arquivo:
        raise SystemExit(f"mídia sem \"transcricao\": {midia['arquivo']}")
    if arquivo not in cache:
        dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
        cache[arquivo] = [w for s in dados["segmentos"] for w in s["palavras"]]
    return cache[arquivo]


def legendar(seq, midias, fps, cache):
    destaques = {d.lower() for d in seq.get("destaques", [])}
    saida, t = [], 0  # t em quadros da sequência, com a mesma conta do premiere_xml.py
    for item in seq["v1"]:
        m = midias[item["midia"]]
        mfps = m.get("fps", fps)
        ent, sai = float(item.get("entrada", 0)), float(item.get("saida", m["duracao"]))
        inicio = Fraction(t) / taxa(fps)[2]
        for w in palavras(m, cache):
            if w["i"] >= ent - .05 and w["f"] <= sai + .1:
                p = w["p"]
                nucleo, pontuacao = re.match(r"^(.*?)([.,!?;:…]*)$", p).groups()
                if re.sub(r"\W", "", nucleo.lower()) in destaques:
                    p = f"*{nucleo}*{pontuacao}"
                saida.append({"p": p, "i": float(inicio) + max(0, w["i"] - ent), "f": float(inicio) + min(w["f"], sai) - ent})
        if taxa(mfps)[2] == taxa(fps)[2]:
            t += quadros(sai, mfps) - quadros(ent, mfps)
        else:
            t += quadros(Fraction(str(sai)) - Fraction(str(ent)), fps)
    return saida


def srt(ws, max_palavras=4):
    def tc(s):
        ms = round(s * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    blocos, atual = [], []
    for w in ws:
        atual.append(w)
        if len(atual) >= max_palavras or re.search(r"[.!?,;:]$", w["p"].replace("*", "")):
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    return "\n".join(f"{n}\n{tc(b[0]['i'])} --> {tc(b[-1]['f'])}\n{' '.join(w['p'].replace('*', '') for w in b)}\n"
                     for n, b in enumerate(blocos, 1))


def main():
    raiz = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("montagem")
    ap.add_argument("--js", default=str(raiz / "youtube/dados/legendas.js"))
    ap.add_argument("--srt", help="pasta para os .srt (padrão: ao lado do montagem.json)")
    args = ap.parse_args()

    dados = json.loads(Path(args.montagem).read_text(encoding="utf-8"))
    for m in dados["midias"].values():
        completar(m)
    reels, cache = {}, {}
    for seq in dados["sequencias"]:
        if seq["altura"] > seq["largura"]:
            reels[seq["nome"]] = legendar(seq, dados["midias"], str(dados["fps"]), cache)

    linhas = ["// Legendas dos Reels, palavra a palavra (gerado por scripts/legendas_reels.py).",
              "//   p: palavra (*palavra* = itálico serifado), i: início, f: fim, em segundos a partir do início do Reel",
              "window.LEGENDAS = {"]
    for nome, ws in reels.items():
        linhas.append(f"  {json.dumps(nome)}: [")
        linhas += [f"    {{ p: {json.dumps(w['p'], ensure_ascii=False)}, i: {w['i']:.2f}, f: {w['f']:.2f} }}," for w in ws]
        linhas.append("  ],")
    linhas.append("};")
    Path(args.js).write_text("\n".join(linhas) + "\n", encoding="utf-8")

    pasta_srt = Path(args.srt) if args.srt else Path(args.montagem).parent
    pasta_srt.mkdir(parents=True, exist_ok=True)
    for nome, ws in reels.items():
        (pasta_srt / f"{nome}.srt").write_text(srt(ws), encoding="utf-8")
        print(f"{nome}: {len(ws)} palavras → {args.js} e {pasta_srt / (nome + '.srt')}")


if __name__ == "__main__":
    main()
