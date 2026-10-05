"""Verifica o documento técnico antes da entrega: estrutura, sigilo, nomes, dicionário, fontes e pendências.

Uso:
    uv run python scripts/verificar_documento.py projeto/docs/DT_<cliente>_<projeto>_v0.1.yaml
    uv run python scripts/verificar_documento.py projeto/docs/revisado/DT_<...>.docx

Na especificação (.yaml) faz todas as conferências; no .docx (ex.: o revisado pelo usuário), as que
dependem só do texto: estrutura, sigilo, nomes e pendências.

  ERRO   (impede a entrega; código de saída 1):
    - seções 1–15 e Apêndice A fora da estrutura fixa (templates/estrutura-documento.yaml);
    - segredo, token, string de conexão, ID do ambiente (workspace, tenant, capacidade, itens)
      ou a conta técnica do Fabric no texto;
    - item `Nome.Tipo` ou tabela `schema.tabela` citados que não existem no inventário;
    - Apêndice A com coluna inexistente ou tipo diferente do inventário;
    - seção com conteúdo sem `fontes` (só .yaml), ou fonte que cita item/arquivo inexistente.
  AVISO  (conferir): outros GUIDs e e-mails, colunas do inventário fora do dicionário, inventário
         antigo, Apêndice B sem planilha de mapeamento registrada.
  PENDÊNCIAS: todos os {{...}} por seção (lista para o usuário completar).

Lê só arquivos do projeto (projeto.yaml, último inventário); não acessa o Fabric.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import CONN_STRING, PROJETO, RAIZ, SEGREDO  # noqa: E402

import yaml  # noqa: E402

ESTRUTURA = RAIZ / "templates" / "estrutura-documento.yaml"
SEM_FONTE = {"Controle do Documento", "Aprovação"}  # seções que não descrevem o ambiente
TIPOS_FABRIC = {"Lakehouse", "Warehouse", "Notebook", "DataPipeline", "Environment", "SemanticModel",
                "Report", "SQLEndpoint", "Dataflow", "KQLDatabase", "Eventhouse", "Eventstream",
                "MLModel", "MLExperiment", "SparkJobDefinition", "MirroredDatabase", "Dashboard",
                "CopyJob", "VariableLibrary", "Workspace"}
SEGREDOS_EXTRA = [re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
                  re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-.]{20,}"),
                  re.compile(r"(?i)(AccountKey|SharedAccessSignature)=[A-Za-z0-9+/=%]{16,}")]
GUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
CRASE = re.compile(r"`([^`]+)`")
PENDENCIA = re.compile(r"\{\{(.+?)\}\}")
ITEM = re.compile(r"^(?P<nome>.+)\.(?P<tipo>[A-Za-z]+)$")
DIAS_INVENTARIO = 30


@dataclass
class Relatorio:
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)

    def imprimir(self) -> None:
        for titulo, itens in (("ERROS", self.erros), ("AVISOS", self.avisos), ("PENDÊNCIAS {{...}}", self.pendencias)):
            print(f"\n{titulo} ({len(itens)})")
            for i in dict.fromkeys(itens):  # sem repetir, na ordem
                print(f"  - {i}")
        print("\nRESULTADO: " + ("NÃO ENTREGAR — corrija os erros." if self.erros else
                                 "OK para revisão humana (confira avisos e pendências)."))


# ---------------------------------------------------------------- contexto do projeto
@dataclass
class Contexto:
    cfg: dict
    inventario: dict | None
    data_inventario: dt.datetime | None

    @property
    def itens(self) -> set[tuple[str, str]]:
        return {(i["displayName"].lower(), i["type"].lower()) for i in (self.inventario or {}).get("itens", [])}

    @property
    def tabelas(self) -> dict[str, dict[str, list | None]]:
        """schema (minúsculo) -> {tabela (minúscula): colunas ou None}, somando os Lakehouses."""
        out: dict[str, dict[str, list | None]] = {}
        for lh in (self.inventario or {}).get("lakehouses", []):
            for schema, tabs in lh.get("schemas", {}).items():
                for t, cols in tabs.items():
                    out.setdefault(schema.lower(), {})[t.lower()] = cols
        return out

    @property
    def ids_do_ambiente(self) -> set[str]:
        inv = self.inventario or {}
        ids = {inv.get("workspace_id"), inv.get("capacity_id"), inv.get("tenant_id"),
               self.cfg.get("tenant_id"), self.cfg.get("workspace_id")}
        ids |= {i.get("id") for i in inv.get("itens", [])}
        return {str(x).lower() for x in ids if x}


def carregar_contexto(projeto: Path) -> Contexto:
    arq = projeto / "projeto.yaml"
    cfg = (yaml.safe_load(arq.read_text(encoding="utf-8")) or {}) if arq.is_file() else {}
    invs = sorted((projeto / "inventario").glob("*.json"))
    if not invs:
        return Contexto(cfg, None, None)
    inv = json.loads(invs[-1].read_text(encoding="utf-8"))
    try:
        data = dt.datetime.fromisoformat(inv.get("gerado_em", ""))
    except ValueError:
        data = None
    return Contexto(cfg, inv, data)


# ---------------------------------------------------------------- leitura do documento
@dataclass
class Secao:
    titulo: str
    textos: list[str]
    blocos: list = field(default_factory=list)
    fontes: list[str] | None = None


def _textos_bloco(bloco) -> list[str]:
    if isinstance(bloco, str):
        return [bloco]
    if isinstance(bloco, list):
        return [t for b in bloco for t in _textos_bloco(b)]
    if isinstance(bloco, dict):
        return [t for v in bloco.values() for t in _textos_bloco(v)]
    return [str(bloco)] if bloco is not None and not isinstance(bloco, bool) else []


def ler_yaml(caminho: Path) -> tuple[list[Secao], list[Secao]]:
    spec = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}

    def secao(d: dict, titulo: str) -> Secao:
        return Secao(titulo, _textos_bloco(d.get("blocos") or []), d.get("blocos") or [], d.get("fontes"))

    secoes = [secao(s, s.get("titulo", "")) for s in spec.get("secoes", [])]
    apendices = [secao(a, f"{a.get('letra', '')}|{a.get('titulo', '')}") for a in spec.get("apendices", [])]
    capa = _textos_bloco(spec.get("documento", {}))
    if secoes:
        secoes[0].textos = capa + secoes[0].textos
    return secoes, apendices


def ler_docx(caminho: Path) -> tuple[list[Secao], list[Secao]]:
    from docx import Document
    from docx.oxml.ns import qn

    def texto(el) -> str:
        """Texto do parágrafo/célula; trechos em fonte de código (Consolas) voltam a ficar entre crases,
        como na especificação (o build_doc.py converte `nome` em Consolas)."""
        partes = []
        for r in el.iter(qn("w:r")):
            t = "".join(x.text or "" for x in r.iter(qn("w:t")))
            fonte = r.find(f"{qn('w:rPr')}/{qn('w:rFonts')}")
            codigo = fonte is not None and (fonte.get(qn("w:ascii")) or "").lower() == "consolas"
            partes.append(f"`{t}`" if codigo and t.strip() else t)
        return "".join(partes)

    d = Document(str(caminho))
    capa = Secao("(capa)", [])
    secoes, apendices, atual = [], [], capa
    corpo = d.element.body
    for el in corpo.iterchildren():
        if el.tag == qn("w:p"):
            estilo = el.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
            texto_p = texto(el)
            if estilo is not None and estilo.get(qn("w:val")) == "Ttulo1":
                m = re.match(r"^\s*(?:(\d+)|([A-Z])\s+Apêndice\s+–)\s+(.*)$", texto_p)
                if m and m.group(2):
                    atual = Secao(f"{m.group(2)}|{m.group(3).strip()}", [])
                    apendices.append(atual)
                else:
                    atual = Secao(m.group(3).strip() if m else texto_p.strip(), [])
                    secoes.append(atual)
                continue
            atual.textos.append(texto_p)
        elif el.tag == qn("w:tbl"):
            atual.textos += [texto(c) for c in el.iter(qn("w:tc"))]
    if secoes:  # a capa (e o sumário) entram nas conferências de texto junto com a 1ª seção
        secoes[0].textos = capa.textos + secoes[0].textos
    return secoes, apendices


# ---------------------------------------------------------------- conferências
def estrutura_esperada() -> tuple[list[str], list[str]]:
    spec = yaml.safe_load(ESTRUTURA.read_text(encoding="utf-8"))
    return ([s["titulo"] for s in spec["secoes"]], [f"{a['letra']}|{a['titulo']}" for a in spec["apendices"]])


def conferir_estrutura(secoes, apendices, ctx: Contexto, r: Relatorio) -> None:
    esperadas, apend_esperados = estrutura_esperada()
    titulos = [s.titulo for s in secoes]
    if titulos != esperadas:
        faltando = [t for t in esperadas if t not in titulos]
        sobrando = [t for t in titulos if t not in esperadas]
        if faltando:
            r.erros.append(f"Estrutura: seções ausentes ou com título alterado: {', '.join(faltando)}")
        if sobrando:
            r.erros.append(f"Estrutura: seções fora da estrutura fixa: {', '.join(sobrando)}")
        if not faltando and not sobrando:
            r.erros.append("Estrutura: seções fora da ordem fixa (1–15).")
    letras = [a.titulo for a in apendices]
    for a in apend_esperados:
        if a not in letras:
            r.erros.append(f"Estrutura: falta o Apêndice {a.replace('|', ' – ')}.")
    if any(a.startswith("B|") for a in letras):
        tem_mapeamento = any((x or {}).get("tipo") == "mapeamento" for x in ctx.cfg.get("referencias") or [])
        if not tem_mapeamento:
            r.avisos.append("Apêndice B presente, mas não há planilha de mapeamento registrada em projeto.yaml → referencias.")


def conferir_sigilo(secoes: list[Secao], ctx: Contexto, r: Relatorio) -> None:
    conta = (ctx.cfg.get("conta_fabric") or "").lower()
    ids = ctx.ids_do_ambiente
    for s in secoes:
        for t in s.textos:
            if SEGREDO.search(t) or CONN_STRING.search(t) or any(p.search(t) for p in SEGREDOS_EXTRA):
                if "***MASCARADO***" not in t:
                    r.erros.append(f"[{s.titulo}] possível segredo/token/string de conexão no texto: {t[:80]!r}")
            for g in GUID.findall(t):
                (r.erros if g.lower() in ids else r.avisos).append(
                    f"[{s.titulo}] {'ID do ambiente (workspace/tenant/capacidade/item)' if g.lower() in ids else 'GUID'}"
                    f" no texto: {g} — refira-se pelo nome.")
            for e in EMAIL.findall(t):
                if conta and e.lower() == conta:
                    r.erros.append(f"[{s.titulo}] conta técnica do Fabric no texto ({e}).")
                else:
                    r.avisos.append(f"[{s.titulo}] e-mail no texto ({e}): confirme se pode constar no documento.")


def _nome_citado(token: str, ctx: Contexto) -> str | None:
    """Erro (texto) se o token entre crases cita item `Nome.Tipo` ou tabela `schema.tabela` inexistente."""
    token = token.strip()
    if not token or "{{" in token:
        return None
    m = ITEM.match(token)
    if m and m.group("tipo") in TIPOS_FABRIC:
        if m.group("tipo") == "Workspace":
            alvo = (ctx.cfg.get("workspace_alvo") or "").lower()
            extras = {str(x).lower() for x in ctx.cfg.get("workspaces_leitura_extra") or []}
            return None if m.group("nome").lower() in {alvo, *extras} else f"workspace `{token}` não é o do projeto"
        if (m.group("nome").lower(), m.group("tipo").lower()) not in ctx.itens:
            return f"item `{token}` não existe no inventário"
        return None
    partes = token.split(".")
    if len(partes) == 2 and partes[0].lower() in ctx.tabelas:
        if partes[1].lower() not in ctx.tabelas[partes[0].lower()]:
            return f"tabela `{token}` não existe no schema `{partes[0]}` do inventário"
    return None


def conferir_nomes(secoes: list[Secao], ctx: Contexto, r: Relatorio) -> None:
    if ctx.inventario is None:
        r.avisos.append("Sem inventário em projeto/inventario/: nomes, dicionário e fontes não foram conferidos.")
        return
    for s in secoes:
        for t in s.textos:
            for token in CRASE.findall(t):
                erro = _nome_citado(token, ctx)
                if erro:
                    r.erros.append(f"[{s.titulo}] {erro}.")
    if ctx.data_inventario and (dt.datetime.now() - ctx.data_inventario).days > DIAS_INVENTARIO:
        r.avisos.append(f"Inventário de {ctx.data_inventario:%d/%m/%Y} (mais de {DIAS_INVENTARIO} dias): "
                        "o workspace pode ter mudado; considere gerar um novo.")


def conferir_dicionario(apendices: list[Secao], ctx: Contexto, r: Relatorio) -> None:
    """Apêndice A (só .yaml): cada `h3: schema.tabela` seguido de tabela Coluna/Tipo confere com o inventário."""
    ap = next((a for a in apendices if a.titulo.startswith("A|")), None)
    if ap is None or ctx.inventario is None:
        return
    atual = None
    documentadas: dict[tuple[str, str], set[str]] = {}
    for bloco in ap.blocos:
        if not isinstance(bloco, dict):
            continue
        if "h3" in bloco:
            nome = str(bloco["h3"]).strip().strip("`")
            atual = tuple(nome.lower().split(".", 1)) if "." in nome and "{{" not in nome else None
            if atual and (atual[0] not in ctx.tabelas or atual[1] not in ctx.tabelas[atual[0]]):
                r.erros.append(f"[Apêndice A] tabela `{nome}` não existe no inventário.")
                atual = None
        elif "tabela" in bloco and atual:
            cols_inv = ctx.tabelas[atual[0]][atual[1]]
            if cols_inv is None:
                r.avisos.append(f"[Apêndice A] colunas de `{'.'.join(atual)}` não estão no inventário "
                                "(rode inventario.py com --colunas para esse schema).")
                continue
            tipos = {c["nome"].lower(): c["tipo"].lower() for c in cols_inv}
            vistas = documentadas.setdefault(atual, set())
            for linha in bloco["tabela"].get("linhas") or []:
                if len(linha) < 2 or "{{" in str(linha[0]):
                    continue
                col, tipo = str(linha[0]).strip().strip("`").lower(), str(linha[1]).strip().lower()
                vistas.add(col)
                if col not in tipos:
                    r.erros.append(f"[Apêndice A] coluna `{col}` não existe em `{'.'.join(atual)}`.")
                elif tipo and tipo != tipos[col]:
                    r.erros.append(f"[Apêndice A] `{'.'.join(atual)}.{col}`: tipo '{linha[1]}' no documento, "
                                   f"'{tipos[col]}' no inventário.")
            fora = sorted(set(tipos) - vistas)
            if fora:
                r.avisos.append(f"[Apêndice A] `{'.'.join(atual)}`: colunas do inventário fora do dicionário: "
                                f"{', '.join(fora[:8])}{'…' if len(fora) > 8 else ''}")


def _tem_conteudo(s: Secao) -> bool:
    return any(PENDENCIA.sub("", t).strip() for t in s.textos)


def conferir_fontes(secoes: list[Secao], apendices: list[Secao], ctx: Contexto, projeto: Path, r: Relatorio) -> None:
    """Só .yaml: toda seção com conteúdo diz de onde veio (item lido, inventário, referência, usuário)."""
    for s in secoes + apendices:
        if s.titulo in SEM_FONTE or not _tem_conteudo(s):
            continue
        if not s.fontes:
            r.erros.append(f"[{s.titulo.replace('|', ' – ')}] sem `fontes:` (de onde veio o conteúdo: itens lidos "
                           "e data, inventário, referência, decisão do usuário).")
            continue
        for f in s.fontes:
            f = str(f)
            for token in CRASE.findall(f):  # itens e tabelas da fonte vão entre crases
                erro = _nome_citado(token, ctx) if ctx.inventario is not None else None
                if erro:
                    r.erros.append(f"[{s.titulo}] fonte: {erro}.")
            for ref in re.findall(r"referencias/[^\s,;)`]+", f):
                if not (projeto / ref).exists():
                    r.erros.append(f"[{s.titulo}] fonte cita `{ref}`, que não existe em projeto/.")


def conferir_pendencias(secoes: list[Secao], r: Relatorio) -> None:
    for s in secoes:
        for t in s.textos:
            for p in PENDENCIA.findall(t):
                r.pendencias.append(f"[{s.titulo.replace('|', ' – ')}] {{{{{p}}}}}")


def verificar(caminho: Path, projeto: Path | None = None) -> Relatorio:
    projeto = projeto or PROJETO
    ctx = carregar_contexto(projeto)
    r = Relatorio()
    eh_yaml = caminho.suffix.lower() in {".yaml", ".yml"}
    secoes, apendices = ler_yaml(caminho) if eh_yaml else ler_docx(caminho)
    todas = secoes + apendices
    conferir_estrutura(secoes, apendices, ctx, r)
    conferir_sigilo(todas, ctx, r)
    conferir_nomes(todas, ctx, r)
    if eh_yaml:
        conferir_dicionario(apendices, ctx, r)
        conferir_fontes(secoes, apendices, ctx, projeto, r)
    conferir_pendencias(todas, r)
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo", type=Path, help="especificação .yaml ou documento .docx")
    a = ap.parse_args()
    if not a.arquivo.is_file():
        sys.exit(f"Arquivo não encontrado: {a.arquivo}")
    r = verificar(a.arquivo)
    print(f"Verificação de {a.arquivo.name}")
    r.imprimir()
    sys.exit(1 if r.erros else 0)


if __name__ == "__main__":
    main()
