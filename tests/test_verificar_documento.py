"""verificar_documento.py: estrutura, sigilo, nomes, dicionário, fontes e pendências (projeto fictício)."""
from __future__ import annotations

import copy
import json

import pytest
import yaml

import build_doc
import verificar_documento as vd
from conftest import RAIZ

WS_ID, TENANT, ITEM_ID = "11111111-2222-3333-4444-555555555555", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", \
    "99999999-8888-7777-6666-555555555555"
INVENTARIO = {
    "workspace": "WS Vendas", "workspace_id": WS_ID, "capacity_id": "c0ffee00-0000-0000-0000-000000000000",
    "gerado_em": "2099-01-01T10:00:00", "tenant_id": TENANT, "conta": "powerbi@cliente.com",
    "itens": [{"displayName": "pl_mestre", "type": "DataPipeline", "id": ITEM_ID, "pasta": "", "description": None},
              {"displayName": "nb_ouro", "type": "Notebook", "id": "x", "pasta": "", "description": None},
              {"displayName": "lh_dados", "type": "Lakehouse", "id": "y", "pasta": "", "description": None}],
    "lakehouses": [{"nome": "lh_dados", "files": [], "schemas": {
        "bronze": {"vendas_raw": None},
        "ouro": {"tf_vendas": [{"nome": "id_venda", "tipo": "bigint"}, {"nome": "valor", "tipo": "decimal(18,2)"},
                               {"nome": "data", "tipo": "date"}]}}}],
}
YAML_PROJETO = ('cliente: "Cli"\nworkspace_alvo: "WS Vendas"\nworkspaces_leitura_extra: []\n'
                f'conta_fabric: "powerbi@cliente.com"\ntenant_id: "{TENANT}"\nreferencias: []\n')
FONTE = ["`pl_mestre.DataPipeline` e `nb_ouro.Notebook` (lidos em 01/01/2099)", "inventário de 01/01/2099"]


@pytest.fixture
def projeto(tmp_path):
    p = tmp_path / "projeto"
    (p / "inventario").mkdir(parents=True)
    (p / "referencias").mkdir()
    (p / "referencias" / "levantamento.pptx").write_bytes(b"x")
    (p / "projeto.yaml").write_text(YAML_PROJETO, encoding="utf-8")
    (p / "inventario" / "2099-01-01_1000.json").write_text(json.dumps(INVENTARIO), encoding="utf-8")
    return p


def spec_completa() -> dict:
    """A estrutura fixa, com conteúdo sem pendências e `fontes` em toda seção que descreve o ambiente."""
    spec = yaml.safe_load((RAIZ / "templates" / "estrutura-documento.yaml").read_text(encoding="utf-8"))
    for s in spec["secoes"]:
        s["blocos"] = [{"p": f"Texto de {s['titulo']} sobre `pl_mestre.DataPipeline` e `ouro.tf_vendas`."}]
        if s["titulo"] not in vd.SEM_FONTE:
            s["fontes"] = list(FONTE)
    spec["apendices"][0]["blocos"] = [
        {"h3": "ouro.tf_vendas"},
        {"tabela": {"colunas": ["Coluna", "Tipo", "Descrição"],
                    "linhas": [["`id_venda`", "bigint", "chave"], ["`valor`", "decimal(18,2)", "valor"],
                               ["`data`", "date", "data da venda"]]}}]
    spec["apendices"][0]["fontes"] = ["inventário de 01/01/2099 (`--colunas ouro`)"]
    spec["documento"] = {"titulo": "Documentação Técnica", "subtitulo": "Projeto X", "autor": "Autor",
                         "campos_capa": [{"rotulo": "Cliente", "valor": "Cli"}]}
    return spec


def rodar(spec: dict, projeto, tmp_path, formato="yaml") -> vd.Relatorio:
    arq = tmp_path / "doc.yaml"
    arq.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if formato == "docx":
        docx = tmp_path / "doc.docx"
        build_doc.gerar(spec, docx)
        arq = docx
    return vd.verificar(arq, projeto)


