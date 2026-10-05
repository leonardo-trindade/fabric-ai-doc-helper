"""Login no Fabric CLI pelo navegador, já escolhendo "Interactive with a web browser".

O assistente roda este script; o usuário só escolhe a conta e faz o login no navegador
(o assistente nunca vê senha nem token). Depois do login, a conta é comparada com a do projeto
(mesma saída e códigos de scripts/verificar_login.py).

Uso:
    uv run python scripts/entrar.py               # login, se não houver nenhum ativo
    uv run python scripts/entrar.py --trocar      # logout da conta atual + login
                                                  # (SOMENTE com permissão explícita do usuário)
    uv run python scripts/entrar.py --outro-tenant  # não força o tenant registrado no projeto
                                                    # (usuário decidiu trocar a conta do projeto)

Se o projeto já tem `tenant_id`, o login é feito nesse tenant (evita entrar no cliente errado).
O login fica pendente até o usuário concluir no navegador (até alguns minutos).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import PROJETO, fab, sessao_fab  # noqa: E402

import yaml  # noqa: E402

OPCAO_NAVEGADOR = "Interactive with a web browser"


def tenant_do_projeto() -> str:
    cfg = PROJETO / "projeto.yaml"
    if not cfg.exists():
        return ""
    dados = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    return (dados.get("tenant_id") or "").strip()


def login_navegador(tenant: str) -> None:
    """Roda `fab auth login` no próprio processo, respondendo o menu com o login pelo navegador."""
    from fabric_cli import main as fab_main
    from fabric_cli.core import fab_constant
    from fabric_cli.core.fab_auth import FabAuth
    from fabric_cli.utils import fab_ui

    def escolher_navegador(pergunta, opcoes):  # substitui o menu interativo do fab
        return OPCAO_NAVEGADOR if OPCAO_NAVEGADOR in opcoes else None

    # O login pede 3 tokens (Fabric, OneLake, Azure) e cada um que não sai em silêncio abre a
    # janela de escolha de conta de novo. Só o do Fabric pode abrir a janela; OneLake e Azure
    # são tentados em silêncio com o mesmo login (o Azure nem é usado pelo projeto).
    original = FabAuth.get_access_token

    def um_login_so(self, scope, interactive_renew=True):
        if scope == fab_constant.SCOPE_FABRIC_DEFAULT:
            return original(self, scope, interactive_renew)
        try:
            return original(self, scope, interactive_renew=False)
        except Exception:  # noqa: BLE001  (sem token silencioso: explicar_tokens() avisa)
            return None

    fab_ui.prompt_select_item = escolher_navegador
    FabAuth.get_access_token = um_login_so
    sys.argv = ["fab", "auth", "login", *(["--tenant", tenant] if tenant else [])]
    fab_main.main()


def explicar_tokens() -> None:
    """O `fab auth login` pede três tokens (Fabric, OneLake/Storage, Azure). Se o 2º ou o 3º falhar,
    ele mostra "Failed to get access token" mesmo com o login do Fabric válido. Diz o que importa."""
    status = fab("auth", "status", check=False)
    tem = lambda rotulo: bool(re.search(rf"{rotulo}:\s*(?!N/A)\S", status))  # noqa: E731
    if not tem("Token Storage"):
        print("Aviso: o login do Fabric está ativo, mas o token do OneLake (Storage) não foi obtido. "
              "Listar tabelas e arquivos dos Lakehouses pode falhar; se falhar, rode o login de novo.")
    if not tem("Token Azure"):
        print("Obs.: o token do Azure não foi obtido (aviso \"Failed to get access token\"). "
              "Ele não é usado neste projeto; pode ignorar.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trocar", action="store_true", help="faz logout da conta atual antes do login")
    ap.add_argument("--outro-tenant", action="store_true", help="não força o tenant registrado no projeto")
    a = ap.parse_args()

    atual = sessao_fab()
    if atual["logado"] and not a.trocar:
        print(f"Já existe login ativo: {atual['conta']} (tenant {atual['tenant_id']}).")
        print("Para trocar de conta, peça permissão ao usuário e rode: uv run python scripts/entrar.py --trocar")
        sys.exit(subprocess.run([sys.executable, str(Path(__file__).with_name("verificar_login.py"))]).returncode)

    if a.trocar and atual["logado"]:
        fab("auth", "logout", check=False)
        print(f"Logout feito ({atual['conta']}).")

    tenant = "" if a.outro_tenant else tenant_do_projeto()
    print("Abrindo o login da Microsoft (navegador ou janela do Windows). Escolha a conta do cliente"
          + (f" no tenant {tenant}" if tenant else "") + "…", flush=True)
    try:
        login_navegador(tenant)
    except SystemExit:
        pass

    if not sessao_fab()["logado"]:
        print("O login não foi concluído (janela fechada ou cancelada). Rode de novo quando o usuário estiver pronto.")
        sys.exit(3)
    explicar_tokens()
    sys.exit(subprocess.run([sys.executable, str(Path(__file__).with_name("verificar_login.py"))]).returncode)


if __name__ == "__main__":
    main()
