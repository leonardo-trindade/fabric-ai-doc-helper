"""escolher_workspace.py com a API do Fabric simulada (nenhum acesso real)."""
from __future__ import annotations

import sys

import pytest

import _comum
import escolher_workspace as ew
import guarda

BASE = ('cliente: "Cli"\nprojeto: "P"\nautor: "A"\nworkspace_alvo: ""\nworkspace_id: ""\n'
        'workspaces_leitura_extra: []\nconta_fabric: "{conta}"\ntenant_id: "t"\n')


@pytest.fixture
def cenario(tmp_path, monkeypatch, capsys):
    (tmp_path / "projeto").mkdir()
    yaml = tmp_path / "projeto" / "projeto.yaml"
    yaml.write_text(BASE.format(conta="powerbi@cliente.com"), encoding="utf-8")
    ws = [{"id": "id-prd", "displayName": 'BI #1 "Produção", Vendas', "type": "Workspace", "capacityId": "c"},
          {"id": "id-dev", "displayName": "WS Fabric-Dev", "type": "Workspace", "capacityId": "c"},
          {"id": "id-me", "displayName": "My workspace", "type": "Personal"},
          {"id": "id-leg", "displayName": "Legado", "type": "Workspace"}]
    monkeypatch.setattr(ew, "YAML", yaml)
    monkeypatch.setattr(_comum, "PROJETO", tmp_path / "projeto")
    monkeypatch.setattr(ew, "checar_login", lambda cfg: {})
    # duas páginas da API (continuationToken), montadas na hora: o teste altera `ws`
    monkeypatch.setattr(ew, "fab_api", lambda ep: ({"value": ws[:2], "continuationToken": "abc"}
                                                   if ep == "workspaces" else {"value": ws[2:]}))

    def rodar(*args):
        monkeypatch.setattr(sys, "argv", ["escolher_workspace.py", *args])
        codigo = 0
        try:
            ew.main()
        except SystemExit as e:
            codigo = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int) and e.code:
                print(e.code)
        return codigo, capsys.readouterr().out

    return type("Cenario", (), {"raiz": tmp_path, "yaml": yaml, "ws": ws, "rodar": staticmethod(rodar)})


def test_sem_conta_registrada_recusa(cenario):
    cenario.yaml.write_text(BASE.format(conta=""), encoding="utf-8")
    codigo, saida = cenario.rodar("--listar")
    assert codigo == 1 and "ainda não foi registrada" in saida


def test_listar(cenario):
    codigo, saida = cenario.rodar("--listar")
    assert codigo == 0 and "(4)" in saida
    assert saida.index("BI #1") < saida.index("Legado") < saida.index("WS Fabric-Dev") < saida.index("My workspace")
    assert "(pessoal)" in saida and "(sem capacidade)" in saida
    _, filtrada = cenario.rodar("--listar", "--filtro", "fabric")
    assert "WS Fabric-Dev" in filtrada and "BI #1" not in filtrada


def test_definir_grava_nome_exato_e_id(cenario):
    assert cenario.rodar("--definir", "1")[0] == 0
    cfg = _comum.config()
    assert (cfg["workspace_alvo"], cfg["workspace_id"]) == ('BI #1 "Produção", Vendas', "id-prd")
    assert guarda.target_workspaces(cenario.raiz) == {'bi #1 "produção", vendas'}
    guarda.verificar_fab(["ls", 'BI #1 "Produção", Vendas.Workspace'], cenario.raiz)


def test_um_workspace_por_projeto(cenario):
    cenario.rodar("--definir", "1")
    codigo, saida = cenario.rodar("--definir", "WS Fabric-Dev")
    assert codigo == 1 and "único workspace" in saida
    assert cenario.rodar("--definir", "1")[0] == 0  # redefinir o mesmo é aceito
    codigo, saida = cenario.rodar("--definir", "nao-existe")
    assert codigo == 1 and "não está na lista" in saida


def test_extra(cenario):
    assert cenario.rodar("--extra", "2")[0] == 1  # antes de escolher o workspace do projeto
    cenario.rodar("--definir", "1")
    assert cenario.rodar("--extra", "2")[0] == 0  # 2 = Legado (pessoal fica no fim)
    assert guarda.target_workspaces(cenario.raiz) == {'bi #1 "produção", vendas', "legado"}
    assert cenario.rodar("--extra", "1")[0] == 1  # igual ao workspace do projeto


def test_conferir_renomeado_e_sumido(cenario):
    cenario.rodar("--definir", "1")
    codigo, saida = cenario.rodar("--conferir")
    assert codigo == 0 and saida.startswith("OK")
    cenario.ws[0]["displayName"] = "BI Produção (novo)"
    codigo, saida = cenario.rodar("--conferir")
    assert codigo == 6 and "RENOMEADO" in saida
    assert cenario.rodar("--renomeado")[0] == 0
    cfg = _comum.config()
    assert (cfg["workspace_alvo"], cfg["workspace_id"]) == ("BI Produção (novo)", "id-prd")
    cenario.ws.pop(0)
    codigo, saida = cenario.rodar("--conferir")
    assert codigo == 7 and "NÃO ENCONTRADO" in saida


def test_conferir_completa_id_de_projeto_antigo(cenario):
    cenario.yaml.write_text(BASE.format(conta="x@y").replace('workspace_alvo: ""', 'workspace_alvo: "Legado"'),
                            encoding="utf-8")
    assert cenario.rodar("--conferir")[0] == 0
    assert _comum.config()["workspace_id"] == "id-leg"