def test_documento_certo_passa(projeto, tmp_path):
    r = rodar(spec_completa(), projeto, tmp_path)
    assert r.erros == [] and r.avisos == [] and r.pendencias == []


def test_template_puro_lista_pendencias_e_cobra_fontes(projeto, tmp_path):
    spec = yaml.safe_load((RAIZ / "templates" / "estrutura-documento.yaml").read_text(encoding="utf-8"))
    r = rodar(spec, projeto, tmp_path)
    assert not any(e.startswith("Estrutura") for e in r.erros)
    assert any("sem `fontes:`" in e for e in r.erros)
    assert any("{{Cliente}}" in p for p in r.pendencias)


@pytest.mark.parametrize("mexer, esperado", [
    (lambda s: s["secoes"].pop(3), "seções ausentes"),
    (lambda s: s["secoes"].insert(2, s["secoes"].pop(5)), "fora da ordem"),
    (lambda s: s["secoes"][1].update(titulo="Visão Geral do Projeto"), "seções ausentes"),
    (lambda s: s["apendices"].clear(), "falta o Apêndice A"),
])
def test_estrutura(projeto, tmp_path, mexer, esperado):
    spec = spec_completa()
    mexer(spec)
    assert any(esperado in e for e in rodar(spec, projeto, tmp_path).erros)


@pytest.mark.parametrize("texto, esperado", [
    ('Conexão: "Server=x;Password=Sup3rS3nha;"', "segredo"),
    ('api_key = "abcdef123456"', "segredo"),
    ("token eyJhbGciOiJIUzI1NiJ9AAAAAAAAAAAA.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop", "segredo"),
    (f"Workspace {WS_ID}", "ID do ambiente"),
    (f"Tenant {TENANT.upper()}", "ID do ambiente"),
    (f"Pipeline {ITEM_ID}", "ID do ambiente"),
    ("Conta powerbi@cliente.com usada na carga", "conta técnica"),
    ("Veja `pl_inexistente.DataPipeline`", "não existe no inventário"),
    ("Tabela `ouro.tf_inventada`", "não existe no schema"),
    ("Workspace `Outro Cliente.Workspace`", "não é o do projeto"),
])
def test_erros_de_conteudo(projeto, tmp_path, texto, esperado):
    spec = spec_completa()
    spec["secoes"][4]["blocos"].append({"p": texto})
    erros = rodar(spec, projeto, tmp_path).erros
    assert any(esperado in e for e in erros), erros


def test_segredo_mascarado_nao_e_erro(projeto, tmp_path):
    spec = spec_completa()
    spec["secoes"][12]["blocos"].append({"p": 'Credencial em texto no código: password = "***MASCARADO***"'})
    assert rodar(spec, projeto, tmp_path).erros == []


@pytest.mark.parametrize("texto, esperado", [
    ("GUID solto 12345678-1234-1234-1234-123456789abc", "GUID"),
    ("Contato: fulano@cliente.com", "e-mail"),
])
def test_avisos(projeto, tmp_path, texto, esperado):
    spec = spec_completa()
    spec["secoes"][4]["blocos"].append({"p": texto})
    r = rodar(spec, projeto, tmp_path)
    assert r.erros == [] and any(esperado in a for a in r.avisos)


def test_nomes_que_nao_sao_itens_ou_tabelas_sao_ignorados(projeto, tmp_path):
    spec = spec_completa()
    spec["secoes"][4]["blocos"].append({"p": "Modo `OverwriteSchema`, filtro `D_E_L_E_T_`, `spark.sql.caseSensitive`."})
    assert rodar(spec, projeto, tmp_path).erros == []


@pytest.mark.parametrize("linha, esperado", [
    (["`inventada`", "string", "x"], "não existe em `ouro.tf_vendas`"),
    (["`valor`", "string", "x"], "tipo 'string' no documento"),
])
def test_dicionario(projeto, tmp_path, linha, esperado):
    spec = spec_completa()
    spec["apendices"][0]["blocos"][1]["tabela"]["linhas"].append(linha)
    assert any(esperado in e for e in rodar(spec, projeto, tmp_path).erros)


