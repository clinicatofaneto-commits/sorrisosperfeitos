#!/usr/bin/env python3
"""Confere o montagem.json contra o roteiro e as transcrições, e ajusta os cortes e respiros.

    python scripts/revisar_montagem.py montagem.json --transcricao PASTA [--roteiro roteiro.txt|.docx]
                                       [--ajustar montagem_revisada.json] [--relatorio REVISAO.md]

Para cada sequência, lista os cortes do v1 na ordem, com o texto falado, e aponta:
  - material misturado: fala que não está no roteiro, ou arquivo bruto que é de outro roteiro;
  - ordem: corte que volta no roteiro (no vídeo do YouTube, que segue o roteiro);
  - roteiro sem take: trecho do roteiro que nenhum corte cobre;
  - corte no meio de uma palavra, respiro curto ou longo, pausa longa dentro do corte;
  - voz de quem dirige (trecho bem mais baixo que a média do arquivo) dentro do corte;
  - frase repetida dentro do corte ou usada em dois cortes;
  - Reel sem o título do assunto na abertura, ou fora de 30 a 60 s.

--ajustar grava uma cópia do JSON com os cortes do v1 refeitos pelas palavras:
  - entrada 0,08 s antes da primeira palavra e saída 0,15 s depois da última, sem encostar
    na palavra vizinha;
  - um corte com pausa longa vira cortes separados (id, id_b, id_c...), sem os pedaços que
    são só muleta ("é", "hã") ou voz de quem dirige;
  - se a mesma frase aparece duas vezes no corte, fica só a última tomada.
O resto (zoom, posição, faixas de cima, marcadores) não muda; o que estava preso ao corte
continua preso ao primeiro pedaço.

As transcrições são os NOME.palavras.json do transcrever.py, achados pelo nome do arquivo
bruto na pasta --transcricao (ou pelo campo "transcricao" da mídia).
"""
import argparse
import copy
import json
import re
import statistics
import unicodedata
import zipfile
from pathlib import Path

ANTES, DEPOIS = 0.08, 0.15          # respiro que o ajuste aplica
RESPIRO_ENTRADA = (0.03, 0.30)      # fora disso, avisa
RESPIRO_SAIDA = (0.08, 0.35)
PAUSA_LONGA = 0.6                   # silêncio dentro do corte que vale cortar
DIRETOR_DB = 8                      # quantos dB abaixo da mediana do arquivo conta como quem dirige
MULETAS = {"e", "eh", "a", "ha", "ah", "ahn", "hum", "hmm", "ta", "entao"}  # já sem acento, como sai do normal()


def normal(texto):
    """'Lente, de CONTATO!' → ['lente', 'de', 'contato']"""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", texto)


def mmss(t):
    m, s = divmod(max(t, 0), 60)
    return f"{int(m):02d}:{s:04.1f}"


def ler_roteiro(arquivo):
    """Parágrafos do roteiro (.txt, .md ou .docx), sem linhas vazias."""
    arquivo = Path(arquivo)
    if arquivo.suffix.lower() == ".docx":
        xml = zipfile.ZipFile(arquivo).read("word/document.xml").decode("utf-8")
        linhas = [re.sub(r"<[^>]+>", "", p) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)]
    else:
        linhas = arquivo.read_text(encoding="utf-8", errors="replace").splitlines()
    return [l.strip() for l in linhas if len(normal(l)) >= 3]


class Transcricao:
    def __init__(self, arquivo):
        dados = json.loads(Path(arquivo).read_text(encoding="utf-8"))
        segs = dados["segmentos"]
        mediana = statistics.median(s["db"] for s in segs) if segs else 0
        self.palavras = []
        for s in segs:
            diretor = s["db"] < mediana - DIRETOR_DB
            for w in s["palavras"]:
                self.palavras.append({**w, "diretor": diretor})
        self.segmentos = [{**s, "diretor": s["db"] < mediana - DIRETOR_DB} for s in segs]

    def no_corte(self, ent, sai):
        """Palavras com pelo menos 35% dentro do corte (a palavra cortada ao meio na ponta conta)."""
        return [w for w in self.palavras
                if min(w["f"], sai) - max(w["i"], ent) >= 0.35 * max(w["f"] - w["i"], 0.01)]

    def vizinhas(self, primeira, ultima):
        i, j = self.palavras.index(primeira), self.palavras.index(ultima)
        return (self.palavras[i - 1] if i > 0 else None), (self.palavras[j + 1] if j + 1 < len(self.palavras) else None)


def parecido(palavras, roteiro_tokens):
    """Melhor parágrafo do roteiro para uma fala: (índice, fração das palavras da fala que estão nele)."""
    fala = {p for p in palavras if len(p) > 2}
    if not fala or not roteiro_tokens:
        return None, 0.0
    notas = [len(fala & par) / len(fala) for par in roteiro_tokens]
    melhor = max(range(len(notas)), key=notas.__getitem__)
    return melhor, notas[melhor]


