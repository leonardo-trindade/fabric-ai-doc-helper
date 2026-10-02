"""Gera o documento técnico (.docx) no template fixo a partir de uma especificação YAML.

Uso:
    uv run python scripts/build_doc.py projeto/docs/<nome>.yaml [--saida arquivo.docx]

A especificação descreve capa, seções e apêndices em blocos simples (ver
templates/exemplo-documento.yaml). O visual (cabeçalho, rodapé, cores, estilos,
numeração) vem de templates/template-bluer.docx e é o mesmo para todo projeto.

Regras:
  * Nunca sobrescreve: se o .docx de saída já existir, o script para.
  * Seções são numeradas automaticamente (1, 2, ...); apêndices usam letras.
  * Depois de gerar, rode scripts/finalizar_docx.ps1 para atualizar o sumário.

Marcação de texto nos blocos:
  **negrito**   `código`   {{pendência}} (dourado itálico = item a preencher)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATE = RAIZ / "templates" / "template-bluer.docx"
NAVY, BLUE, GOLD, GREY = "0B3A57", "0173B6", "C79408", "595959"
LARGURA = 9026  # largura útil da página (A4, margens do template), em DXA
MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO",
         "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]


# ---------------------------------------------------------------- primitivas XML
def _rpr(b=False, i=False, color=None, sz=None, font=None):
    x = ""
    if font:
        x += f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>'
    if b:
        x += "<w:b/><w:bCs/>"
    if i:
        x += "<w:i/><w:iCs/>"
    if color:
        x += f'<w:color w:val="{color}"/>'
    if sz:
        x += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    return f"<w:rPr>{x}</w:rPr>" if x else ""


def run(t, **k):
    return f'<w:r>{_rpr(**k)}<w:t xml:space="preserve">{escape(str(t))}</w:t></w:r>'


def rich(text, sz=None, color=None, i=False):
    out = []
    for tok in re.split(r"(\*\*.+?\*\*|`.+?`|\{\{.+?\}\})", str(text)):
        if not tok:
            continue
        if tok.startswith("**"):
            out.append(run(tok[2:-2], b=True, sz=sz, color=color or NAVY, i=i))
        elif tok.startswith("`"):
            out.append(run(tok[1:-1], font="Consolas", sz=(sz or 22) - 3, color="1F2937", i=i))
        elif tok.startswith("{{"):
            out.append(run(tok, i=True, color=GOLD, sz=sz))
        else:
            out.append(run(tok, sz=sz, color=color, i=i))
    return "".join(out)


def para(inner, before=60, after=120, style=None, jc=None, extra="", keep_next=False):
    ppr = f'<w:pStyle w:val="{style}"/>' if style else ""
    ppr += "<w:keepNext/>" if keep_next else ""
    ppr += extra + f'<w:spacing w:before="{before}" w:after="{after}"/>'
    ppr += f'<w:jc w:val="{jc}"/>' if jc else ""
    return f"<w:p><w:pPr>{ppr}</w:pPr>{inner}</w:p>"


class Doc:
    def __init__(self):
        self.body: list[str] = []
        self.toc: list[tuple[str, str]] = []
        self.bm = 100

    def add(self, x):
        self.body.append(x)

    # títulos
    def _bookmark(self):
        self.bm += 1
        return self.bm, f"_TocDH{self.bm}"

    def h1(self, texto):
        i, name = self._bookmark()
        self.toc.append((texto, name))
        self.add(f'<w:p><w:pPr><w:pStyle w:val="Ttulo1"/><w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="{GOLD}"/></w:pBdr>'
                 f'<w:spacing w:before="320" w:after="120"/></w:pPr><w:bookmarkStart w:id="{i}" w:name="{name}"/>'
                 f'{run(texto)}<w:bookmarkEnd w:id="{i}"/></w:p>')

    def h2(self, texto):
        i, name = self._bookmark()
        self.add(f'<w:p><w:pPr><w:pStyle w:val="Ttulo2"/><w:keepNext/><w:spacing w:before="200" w:after="80"/></w:pPr>'
                 f'<w:bookmarkStart w:id="{i}" w:name="{name}"/>{run(texto)}<w:bookmarkEnd w:id="{i}"/></w:p>')

    def h3(self, texto):
        self.add(para(run(texto, b=True, color=BLUE), before=160, after=60, keep_next=True))

    # texto
    def p(self, texto):
        self.add(para(rich(texto)))

    def nota(self, texto):
        self.add(para(run("» " + str(texto), i=True, color=GREY, sz=20)))

    def bullets(self, itens):
        for it in itens:
            self.add(para(rich(it), before=40, after=40, style="PargrafodaLista",
                          extra='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>'))

    def destaque(self, titulo, texto):
        extra = (f'<w:pBdr><w:left w:val="single" w:sz="18" w:space="8" w:color="{GOLD}"/></w:pBdr>'
                 '<w:shd w:val="clear" w:color="auto" w:fill="FFF8E6"/><w:ind w:left="170" w:right="170"/>')
        self.add(para(run(str(titulo) + " ", b=True, color=NAVY, sz=20) + rich(texto, sz=20), before=120, after=160, extra=extra))

    def codigo(self, linhas):
        if isinstance(linhas, str):
            linhas = linhas.splitlines()
        extra = '<w:shd w:val="clear" w:color="auto" w:fill="F3F4F6"/><w:ind w:left="170" w:right="170"/>'
        for n, ln in enumerate(linhas):
            self.add(para(run(ln if ln else " ", font="Consolas", sz=17, color="1F2937"),
                          before=60 if n == 0 else 0, after=60 if n == len(linhas) - 1 else 0, extra=extra))

    def quebra(self):
        self.add('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    # tabela
    def tabela(self, colunas, linhas, larguras=None, tamanho=None, primeira_negrito=False, zebra=True, total=False):
        n = len(colunas)
        linhas = [[("" if c is None else c) for c in (list(l) + [""] * (n - len(l)))[:n]] for l in linhas]
        larguras = larguras or _larguras_auto(colunas, linhas)
        larguras = _ajusta(larguras)
        sz = tamanho or (20 if n <= 2 else 18 if n <= 3 else 17)
        cm = ('<w:tcMar><w:top w:w="50" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
              '<w:bottom w:w="50" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tcMar>')
        x = (f'<w:tbl><w:tblPr><w:tblW w:w="{LARGURA}" w:type="dxa"/><w:tblBorders>'
             + "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="BFC7D0"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
             + '</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="10" w:type="dxa"/><w:right w:w="10" w:type="dxa"/></w:tblCellMar></w:tblPr>'
             + "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in larguras) + "</w:tblGrid>")
        x += "<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>"
        for h, w in zip(colunas, larguras):
            x += (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="{NAVY}"/>{cm}</w:tcPr>'
                  f'<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr>{run(h, b=True, color="FFFFFF", sz=sz)}</w:p></w:tc>')
        x += "</w:tr>"
        for ri, r in enumerate(linhas):
            e_total = total and ri == len(linhas) - 1
            fill = "E8EEF3" if e_total else ("F5F7F9" if zebra and ri % 2 == 1 else None)
            x += "<w:tr><w:trPr><w:cantSplit/></w:trPr>"
            for ci, (c, w) in enumerate(zip(r, larguras)):
                shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
                inner = ""
                for ptxt in (c if isinstance(c, list) else [c]):
                    ptxt = str(ptxt)
                    if ((primeira_negrito and ci == 0) or e_total) and ptxt and not ptxt.startswith("**"):
                        ptxt = f"**{ptxt}**"
                    inner += f'<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr>{rich(ptxt, sz=sz)}</w:p>'
                x += f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shd}{cm}</w:tcPr>{inner}</w:tc>'
            x += "</w:tr>"
        self.add(x + "</w:tbl>")
        self.add(para("", before=0, after=60))


def _larguras_auto(colunas, linhas):
    pesos = []
    for ci, h in enumerate(colunas):
        tams = [len(str(h))] + [len(" ".join(c) if isinstance(c, list) else str(c)) for c in (l[ci] for l in linhas)]
        media = sum(tams) / len(tams)
        pesos.append(max(4.0, min(max(tams), 60) * 0.5 + media * 0.5))
    return [p / sum(pesos) * LARGURA for p in pesos]


def _ajusta(larguras):
    ws = [max(600, float(w)) for w in larguras]
    ws = [int(w / sum(ws) * LARGURA) for w in ws]
    ws[-1] += LARGURA - sum(ws)
    return ws


# ---------------------------------------------------------------- blocos da especificação
def render_blocos(doc: Doc, blocos: list) -> None:
    for b in blocos or []:
        if not isinstance(b, dict) or len(b) != 1:
            raise ValueError(f"Bloco inválido (use uma chave por bloco): {b}")
        chave, valor = next(iter(b.items()))
        if chave == "h2":
            doc.h2(valor)
        elif chave == "h3":
            doc.h3(valor)
        elif chave == "p":
            doc.p(valor)
        elif chave == "nota":
            doc.nota(valor)
        elif chave == "bullets":
            doc.bullets(valor)
        elif chave == "destaque":
            doc.destaque(valor.get("titulo", ""), valor.get("texto", ""))
        elif chave == "codigo":
            doc.codigo(valor)
        elif chave == "tabela":
            doc.tabela(valor["colunas"], valor.get("linhas", []), valor.get("larguras"), valor.get("tamanho"),
                       valor.get("primeira_negrito", False), valor.get("zebra", True), valor.get("total", False))
        elif chave == "quebra_pagina":
            doc.quebra()
        else:
            raise ValueError(f"Tipo de bloco desconhecido: '{chave}'")


def capa(doc: Doc, meta: dict) -> str:
    data = str(meta.get("data") or dt.date.today().strftime("%d/%m/%Y"))
    try:
        d = dt.datetime.strptime(data, "%d/%m/%Y")
        mes_ano = f"{MESES[d.month - 1]} {d.year}"
    except ValueError:
        mes_ano = data
    tag = f"{str(meta.get('classificacao', 'RESTRITO')).upper()} · {mes_ano}"
    doc.add(f'<w:tbl><w:tblPr><w:tblW w:w="2600" w:type="dxa"/><w:jc w:val="right"/><w:tblBorders>'
            + "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="auto"/>' for s in ("top", "left", "bottom", "right"))
            + '</w:tblBorders></w:tblPr><w:tblGrid><w:gridCol w:w="2600"/></w:tblGrid><w:tr><w:trPr><w:jc w:val="right"/></w:trPr>'
            f'<w:tc><w:tcPr><w:tcW w:w="2600" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="{NAVY}"/>'
            '<w:tcMar><w:top w:w="60" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tcMar></w:tcPr>'
            f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr>{run(tag, b=True, color="FFFFFF", sz=18)}</w:p></w:tc></w:tr></w:tbl>')
    doc.add(para(run(meta.get("titulo", "Documentação Técnica"), b=True, color=BLUE, sz=52), before=900, after=120))
    if meta.get("subtitulo"):
        doc.add(para(rich(meta["subtitulo"], color=NAVY, sz=30), before=0, after=80))
    if meta.get("linha_apoio"):
        doc.add(para(run(meta["linha_apoio"], i=True, color=GREY, sz=22), before=0, after=200))
    for campo in meta.get("campos_capa", []):
        doc.add(para(run(f"{campo['rotulo']}: ", b=True, color=NAVY) + rich(campo["valor"]), before=0, after=60))
    for _ in range(6):
        doc.add(para("", before=0, after=60))
    doc.add(para(run("Sumário", b=True, color=NAVY, sz=28), before=500, after=120))
    doc.add("@@SUMARIO@@")
    doc.quebra()
    return tag


def sumario(doc: Doc) -> str:
    out = ['<w:sdt><w:sdtPr><w:alias w:val="Sumário"/><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>'
           '<w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>']
    for n, (titulo, bm) in enumerate(doc.toc):
        ini = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\h \\o "1-1" </w:instrText></w:r>'
               '<w:r><w:fldChar w:fldCharType="separate"/></w:r>') if n == 0 else ""
        out.append(f'<w:p><w:pPr><w:pStyle w:val="Sumrio1"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9016"/></w:tabs></w:pPr>{ini}'
                   f'<w:hyperlink w:anchor="{bm}" w:history="1"><w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr><w:t xml:space="preserve">{escape(titulo)}</w:t></w:r>'
                   f'<w:r><w:tab/></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGEREF {bm} \\h </w:instrText></w:r>'
                   '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink></w:p>')
    out.append('<w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:sdtContent></w:sdt>')
    return "".join(out)


# ---------------------------------------------------------------- montagem
def gerar(spec: dict, saida: Path) -> None:
    meta = spec.get("documento", {})
    doc = Doc()
    capa(doc, meta)
    for n, sec in enumerate(spec.get("secoes", []), start=1):
        doc.h1(f"{n}  {sec['titulo']}")
        render_blocos(doc, sec.get("blocos"))
    for ap in spec.get("apendices", []):
        doc.quebra()
        doc.h1(f"{ap['letra']}  Apêndice – {ap['titulo']}")
        render_blocos(doc, ap.get("blocos"))

    work = Path(tempfile.mkdtemp(prefix="docx_"))
    try:
        with zipfile.ZipFile(TEMPLATE) as z:
            z.extractall(work)
        docp = work / "word" / "document.xml"
        orig = docp.read_text(encoding="utf-8")
        head = orig[: orig.index("<w:body>") + len("<w:body>")]
        sect = re.search(r"<w:sectPr[ >].*?</w:sectPr>", orig, re.S).group(0)
        corpo = "".join(doc.body).replace("@@SUMARIO@@", sumario(doc))
        docp.write_text(head + corpo + sect + "</w:body></w:document>", encoding="utf-8")

        rod = work / "word" / "footer1.xml"
        f = rod.read_text(encoding="utf-8")
        nome_rod = str(meta.get("rodape", "Documentação Técnica"))
        partes = nome_rod.split(" ", 1) + [""]
        f = f.replace(">Levantamento de <", f">{escape(partes[0])} <").replace(">Requisitos  —<", f">{escape(partes[1])}  —<")
        rod.write_text(f, encoding="utf-8")

        core = work / "docProps" / "core.xml"
        c = core.read_text(encoding="utf-8")
        c = re.sub(r"<dc:title>.*?</dc:title>|<dc:title/>", "", c)
        titulo_prop = " – ".join(x for x in [meta.get("titulo"), meta.get("subtitulo")] if x)
        c = c.replace("</cp:coreProperties>", f"<dc:title>{escape(titulo_prop)}</dc:title></cp:coreProperties>")
        if meta.get("autor"):
            c = re.sub(r"<dc:creator>.*?</dc:creator>", f"<dc:creator>{escape(meta['autor'])}</dc:creator>", c)
            c = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", f"<cp:lastModifiedBy>{escape(meta['autor'])}</cp:lastModifiedBy>", c)
        core.write_text(c, encoding="utf-8")

        saida.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(work / "[Content_Types].xml", "[Content_Types].xml")
            for arq in work.rglob("*"):
                rel = arq.relative_to(work).as_posix()
                if arq.is_file() and rel != "[Content_Types].xml":
                    z.write(arq, rel)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("especificacao", type=Path)
    ap.add_argument("--saida", type=Path, help="padrão: mesmo nome da especificação, com .docx")
    a = ap.parse_args()
    spec = yaml.safe_load(a.especificacao.read_text(encoding="utf-8"))
    saida = a.saida or a.especificacao.with_suffix(".docx")
    if saida.exists():
        sys.exit(f"{saida} já existe. O gerador nunca sobrescreve: use um novo nome/versão.")
    gerar(spec, saida)
    print(f"Gerado: {saida}")
    print("Próximo passo: powershell -File scripts/finalizar_docx.ps1 \"" + str(saida) + "\"  (atualiza o sumário; -Pdf gera PDF)")


if __name__ == "__main__":
    main()
