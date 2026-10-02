"""Hook SessionStart do Claude Code: prepara o ambiente e confere a conta do Fabric no início da conversa.

- Sem `.venv`: roda `uv sync` (primeira abertura da pasta).
- Roda scripts/verificar_login.py e entrega ao assistente o estado do projeto e da conta, com a
  ação esperada (registrar, logar ou trocar de conta com permissão do usuário).
- Mostra ao usuário uma linha de resumo.

Só biblioteca padrão (roda com `uv run --no-project`). Nunca bloqueia a sessão: em erro, só avisa.
Para outra ferramenta com hook de início, reaproveite `resumo()` no adaptador dela.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
YAML = RAIZ / "projeto" / "projeto.yaml"

ACOES = {
    0: "Conta do Fabric confere com a registrada no projeto. Informe em uma linha e siga.",
    3: ("Não há login ativo no Fabric (ou o login expirou). Avise o usuário que a janela de login da "
        "Microsoft vai abrir e rode `uv run python scripts/entrar.py`."),
    4: ("A conta logada NÃO é a do projeto (o usuário pode ter entrado em outra conta). Mostre as duas "
        "contas e PEÇA PERMISSÃO para fazer logout da atual. Se ele aceitar: "
        "`uv run python scripts/entrar.py --trocar`. Não acesse o Fabric antes disso."),
    5: ("O projeto ainda não tem conta registrada. Mostre a conta e o tenant e pergunte se é a conta do "
        "cliente. Se sim: `uv run python scripts/verificar_login.py --registrar`. Se não: PEÇA PERMISSÃO "
        "para logout e rode `uv run python scripts/entrar.py --trocar --outro-tenant`."),
}


def campo(texto: str, chave: str) -> str:
    m = re.search(rf"(?m)^{chave}:\s*[\"']?([^\"'\n#]*)", texto)
    return m.group(1).strip() if m else ""


def uv(*args: str, timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(["uv", *args], cwd=RAIZ, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def resumo() -> tuple[str, str]:
    """(contexto para o assistente, linha para o usuário)."""
    ctx, linha = ["[Início de sessão — fabric-ai-doc-helper]"], []

    if not (RAIZ / ".venv").exists():
        r = uv("sync", "--quiet")
        if r.returncode != 0:
            msg = (r.stderr or r.stdout).strip()[-400:]
            return (f"Falha no `uv sync` ao preparar o ambiente: {msg}. Explique ao usuário e consulte o "
                    "README (Problemas comuns).", "Falha ao preparar o ambiente (uv sync).")
        ctx.append("Ambiente instalado agora (uv sync).")

    if YAML.exists():
        t = YAML.read_text(encoding="utf-8", errors="ignore")
        ctx.append(f"Projeto: {campo(t, 'cliente')} · {campo(t, 'projeto')} · workspace "
                   f"{campo(t, 'workspace_alvo') or '(não definido)'}.")
        linha.append(f"{campo(t, 'cliente')} · {campo(t, 'projeto')}")
        if not campo(t, "workspace_alvo") or not campo(t, "autor"):
            ctx.append("projeto.yaml incompleto: complete a entrevista (skill iniciar-projeto).")
    else:
        ctx.append("Sem projeto/projeto.yaml: depois da conta, faça a entrevista (skill iniciar-projeto).")
        linha.append("projeto novo")

    if (RAIZ / "projeto" / "analise" / "notas.md").exists():
        ctx.append("Existe projeto/analise/notas.md: leia antes de ir ao Fabric.")

    try:
        r = uv("run", "--quiet", "python", "scripts/verificar_login.py", timeout=90)
        saida = "\n".join(l for l in r.stdout.splitlines() if l.startswith(("Conta logada", "Tenant", "RESULTADO")))
        ctx.append(f"Conta do Fabric (scripts/verificar_login.py, código {r.returncode}):\n{saida or r.stdout.strip()}")
        ctx.append("Ação: " + ACOES.get(r.returncode, "Verifique a conta com scripts/verificar_login.py."))
        conta = re.search(r"Conta logada\s*:\s*(\S+)", r.stdout)
        linha.append({0: f"conta OK ({conta.group(1) if conta else '?'})", 3: "sem login no Fabric",
                      4: "CONTA DIFERENTE da do projeto", 5: f"conta a confirmar ({conta.group(1) if conta else '?'})"}
                     .get(r.returncode, "conta não verificada"))
    except Exception as e:  # noqa: BLE001
        ctx.append(f"Não foi possível verificar a conta ({e}). Rode scripts/verificar_login.py antes de acessar o Fabric.")
        linha.append("conta não verificada")

    return "\n".join(ctx), "Fabric Doc Helper: " + " · ".join(linha)


def main() -> None:
    try:
        contexto, linha = resumo()
    except Exception as e:  # noqa: BLE001
        contexto, linha = f"Hook de início falhou ({e}). Siga os Primeiros passos do AGENTS.md.", "Fabric Doc Helper: verificação inicial falhou"
    json.dump({"systemMessage": linha,
               "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": contexto}},
              sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
