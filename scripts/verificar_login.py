"""Mostra a conta logada no Fabric CLI e compara com a registrada no projeto (nunca exibe tokens).

Uso:
    uv run python scripts/verificar_login.py              # verificar
    uv run python scripts/verificar_login.py --registrar  # grava conta/tenant ativos no projeto.yaml
                                                          # (somente após o usuário CONFIRMAR a conta)

Códigos de saída:
    0  logado na conta registrada no projeto
    3  sem login (rode `uv run python scripts/entrar.py`)
    4  logado em OUTRA conta/tenant (confirmar com o usuário; se errado: logout + login)
    5  logado, mas o projeto ainda não tem conta registrada (confirmar com o usuário e --registrar)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import PROJETO, sessao_fab  # noqa: E402

import yaml  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args()

    s = sessao_fab()
    cfg_path = PROJETO / "projeto.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    cfg = cfg or {}
    conta_esp = (cfg.get("conta_fabric") or "").strip()
    tenant_esp = (cfg.get("tenant_id") or "").strip()

    if not s["logado"]:
        print("SEM LOGIN no Fabric CLI.")
        print("Ação: avise o usuário e rode: uv run python scripts/entrar.py (login pelo navegador)")
        sys.exit(3)

    print(f"Conta logada : {s['conta']}")
    print(f"Tenant       : {s['tenant_id']}")
    if cfg:
        print(f"Projeto      : {cfg.get('cliente', '?')} · {cfg.get('projeto', '?')} · workspace {cfg.get('workspace_alvo', '?')}")

    if a.registrar:
        if not cfg_path.exists():
            sys.exit("projeto/projeto.yaml ainda não existe; crie-o na entrevista antes de registrar a conta.")
        txt = cfg_path.read_text(encoding="utf-8")
        for chave, valor in (("conta_fabric", s["conta"]), ("tenant_id", s["tenant_id"])):
            if re.search(rf"(?m)^{chave}:", txt):
                txt = re.sub(rf'(?m)^{chave}:.*$', f'{chave}: "{valor}"', txt)
            else:
                txt = txt.rstrip() + f'\n{chave}: "{valor}"\n'
        cfg_path.write_text(txt, encoding="utf-8")
        print("Conta e tenant registrados em projeto/projeto.yaml.")
        sys.exit(0)

    if not conta_esp and not tenant_esp:
        print("RESULTADO: projeto sem conta registrada. Confirme com o usuário se esta é a conta do cliente;")
        print("se sim: uv run python scripts/verificar_login.py --registrar")
        print("se não: com permissão do usuário, rode: uv run python scripts/entrar.py --trocar")
        sys.exit(5)

    ok_conta = not conta_esp or (s["conta"] or "").lower() == conta_esp.lower()
    ok_tenant = not tenant_esp or (s["tenant_id"] or "").lower() == tenant_esp.lower()
    if ok_conta and ok_tenant:
        print(f"RESULTADO: OK — conta do projeto ({conta_esp or tenant_esp}).")
        sys.exit(0)
    print(f"RESULTADO: CONTA DIFERENTE. O projeto espera {conta_esp or '?'} (tenant {tenant_esp or '?'}).")
    print("Ação: mostre as duas contas e peça permissão para trocar; se sim: uv run python scripts/entrar.py --trocar")
    sys.exit(4)


if __name__ == "__main__":
    main()
