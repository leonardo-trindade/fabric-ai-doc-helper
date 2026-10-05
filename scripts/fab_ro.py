"""Executa o Fabric CLI (`fab`) somente com comandos de LEITURA permitidos neste projeto.

É a forma padrão de o assistente usar o `fab`, em qualquer ferramenta (com ou sem hooks):
as regras de scripts/guarda.py são aplicadas antes da execução e, com o projeto configurado,
a conta logada é conferida com a registrada em projeto/projeto.yaml.

Uso (mesmos argumentos do `fab`):
    uv run python scripts/fab_ro.py ls "<ws>.Workspace" -l
    uv run python scripts/fab_ro.py table schema "<ws>.Workspace/<lh>.Lakehouse/Tables/<schema>/<tabela>"
    uv run python scripts/fab_ro.py auth status

Códigos de saída: 2 = bloqueado pela guarda; demais = código do próprio `fab`.
Login: `uv run python scripts/entrar.py` (o usuário escolhe a conta no navegador).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import PROJETO, checar_login, config, fab_exe  # noqa: E402
from guarda import Bloqueio, verificar_fab  # noqa: E402

SEM_CONFERIR_LOGIN = {"auth", "--version", "--help", "-h"}


def main() -> None:
    args = sys.argv[1:]
    try:
        verificar_fab(args)
    except Bloqueio as e:
        print(f"[guarda fabric-ai-doc-helper] BLOQUEADO: {e}", file=sys.stderr)
        sys.exit(2)
    if args[0].lower() not in SEM_CONFERIR_LOGIN and "--help" not in args and (PROJETO / "projeto.yaml").exists():
        checar_login(config(exigir_workspace=False))
    sys.exit(subprocess.run([fab_exe(), *args]).returncode)


if __name__ == "__main__":
    main()