def repetida(tokens, n=4):
    vistos = set()
    for k in range(len(tokens) - n + 1):
        g = tuple(tokens[k:k + n])
        if g in vistos:
            return " ".join(g)
        vistos.add(g)
    return None


def muleta(w):
    return normal(w["p"]) in [[m] for m in MULETAS]


def refazer(tr, ws):
    """Entradas e saídas limpas para as palavras de um corte: [(entrada, saída), ...]."""
    grupos = [[ws[0]]]
    for a, b in zip(ws, ws[1:]):
        if b["i"] - a["f"] > PAUSA_LONGA:
            grupos.append([])
        grupos[-1].append(b)
    # fora: só muleta ou só quem dirige; nas pontas de cada grupo, também
    limpos = []
    for g in grupos:
        while g and (g[0]["diretor"] or muleta(g[0])):
            g = g[1:]
        while g and (g[-1]["diretor"] or muleta(g[-1])):
            g = g[:-1]
        if g:
            limpos.append(g)
    # mesma frase em duas tomadas: fica a mais completa (no empate, a última)
    falas = [{p for w in g for p in normal(w["p"]) if len(p) > 2} for g in limpos]
    finais = []
    for k, g in enumerate(limpos):
        a = falas[k]
        perde = any(a and b and len(a & b) / min(len(a), len(b)) > 0.7 and (len(b) > len(a) or (len(b) == len(a) and j > k))
                    for j, b in enumerate(falas) if j != k)
        if not perde:
            finais.append(g)
    cortes = []
    for g in finais:
        antes, depois = tr.vizinhas(g[0], g[-1])
        e = g[0]["i"] - ANTES
        if antes:
            e = max(e, antes["f"] + 0.02)
        s = g[-1]["f"] + DEPOIS
        if depois:
            s = min(s, depois["i"] - 0.03)
        cortes.append((e, s))
    return cortes


