"""Guarda: comandos do Fabric CLI (somente leitura, somente o workspace do projeto)."""
from __future__ import annotations

import pytest

import guarda
from servicos import _yaml_str  # mesmo jeito que o app grava o projeto.yaml

YAML = 'workspace_alvo: "WS Fabric-Dev"\nworkspaces_leitura_extra: ["Legado Prod"]\n'


def liberado(args, raiz) -> bool:
    try:
        guarda.verificar_fab(args, raiz)
        return True
    except guarda.Bloqueio:
        return False


@pytest.mark.parametrize("args, esperado", [
    (["exists", "WS Fabric-Dev.Workspace"], True),
    (["ls", "WS Fabric-Dev.Workspace", "-l"], True),
    (["ls", "WS Fabric-Dev.Workspace/lh_ouro.Lakehouse/Tables/dbo"], True),
    (["table", "schema", "WS Fabric-Dev.Workspace/lh.Lakehouse/Tables/ouro/tf_vendas"], True),
    (["get", "ws fabric-dev.workspace", "-q", "id"], True),
    (["get", "WS Fabric-Dev.Workspace/pl.DataPipeline", "-q", "{definition: definition}", "-f"], True),
    (["ls", "Legado Prod.Workspace"], True),
    (["ls"], True),
    (["api", "workspaces/abc/items"], True),
    (["auth", "status"], True),
    (["ls", "Fabric-Dev.Workspace"], False),  # o pedaço que a versão antiga lia
    (["ls", "Outro Cliente.Workspace"], False),
    (["ls", "WS Fabric-Dev.Workspace/../Outro.Workspace"], False),
    (["ls", "Outro.Workspace/x.Lakehouse"], False),
    (["get", "WS Fabric-Dev.Workspace", "Outro.Workspace"], False),
    (["ls", "WS Fabric-Dev.Workspace Outro.Workspace"], False),
    (["ls", "x.Workspace:abc"], False),  # formato estranho: bloqueia
    (["rm", "WS Fabric-Dev.Workspace/x.Notebook"], False),
    (["export", "WS Fabric-Dev.Workspace/x.Notebook"], False),
    (["get", "WS Fabric-Dev.Workspace/x.Notebook", "-o", "saida"], False),
    (["api", "-X", "post", "workspaces"], False),
    (["auth", "login"], False),
    ([], False),
])
def test_verificar_fab(projeto, args, esperado):
    assert liberado(args, projeto(YAML)) is esperado


@pytest.mark.parametrize("nome", [
    "Produção", "BI - Vendas (PRD)", "Vendas 2.0", "Comercial & Marketing", "Time #1 Analytics",
    'Projeto "Alfa"', "Área: Financeiro", "UAT, Homologação", "[PRD] Data Platform", "ws_dev",
])
def test_qualquer_nome_de_workspace(projeto, nome):
    raiz = projeto(f"workspace_alvo: {_yaml_str(nome)}\n"
                   f"workspaces_leitura_extra: [{_yaml_str('Legado, Antigo')}]\n")
    assert guarda.target_workspaces(raiz) == {nome.lower(), "legado, antigo"}
    assert liberado(["exists", f"{nome}.Workspace"], raiz)
    assert liberado(["ls", f"{nome}.Workspace/lh.Lakehouse/Tables"], raiz)
    assert liberado(["ls", "Legado, Antigo.Workspace"], raiz)
    assert not liberado(["ls", "Outro.Workspace"], raiz)


@pytest.mark.parametrize("trecho, valores", [
    ('"WS Fabric-Dev"', ["WS Fabric-Dev"]),
    ('"WS Fabric-Dev"   # comentário', ["WS Fabric-Dev"]),
    ("Producao # c", ["Producao"]),
    ("'O''Neil BI'", ["O'Neil BI"]),
    ('"A, B", "C #2", D', ["A, B", "C #2", "D"]),
    ('"Projeto \\"Alfa\\""', ['Projeto "Alfa"']),
    ("", []),
    ('""', []),
])
def test_valores_yaml(trecho, valores):
    assert guarda._valores_yaml(trecho) == valores


def test_sem_projeto_so_listagem(tmp_path):
    assert liberado(["ls"], tmp_path)
    assert liberado(["exists", "Qualquer.Workspace"], tmp_path)
    assert not liberado(["get", "Qualquer.Workspace", "-q", "id"], tmp_path)


def test_projeto_sem_workspace_escolhido(projeto):
    raiz = projeto('workspace_alvo: ""\nworkspace_id: ""\n')
    assert guarda.target_workspaces(raiz) == set()
    assert liberado(["api", "workspaces"], raiz)  # usado por escolher_workspace.py --listar
    assert not liberado(["ls", "Algum.Workspace"], raiz)


@pytest.mark.parametrize("comando, esperado", [
    ('uv run python scripts/fab_ro.py exists "WS Fabric-Dev.Workspace"', True),
    ("uv run python scripts/fab_ro.py ls 'WS Fabric-Dev.Workspace/lh.Lakehouse/Tables' -l", True),
    ('uv run python scripts/fab_ro.py ls "Outro Cliente.Workspace"', False),
    ("uv run fab rm WS.Workspace/x.Notebook", False),
    ('& fab rm "a.Workspace"', False),
    ("echo oi && uv run fab export x", False),
])
def test_fab_pelo_terminal(projeto, comando, esperado):
    raiz = projeto(YAML)
    try:
        for args in guarda.fab_invocations(comando):
            guarda.verificar_fab(args, raiz)
        resultado = True
    except guarda.Bloqueio:
        resultado = False
    assert resultado is esperado


@pytest.mark.parametrize("comando, esperado", [
    ('grep -n "fab|fab =" arquivo.txt', True),  # "|" entre aspas não é pipe
    ("uv run fab auth login", False),
    ("uv run python scripts/fab_ro.py auth login", False),
    ("uv run python scripts/fab_ro.py ls | grep x", True),
    ("uv run python scripts/entrar.py --trocar", True),
    ("uv run python scripts/fab_ro.py auth status 2>&1", True),
    ("uv run python scripts/verificar_login.py", True),
    ("uv run python scripts/inventario.py", True),
    ("uv run python scripts/escolher_workspace.py --listar", True),
])
def test_comandos_de_terminal(fora_da_manutencao, comando, esperado):
    try:
        guarda.verificar_comando(comando)
        resultado = True
    except guarda.Bloqueio:
        resultado = False
    assert resultado is esperado


def test_leitura_de_item_nao_vai_para_arquivo(fora_da_manutencao):
    with pytest.raises(guarda.Bloqueio):
        guarda.verificar_comando('uv run python scripts/ler_item.py "x.Notebook" > saida.txt')
    guarda.verificar_comando('uv run python scripts/ler_item.py "x.Notebook" 2>&1')
