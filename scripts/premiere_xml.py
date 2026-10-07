#!/usr/bin/env python3
"""Gera um XML do Final Cut Pro 7 (xmeml) que o Premiere importa como sequências prontas.

    python scripts/premiere_xml.py montagem.json saida.xml [--kf-base midia|clipe]

No Premiere: Arquivo > Importar > saida.xml. Cada sequência do JSON vira uma sequência no
projeto, com as mídias originais (em log, sem LUT) e os gráficos nas faixas de cima.

montagem.json (exemplo completo em youtube/dados/montagem-exemplo.json):
  fps        taxa da sequência: "23.976", "24", "25", "29.97", "30", "59.94" ou "60"
  midias     { id: { arquivo, alfa?, transcricao?, largura?, altura?, fps?, duracao (s)?, canais? } }
             o que faltar (largura, altura, fps, duração, canais) é lido do arquivo pelo ffprobe
  sequencias [ { nome, largura, altura, v1, sobre, marcadores, audio_vazias } ]
    v1          cortes do vídeo principal, colados um depois do outro; o áudio vai junto em A1/A2
                { id?, midia, entrada (s), saida (s), zoom?, posicao? }
    sobre       o que fica por cima (vinheta, páginas, títulos, legendas, elementos)
                { faixa (2, 3...), midia, entrada?, saida?, em (s) | no (id de um corte do v1) + desloc?, zoom?, posicao? }
    marcadores  [ { em (s) | no + desloc?, nome, nota? } ]
    audio_vazias  quantas faixas de áudio vazias criar depois da voz (música, efeitos)
  zoom      1 = preenche o quadro; 1.15 = 15% mais perto; [1, 1.2] = zoom animado do início ao fim do corte
  posicao   [x, y] em pixels da sequência, a partir do centro, y positivo para baixo (reenquadrar)

--kf-base diz como o Premiere conta o tempo dos keyframes de zoom: "midia" (a partir do
início do arquivo, padrão) ou "clipe" (a partir do início do corte). Confira no primeiro
zoom animado do piloto; se o movimento aparecer deslocado, gere de novo com a outra opção.
"""
import argparse
import json
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote

NTSC = {"23.976": 24, "29.97": 30, "59.94": 60}
NOMES_FPS = {"24000/1001": "23.976", "30000/1001": "29.97", "60000/1001": "59.94"}


def taxa(fps):
    """'29.97' → (timebase 30, ntsc True, 30000/1001 quadros por segundo)."""
    fps = str(fps)
    if fps in NTSC:
        return NTSC[fps], True, Fraction(NTSC[fps] * 1000, 1001)
    tb = round(float(fps))
    return tb, False, Fraction(tb)


def quadros(segundos, fps):
    return round(Fraction(str(segundos)) * taxa(fps)[2])


def pathurl(arquivo):
    """C:/Pasta Com Espaço/a.mp4 → file://localhost/C%3a/Pasta%20Com%20Espa%C3%A7o/a.mp4"""
    caminho = str(arquivo).replace("\\", "/")
    if len(caminho) > 1 and caminho[1] == ":":
        return "file://localhost/" + quote(caminho[0] + ":", safe="").replace("%3A", "%3a") + quote(caminho[2:])
    return "file://localhost" + quote(str(Path(caminho).resolve()).replace("\\", "/"))


def completar(m):
    """Preenche largura, altura, fps, duração e canais pelo ffprobe quando faltarem no JSON."""
    if all(k in m for k in ("largura", "altura", "fps", "duracao", "canais")):
        return
    import subprocess
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,channels:format=duration",
         "-of", "json", str(m["arquivo"])], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    m.setdefault("largura", v["width"])
    m.setdefault("altura", v["height"])
    m.setdefault("fps", NOMES_FPS.get(v["r_frame_rate"], str(round(Fraction(v["r_frame_rate"])))))
    m.setdefault("duracao", float(info["format"]["duration"]))
    m.setdefault("canais", min(2, sum(s.get("channels", 0) for s in info["streams"] if s["codec_type"] == "audio")))


def el(pai, tag, texto=None, **attrs):
    e = ET.SubElement(pai, tag, {k: str(v) for k, v in attrs.items()})
    if texto is not None:
        e.text = str(texto)
    return e


def el_taxa(pai, fps):
    tb, ntsc, _ = taxa(fps)
    r = el(pai, "rate")
    el(r, "timebase", tb)
    el(r, "ntsc", "TRUE" if ntsc else "FALSE")


def el_timecode(pai, fps):
    tc = el(pai, "timecode")
    el_taxa(tc, fps)
    el(tc, "string", "00:00:00:00")
    el(tc, "frame", 0)
    el(tc, "displayformat", "NDF")


def el_quadro(pai, fps, largura, altura):
    sc = el(pai, "samplecharacteristics")
    el_taxa(sc, fps)
    el(sc, "width", largura)
    el(sc, "height", altura)
    el(sc, "anamorphic", "FALSE")
    el(sc, "pixelaspectratio", "square")
    el(sc, "fielddominance", "none")