def revisar(dados, pasta_transcricao, roteiro, ajustar):
    fps = dados.get("fps", "29.97")
    transcricoes, avisos_gerais = {}, []
    for mid, m in dados["midias"].items():
        arq = m.get("transcricao") or (Path(pasta_transcricao) / (Path(str(m["arquivo"]).replace("\\", "/")).stem + ".palavras.json") if pasta_transcricao else None)
        if arq and Path(arq).exists():
            transcricoes[mid] = Transcricao(arq)

    roteiro_tokens = [set(p for p in normal(par) if len(p) > 2) for par in roteiro]

    # Arquivo bruto de outro roteiro: poucas falas do Thiago batem com o roteiro.
    if roteiro:
        for mid, tr in transcricoes.items():
            falas = [s for s in tr.segmentos if not s["diretor"] and len(normal(s["texto"])) >= 4]
            if falas:
                bate = sum(parecido(normal(s["texto"]), roteiro_tokens)[1] >= 0.5 for s in falas) / len(falas)
                if bate < 0.3:
                    avisos_gerais.append(f"**{mid}**: só {bate:.0%} das falas batem com o roteiro. Parece material de outro vídeo.")

    saida = ["# Revisão da montagem", ""]
    if avisos_gerais:
        saida += ["## Material", ""] + [f"- {a}" for a in avisos_gerais] + [""]
    revisado = copy.deepcopy(dados)
    ajustes = {}
    total_avisos = len(avisos_gerais)

    for n_seq, seq in enumerate(dados["sequencias"]):
        reels = seq.get("altura", 0) > seq.get("largura", 0)
        saida += [f"## {seq['nome']}", ""]
        usados, textos, ultimo_par, t_seq = set(), [], -1, 0.0
        for n, item in enumerate(seq.get("v1", [])):
            cid = item.get("id", n + 1)
            ent, sai = float(item.get("entrada", 0)), float(item.get("saida", 0))
            tr = transcricoes.get(item["midia"])
            linha = f"**{cid}** · {item['midia']} {mmss(ent)}–{mmss(sai)} · na timeline {mmss(t_seq)}"
            t_seq += sai - ent
            if not tr:
                saida += [f"- {linha} · sem transcrição", ""]
                continue
            ws = tr.no_corte(ent, sai)
            if not ws:
                saida += [f"- {linha} · ⚠ nenhuma palavra no corte", ""]
                total_avisos += 1
                continue
            avisos = []
            texto = " ".join(w["p"] for w in ws)
            tokens = normal(texto)

            # pontas: palavra cortada ao meio e respiro
            for w in tr.palavras:
                if w["i"] < ent < w["f"]:
                    avisos.append(f"entra no meio de \"{w['p']}\"")
                if w["i"] < sai < w["f"]:
                    avisos.append(f"sai no meio de \"{w['p']}\"")
            pre, pos = ws[0]["i"] - ent, sai - ws[-1]["f"]
            if not RESPIRO_ENTRADA[0] <= pre <= RESPIRO_ENTRADA[1]:
                avisos.append(f"respiro de entrada {pre:+.2f} s")
            if not RESPIRO_SAIDA[0] <= pos <= RESPIRO_SAIDA[1]:
                avisos.append(f"respiro de saída {pos:+.2f} s")
            for a, b in zip(ws, ws[1:]):
                if b["i"] - a["f"] > PAUSA_LONGA:
                    avisos.append(f"pausa de {b['i'] - a['f']:.1f} s em {mmss(a['f'])} (\"{a['p']} … {b['p']}\"): dividir o corte")
            if any(w["diretor"] for w in ws):
                d = " ".join(w["p"] for w in ws if w["diretor"])
                avisos.append(f"voz de quem dirige no corte: \"{d[:60]}\"")
            if muleta(ws[0]):
                avisos.append(f"começa com \"{ws[0]['p']}\"")
            if muleta(ws[-1]):
                avisos.append(f"termina com \"{ws[-1]['p']}\"")
            if (r := repetida(tokens)):
                avisos.append(f"frase repetida dentro do corte (\"{r}\"): sobrou outro take")
            fala = {p for p in tokens if len(p) > 2}
            for outro_id, outro in textos:
                if fala and len(fala & outro) / len(fala) > 0.7:
                    avisos.append(f"mesma fala do corte {outro_id}")
                    break
            textos.append((cid, fala))

            # roteiro: origem e ordem
            if roteiro:
                par, nota = parecido(tokens, roteiro_tokens)
                if nota < 0.5:
                    avisos.append("fala fora do roteiro (material de outro vídeo?)")
                else:
                    usados.add(par)
                    linha += f" · roteiro §{par + 1}"
                    if not reels and par < ultimo_par:
                        avisos.append(f"fora de ordem: volta do §{ultimo_par + 1} para o §{par + 1}")
                    ultimo_par = max(ultimo_par, par)

            saida.append(f"- {linha}")
            saida.append(f"  > {texto}")
            for a in avisos:
                saida.append(f"  - ⚠ {a}")
            total_avisos += len(avisos)

            if ajustar:
                pedacos = refazer(tr, ws)
                novos = []
                for k, (e, s_) in enumerate(pedacos):
                    novo = {**item, "entrada": round(e, 3), "saida": round(s_, 3)}
                    if k:
                        novo["id"] = f"{cid}_{chr(ord('a') + k)}"
                    novos.append(novo)
                ajustes[(n_seq, n)] = novos
                if [(round(e, 2), round(s_, 2)) for e, s_ in pedacos] != [(round(ent, 2), round(sai, 2))]:
                    saida.append("  - ✔ ajustado para " + (" + ".join(f"{mmss(e)}–{mmss(s_)}" for e, s_ in pedacos) or "nada (corte removido)"))

        if reels:
            if not (25 <= t_seq <= 65):
                saida.append(f"- ⚠ Reel com {t_seq:.0f} s (o alvo é 30 a 60 s)")
                total_avisos += 1
            if not any(x.get("em", None) == 0 or (x.get("no") == seq["v1"][0].get("id") and not x.get("desloc")) for x in seq.get("sobre", [])):
                saida.append("- ⚠ Reel sem o título do assunto na abertura")
                total_avisos += 1
        elif roteiro and n_seq == 0:
            faltam = [i for i in range(len(roteiro)) if i not in usados]
            if faltam:
                saida += ["", "**Trechos do roteiro sem corte** (confira se foram cortados de propósito):"]
                saida += [f"- §{i + 1}: {roteiro[i][:90]}" for i in faltam]
        saida += ["", f"Duração: {mmss(t_seq)}", ""]

    for n_seq, seq in enumerate(revisado["sequencias"]):
        v1 = []
        for n, item in enumerate(seq.get("v1", [])):
            v1 += ajustes.get((n_seq, n), [item])
        seq["v1"] = v1

    if roteiro:
        saida += ["## Roteiro numerado", ""] + [f"{i + 1}. {p}" for i, p in enumerate(roteiro)] + [""]
    saida.insert(2, f"{total_avisos} aviso(s).\n")
    return "\n".join(saida), revisado


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("montagem")
    ap.add_argument("--transcricao", help="pasta com os .palavras.json")
    ap.add_argument("--roteiro", help="roteiro em .txt, .md ou .docx")
    ap.add_argument("--ajustar", help="grava aqui o JSON com entradas e saídas recalculadas")
    ap.add_argument("--relatorio", help="grava o relatório em Markdown (padrão: só mostra)")
    args = ap.parse_args()
    dados = json.loads(Path(args.montagem).read_text(encoding="utf-8"))
    roteiro = ler_roteiro(args.roteiro) if args.roteiro else []
    relatorio, revisado = revisar(dados, args.transcricao, roteiro, bool(args.ajustar))
    if args.relatorio:
        Path(args.relatorio).write_text(relatorio, encoding="utf-8")
        print(f"relatório → {args.relatorio}")
    else:
        print(relatorio)
    if args.ajustar:
        Path(args.ajustar).write_text(json.dumps(revisado, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"montagem ajustada → {args.ajustar}")


if __name__ == "__main__":
    main()
