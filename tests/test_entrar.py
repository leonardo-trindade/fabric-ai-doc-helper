"""entrar.py: uma janela de login só e explicação dos tokens que faltaram (sem login real)."""
from __future__ import annotations

import pytest
from fabric_cli.core import fab_constant
from fabric_cli.core.fab_auth import FabAuth

import entrar


@pytest.fixture
def auth_real():
    """A instância única (singleton) do FabAuth real; desfaz a troca que entrar.py faz nela."""
    auth = FabAuth()
    yield auth
    auth.__dict__.pop("get_access_token", None)


def test_so_o_token_do_fabric_abre_janela(monkeypatch, auth_real):
    janelas, chamadas = [], []

    def token_falso(self, scope, interactive_renew=True):
        """Imita o fab: OneLake sai em silêncio; Azure falha em silêncio; Fabric pede janela."""
        nome = {tuple(fab_constant.SCOPE_FABRIC_DEFAULT): "fabric",
                tuple(fab_constant.SCOPE_ONELAKE_DEFAULT): "onelake",
                tuple(fab_constant.SCOPE_AZURE_DEFAULT): "azure"}[tuple(scope)]
        chamadas.append((nome, interactive_renew))
        if nome == "onelake":
            return "tok"
        if interactive_renew:
            janelas.append(nome)
            return "tok"
        raise RuntimeError("Failed to get access token")

    def login_falso():  # mesma sequência e mesma chamada de fabric_cli/commands/auth/fab_auth.py: init()
        for escopo in (fab_constant.SCOPE_FABRIC_DEFAULT, fab_constant.SCOPE_ONELAKE_DEFAULT,
                       fab_constant.SCOPE_AZURE_DEFAULT):
            FabAuth().get_access_token(scope=escopo)

    import fabric_cli.main as fab_main
    monkeypatch.setattr(type(auth_real), "get_access_token", token_falso)  # a classe real, atrás do singleton
    monkeypatch.setattr(fab_main, "main", login_falso)
    entrar.login_navegador("")
    assert janelas == ["fabric"]
    assert chamadas == [("fabric", True), ("onelake", False), ("azure", False)]


@pytest.mark.parametrize("status, avisos", [
    ("Token Fabric PowerBI: eyJ0***\nToken Storage: eyJ0***\nToken Azure: N/A", ["Azure"]),
    ("Token Storage: N/A\nToken Azure: N/A", ["OneLake", "Azure"]),
    ("Token Storage: eyJ0**\nToken Azure: eyJ0**", []),
])
def test_explicar_tokens(monkeypatch, capsys, status, avisos):
    monkeypatch.setattr(entrar, "fab", lambda *a, check=True: status)
    entrar.explicar_tokens()
    saida = capsys.readouterr().out
    for termo in ("OneLake", "Azure"):
        assert (termo in saida) is (termo in avisos)
