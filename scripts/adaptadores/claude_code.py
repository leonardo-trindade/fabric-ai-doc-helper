"""Adaptador da guarda para o Claude Code (hook PreToolUse em .claude/settings.json).

Traduz o evento do Claude Code para as regras de scripts/guarda.py.
Protocolo: recebe o JSON da chamada em stdin; sai com código 2 e o motivo em stderr para
bloquear; código 0 para liberar (as regras normais de permissão do Claude Code continuam valendo).
Se a guarda não puder ser carregada, bloqueia por segurança.

Para outra ferramenta, crie scripts/adaptadores/<ferramenta>.py no mesmo molde: leia o evento
no formato dela, chame `guarda.verificar_arquivo` / `guarda.verificar_comando` e responda
no protocolo de bloqueio dela. Use só a biblioteca padrão (o hook roda sem o ambiente do projeto).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
try:
    sys.path.insert(0, str(RAIZ / "scripts"))
    import guarda  # noqa: E402
except Exception as e:  # noqa: BLE001
    print(f"[guarda fabric-ai-doc-helper] BLOQUEADO: guarda indisponível ({e}).", file=sys.stderr)
    sys.exit(2)

FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Glob", "Grep"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
# Áreas de trabalho do próprio Claude Code: rascunhos (scratchpad), memória e resultados de ferramentas.
RAIZES_CLAUDE = [Path(tempfile.gettempdir()) / "claude", Path.home() / ".claude" / "projects"]


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    try:
        if tool in FILE_TOOLS:
            for key in ("file_path", "notebook_path", "path"):
                if ti.get(key):
                    guarda.verificar_arquivo(str(ti[key]), escrita=tool in EDIT_TOOLS, cwd=cwd,
                                             raizes_extra=RAIZES_CLAUDE)
        elif tool in SHELL_TOOLS:
            guarda.verificar_comando(str(ti.get("command", "")), cwd=cwd, raizes_extra=RAIZES_CLAUDE)
    except guarda.Bloqueio as e:
        print(f"[guarda fabric-ai-doc-helper] BLOQUEADO: {tool}: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