class Montagem:
    def __init__(self, dados, kf_base):
        self.dados = dados
        self.fps = str(dados["fps"])
        self.midias = dados["midias"]
        self.kf_base = kf_base
        self.arquivos_escritos = set()
        self.n_clipe = 0
        for i, (mid, m) in enumerate(self.midias.items(), 1):
            completar(m)
            m["_file"] = f"file-{i}"
            m["_master"] = f"masterclip-{i}"
            m["_quadros"] = quadros(m["duracao"], m.get("fps", self.fps))

    def novo_id(self):
        self.n_clipe += 1
        return f"clipitem-{self.n_clipe}"

    def el_file(self, pai, m, nome):
        if m["_file"] in self.arquivos_escritos:
            el(pai, "file", id=m["_file"])
            return
        self.arquivos_escritos.add(m["_file"])
        fps = m.get("fps", self.fps)
        f = el(pai, "file", id=m["_file"])
        el(f, "name", nome)
        el(f, "pathurl", pathurl(m["arquivo"]))
        el_taxa(f, fps)
        el(f, "duration", m["_quadros"])
        el_timecode(f, fps)
        media = el(f, "media")
        el_quadro(el(media, "video"), fps, m["largura"], m["altura"])
        if m.get("canais", 0):
            a = el(media, "audio")
            sc = el(a, "samplecharacteristics")
            el(sc, "depth", 16)
            el(sc, "samplerate", 48000)
            el(a, "channelcount", m["canais"])

    def el_movimento(self, pai, item, m, seq, ent, sai):
        """Basic Motion: escala que preenche o quadro × zoom do item, e posição opcional."""
        base = max(seq["largura"] / m["largura"], seq["altura"] / m["altura"]) * 100
        zoom = item.get("zoom", 1)
        z0, z1 = (zoom, zoom) if not isinstance(zoom, list) else zoom
        efeito = el(el(pai, "filter"), "effect")
        el(efeito, "name", "Basic Motion")
        el(efeito, "effectid", "basic")
        el(efeito, "effectcategory", "motion")
        el(efeito, "effecttype", "motion")
        el(efeito, "mediatype", "video")
        p = el(efeito, "parameter", authoringApp="PremierePro")
        el(p, "parameterid", "scale")
        el(p, "name", "Scale")
        el(p, "valuemin", 0)
        el(p, "valuemax", 1000)
        el(p, "value", round(base * z0, 3))
        if z0 != z1:
            inicio = ent if self.kf_base == "midia" else 0
            for quando, z in ((inicio, z0), (inicio + sai - ent, z1)):
                k = el(p, "keyframe")
                el(k, "when", quando)
                el(k, "value", round(base * z, 3))
        if "posicao" in item:
            x, y = item["posicao"]
            p = el(efeito, "parameter", authoringApp="PremierePro")
            el(p, "parameterid", "center")
            el(p, "name", "Center")
            v = el(p, "value")
            el(v, "horiz", round(x / seq["largura"], 6))
            el(v, "vert", round(y / seq["altura"], 6))

    def el_clipe(self, faixa, item, seq, inicio, cid, tipo="video", canal=None):
        m = self.midias[item["midia"]]
        fps = m.get("fps", self.fps)
        nome = Path(str(m["arquivo"]).replace("\\", "/")).name
        ent = quadros(item.get("entrada", 0), fps)
        sai = quadros(item.get("saida", m["duracao"]), fps)
        if taxa(fps)[2] == taxa(self.fps)[2]:
            fim = inicio + sai - ent
        else:
            fim = inicio + quadros(Fraction(str(item.get("saida", m["duracao"]))) - Fraction(str(item.get("entrada", 0))), self.fps)
        attrs = {"id": cid}
        if tipo == "audio":
            attrs["premiereChannelType"] = "stereo" if m.get("canais", 0) >= 2 else "mono"
        c = el(faixa, "clipitem", **attrs)
        el(c, "masterclipid", m["_master"])
        el(c, "name", nome)
        el(c, "enabled", "TRUE")
        el(c, "duration", m["_quadros"])
        el_taxa(c, fps)
        el(c, "start", inicio)
        el(c, "end", fim)
        el(c, "in", ent)
        el(c, "out", sai)
        if tipo == "video":
            el(c, "alphatype", "straight" if m.get("alfa") else "none")
            el(c, "pixelaspectratio", "square")
            el(c, "anamorphic", "FALSE")
        self.el_file(c, m, nome)
        if tipo == "video":
            self.el_movimento(c, item, m, seq, ent, sai)
        else:
            st = el(c, "sourcetrack")
            el(st, "mediatype", "audio")
            el(st, "trackindex", canal)
        return c, fim

    @staticmethod
    def el_links(clipe, links):
        for ref, tipo, faixa, indice, grupo in links:
            ln = el(clipe, "link")
            el(ln, "linkclipref", ref)
            el(ln, "mediatype", tipo)
            el(ln, "trackindex", faixa)
            el(ln, "clipindex", indice)
            if grupo:
                el(ln, "groupindex", grupo)

    def posicao(self, item, inicios_v1, fps):
        if "no" in item:
            return inicios_v1[item["no"]] + quadros(item.get("desloc", 0), fps)
        return quadros(item["em"], fps)

    def sequencia(self, pai, seq, n):
        fps = self.fps
        s = el(pai, "sequence", id=f"sequence-{n}")
        el(s, "name", seq["nome"])
        duracao = el(s, "duration", 0)
        el_taxa(s, fps)
        el_timecode(s, fps)
        media = el(s, "media")
        video = el(media, "video")
        el_quadro(el(video, "format"), fps, seq["largura"], seq["altura"])

        # V1: cortes colados em sequência, cada um com o áudio ligado em A1/A2.
        v1 = el(video, "track")
        audio_clipes = {1: [], 2: []}
        inicios_v1, t = {}, 0
        for i, item in enumerate(seq.get("v1", []), 1):
            m = self.midias[item["midia"]]
            canais = [1, 2][: min(m.get("canais", 0), 2)]
            # vídeo e áudio do mesmo corte se referenciam para andarem juntos na timeline
            links = [(self.novo_id(), "video", 1, i, None)]
            for c in canais:
                links.append((self.novo_id(), "audio", c, len(audio_clipes[c]) + 1, 1))
                audio_clipes[c].append((item, t, links[-1][0], links))
            inicios_v1[item.get("id", i)] = t
            clipe, fim = self.el_clipe(v1, item, seq, t, links[0][0])
            self.el_links(clipe, links)
            t = fim
        total = t
        el(v1, "enabled", "TRUE")
        el(v1, "locked", "FALSE")

        # Faixas de cima: vinheta, páginas, títulos, legendas, elementos do gancho.
        sobre = seq.get("sobre", [])
        for numero in range(2, max([2] + [x["faixa"] for x in sobre]) + 1):
            faixa = el(video, "track")
            for item in sorted((x for x in sobre if x["faixa"] == numero), key=lambda x: self.posicao(x, inicios_v1, fps)):
                _, fim = self.el_clipe(faixa, item, seq, self.posicao(item, inicios_v1, fps), self.novo_id())
                total = max(total, fim)
            el(faixa, "enabled", "TRUE")
            el(faixa, "locked", "FALSE")

        # Áudio: voz em estéreo (A1 + A2, como o Premiere exporta) e faixas vazias para música/efeitos.
        audio = el(media, "audio")
        el(audio, "numOutputChannels", 2)
        sc = el(el(audio, "format"), "samplecharacteristics")
        el(sc, "depth", 16)
        el(sc, "samplerate", 48000)
        saidas = el(audio, "outputs")
        for c in (1, 2):
            g = el(saidas, "group")
            el(g, "index", c)
            el(g, "numchannels", 1)
            el(g, "downmix", 0)
            el(el(g, "channel"), "index", c)
        for c in (1, 2):
            if not audio_clipes[c]:
                continue
            faixa = el(audio, "track", premiereTrackType="Stereo", currentExplodedTrackIndex=c - 1, totalExplodedTrackCount=2)
            for item, inicio, aid, links in audio_clipes[c]:
                clipe, _ = self.el_clipe(faixa, item, seq, inicio, aid, tipo="audio", canal=c)
                self.el_links(clipe, links)
            el(faixa, "enabled", "TRUE")
            el(faixa, "locked", "FALSE")
        for _ in range(seq.get("audio_vazias", 0)):
            faixa = el(audio, "track")
            el(faixa, "enabled", "TRUE")
            el(faixa, "locked", "FALSE")

        for mk in seq.get("marcadores", []):
            m = el(s, "marker")
            el(m, "name", mk["nome"])
            el(m, "comment", mk.get("nota", ""))
            el(m, "in", self.posicao(mk, inicios_v1, fps))
            el(m, "out", -1)

        duracao.text = str(total)

    def xml(self):
        raiz = ET.Element("xmeml", version="4")
        projeto = el(raiz, "project")
        el(projeto, "name", self.dados.get("projeto", "Montagem"))
        filhos = el(projeto, "children")
        for n, seq in enumerate(self.dados["sequencias"], 1):
            self.sequencia(filhos, seq, n)
        ET.indent(raiz, space="\t")
        return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(raiz, encoding="unicode") + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("montagem", help="JSON com mídias e sequências")
    ap.add_argument("saida", help="arquivo .xml para importar no Premiere")
    ap.add_argument("--kf-base", choices=["midia", "clipe"], default="midia")
    args = ap.parse_args()
    dados = json.loads(Path(args.montagem).read_text(encoding="utf-8"))
    Path(args.saida).write_text(Montagem(dados, args.kf_base).xml(), encoding="utf-8")
    print(f"{len(dados['sequencias'])} sequência(s) → {args.saida}")


if __name__ == "__main__":
    main()