def test_dicionario_incompleto_e_tabela_inexistente(projeto, tmp_path):
    spec = spec_completa()
    spec["apendices"][0]["blocos"][1]["tabela"]["linhas"].pop()  # tira `data`
    spec["apendices"][0]["blocos"] += [{"h3": "ouro.tf_fantasma"}]
    r = rodar(spec, projeto, tmp_path)
    assert any("fora do dicionário: data" in a for a in r.avisos)
    assert any("`ouro.tf_fantasma` não existe" in e for e in r.erros)


@pytest.mark.parametrize("fontes, esperado", [
    (None, "sem `fontes:`"),
    (["`nb_fantasma.Notebook` (lido em 01/01/2099)"], "fonte: item `nb_fantasma.Notebook`"),
    (["planilha referencias/mapeamento.xlsx"], "não existe em projeto/"),
])
def test_fontes(projeto, tmp_path, fontes, esperado):
    spec = spec_completa()
    spec["secoes"][5]["fontes"] = fontes
    assert any(esperado in e for e in rodar(spec, projeto, tmp_path).erros)


def test_fonte_com_referencia_existente(projeto, tmp_path):
    spec = spec_completa()
    spec["secoes"][2]["fontes"] = ["levantamento de requisitos (referencias/levantamento.pptx)"]
    assert rodar(spec, projeto, tmp_path).erros == []


def test_sem_inventario(projeto, tmp_path):
    for f in (projeto / "inventario").glob("*.json"):
        f.unlink()
    r = rodar(spec_completa(), projeto, tmp_path)
    assert r.erros == [] and any("Sem inventário" in a for a in r.avisos)


def test_inventario_antigo(projeto, tmp_path):
    antigo = copy.deepcopy(INVENTARIO) | {"gerado_em": "2020-01-01T10:00:00"}
    (projeto / "inventario" / "2099-01-01_1000.json").write_text(json.dumps(antigo), encoding="utf-8")
    assert any("mais de 30 dias" in a for a in rodar(spec_completa(), projeto, tmp_path).avisos)


def test_docx_gerado(projeto, tmp_path):
    """No .docx: estrutura, sigilo, nomes e pendências pelo texto (sem dicionário nem fontes)."""
    assert rodar(spec_completa(), projeto, tmp_path, "docx").erros == []
    spec = spec_completa()
    spec["secoes"].pop(7)
    spec["secoes"][4]["blocos"].append({"p": f"Tabela `ouro.tf_inventada` no workspace {WS_ID}; falta {{{{data}}}}."})
    spec["documento"]["campos_capa"].append({"rotulo": "Conta", "valor": "powerbi@cliente.com"})
    r = rodar(spec, projeto, tmp_path, "docx")
    for esperado in ("seções ausentes", "tf_inventada", "ID do ambiente", "conta técnica"):
        assert any(esperado in e for e in r.erros), (esperado, r.erros)
    assert any("{{data}}" in p for p in r.pendencias)


@pytest.mark.parametrize("extra, codigo, texto", [
    ("falta {{volume diário}}", 0, "OK para revisão humana"),
    ("Veja `pl_inexistente.DataPipeline`", 1, "NÃO ENTREGAR"),
])
def test_saida_do_script(projeto, tmp_path, capsys, monkeypatch, extra, codigo, texto):
    spec = spec_completa()
    spec["secoes"][4]["blocos"].append({"p": extra})
    arq = tmp_path / "doc.yaml"
    arq.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(vd, "PROJETO", projeto)
    monkeypatch.setattr(vd.sys, "argv", ["verificar_documento.py", str(arq)])
    with pytest.raises(SystemExit) as fim:
        vd.main()
    saida = capsys.readouterr().out
    assert fim.value.code == codigo and texto in saida and "PENDÊNCIAS" in saida
