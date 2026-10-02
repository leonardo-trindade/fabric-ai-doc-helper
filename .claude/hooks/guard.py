"""Guarda do fabric-ai-doc-helper (hook PreToolUse do Claude Code).

Bloqueia, antes da execução:
  1. Acesso a arquivos fora da pasta do projeto (onde o repo foi clonado).
  2. Comandos de terminal que referenciam caminhos fora da pasta do projeto.
  3. Comandos `fab` de escrita e acesso a workspaces diferentes do informado
     em projeto/projeto.yaml (chave `workspace_alvo`).
  4. Alteração dos arquivos do assistente (CLAUDE.md, README, .claude/, scripts/,
     templates/, dependências) e dos arquivos de referência do usuário
     (projeto/referencias/, exceto a pasta gerada _texto/). Leitura é livre.

Modo manutenção (para evoluir o próprio repositório): crie MANUALMENTE, fora do
Claude, o arquivo vazio `.claude/MANUTENCAO`. Enquanto ele existir, a regra 4 fica
desligada (as demais continuam). O Claude não consegue criar esse arquivo.

Protocolo: recebe o JSON da chamada em stdin; sai com código 2 e o motivo em
stderr para bloquear; código 0 para liberar (as regras normais de permissão
do Claude Code continuam valendo).

Limite conhecido: para comandos de terminal a verificação é textual. Protege
contra erro e distração do modelo, não contra evasão deliberada. Isolamento
real exige o sandbox do Claude Code (macOS/Linux/WSL2) ou container.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Glob", "Grep"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# Subcomandos do fab que alteram algo no Fabric ou na configuração local.
FAB_WRITE = {"rm", "del", "mv", "cp", "copy", "import", "mkdir", "create", "set",
             "run", "start", "stop", "assign", "unassign", "ln", "load", "optimize",
             "vacuum", "label", "acl"}
FAB_WRITE_PAIRS = {("config", "set"), ("config", "clear-cache"), ("table", "load"),
                   ("table", "optimize"), ("table", "vacuum"), ("job", "run"),
                   ("job", "start"), ("acl", "set"), ("acl", "rm"), ("label", "set"),
                   ("label", "rm")}
# Sempre permitidos, mesmo sem projeto.yaml (login e verificação inicial).
FAB_FREE = {("auth",), ("--version",), ("--help",), ("-h",)}

SENSITIVE = [Path.home() / ".config" / "fab", Path.home() / ".ssh", Path.home() / ".azure"]
SAFE_DEVICES = {"/dev/null", "nul", "$null", "/dev/stdout", "/dev/stderr"}


# Arquivos/pastas somente leitura para o Claude (relativos à raiz do projeto).
PROTEGIDOS = ["CLAUDE.md", "README.md", "pyproject.toml", "uv.lock", ".python-version",
              ".mcp.json", ".gitignore", ".claude", "scripts", "templates",
              "projeto/referencias"]
LIBERADOS_DENTRO = ["projeto/referencias/_texto"]  # gerado por scripts/ler_referencia.py
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
VERBOS_ESCRITA = re.compile(
    r"(?ix)(?:^|[\s;&|(])(?:rm|rmdir|del|erase|rd|mv|move|ren|rename|truncate|touch|chmod|attrib|unlink|"
    r"tee|dd|install|ln|"
    r"sed\s+(?:-\w*\s+)*-i|perl\s+(?:-\w*\s+)*-i|"
    r"git\s+(?:rm|mv|checkout|restore|reset|clean|apply|am|stash)|"
    r"remove-item|move-item|rename-item|new-item|set-content|add-content|clear-content|"
    r"out-file|set-itemproperty|ri|mi|rni|ni|sc|ac|clc)(?=$|[\s;&|)])")
REDIR = re.compile(r">{1,2}\s*(\"[^\"]+\"|'[^']+'|[^\s;&|<>]+)")


def manutencao(root: Path) -> bool:
    return (root / ".claude" / "MANUTENCAO").exists()


def protegido(path: Path, root: Path) -> bool:
    p = norm(path)
    for livre in LIBERADOS_DENTRO:
        l = norm(root / livre)
        if p == l or p.startswith(l + os.sep):
            return False
    for item in PROTEGIDOS:
        alvo = norm(root / item)
        if p == alvo or p.startswith(alvo + os.sep):
            return True
    return False


def tokens_caminho(cmd: str, cwd: Path) -> list[tuple[str, Path]]:
    try:
        toks = shlex.split(cmd, posix=True)
    except ValueError:
        toks = cmd.split()
    out = []
    for t in toks:
        t = t.strip().strip(";&|()")
        if not t or t.startswith("-") or "://" in t:
            continue
        p = to_path(t.replace("*", "_").replace("?", "_"), cwd)
        if p is not None:
            out.append((t, p))
    return out


def check_protecao_arquivo(tool: str, ti: dict, cwd: Path, root: Path) -> None:
    for key in ("file_path", "notebook_path"):
        raw = ti.get(key)
        if raw:
            p = to_path(str(raw), cwd)
            if p is not None and protegido(p, root):
                block(f"{tool} em arquivo protegido ({raw}). Arquivos do assistente e referências são "
                      "somente leitura; peça ao usuário para alterar manualmente ou ativar o modo manutenção.")


COPIA = re.compile(r"(?i)(?:^|[\s;&|(])(cp|copy|copy-item|cpi|xcopy|robocopy)(?=\s)")


def check_protecao_shell(cmd: str, cwd: Path, root: Path) -> None:
    for m in REDIR.finditer(cmd):
        p = to_path(m.group(1), cwd)
        if p is not None and protegido(p, root):
            block(f"redirecionamento para arquivo protegido: {m.group(1)}")
    toks = tokens_caminho(cmd, cwd)
    alvos = [t for t, p in toks if protegido(p, root)]
    if not alvos:
        return
    if VERBOS_ESCRITA.search(cmd):
        block(f"comando que altera arquivo protegido ({alvos[0]}). Arquivos do assistente e "
              "referências são somente leitura.")
    # Cópia: ler de área protegida é permitido; gravar dentro dela, não.
    if COPIA.search(cmd) and protegido(toks[-1][1], root):
        block(f"cópia para dentro de área protegida: {toks[-1][0]}")


def block(reason: str) -> None:
    print(f"[guarda fabric-ai-doc-helper] BLOQUEADO: {reason}", file=sys.stderr)
    sys.exit(2)


def norm(p: Path) -> str:
    return os.path.normcase(os.path.abspath(os.path.realpath(p)))


def project_root(data: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())


def allowed_roots(root: Path) -> list[str]:
    roots = [norm(root)]
    # Pasta temporária do próprio Claude Code (rascunhos/scratchpad).
    roots.append(norm(Path(tempfile.gettempdir()) / "claude"))
    # Área do Claude Code para este usuário (memória, resultados de ferramentas).
    roots.append(norm(Path.home() / ".claude" / "projects"))
    return roots


def inside(path: Path, roots: list[str]) -> bool:
    p = norm(path)
    return any(p == r or p.startswith(r + os.sep) for r in roots)


def sensitive(path: Path) -> bool:
    p = norm(path)
    if os.path.basename(p) in {".env"}:
        return True
    return any(p == norm(s) or p.startswith(norm(s) + os.sep) for s in SENSITIVE)


def to_path(raw: str, cwd: Path) -> Path | None:
    s = raw.strip().strip("'\"")
    if not s or s.lower() in SAFE_DEVICES:
        return None
    s = os.path.expandvars(s)
    s = re.sub(r"%(\w+)%", lambda m: os.environ.get(m.group(1), m.group(0)), s)
    s = re.sub(r"\$env:(\w+)", lambda m: os.environ.get(m.group(1), m.group(0)), s, flags=re.I)
    s = os.path.expanduser(s)
    m = re.match(r"^/([a-zA-Z])(/.*)?$", s)  # Git Bash: /c/Users/... -> C:/Users/...
    if m and os.name == "nt":
        s = f"{m.group(1)}:{m.group(2) or '/'}"
    p = Path(s)
    return p if p.is_absolute() else cwd / p


# ---------------------------------------------------------------- arquivos
def check_file_tool(tool: str, ti: dict, cwd: Path, roots: list[str]) -> None:
    for key in ("file_path", "notebook_path", "path"):
        raw = ti.get(key)
        if not raw:
            continue
        p = to_path(str(raw), cwd)
        if p is None:
            continue
        if sensitive(p):
            block(f"{tool} em caminho sensível ({raw}).")
        if not inside(p, roots):
            block(f"{tool} fora da pasta do projeto: {raw}. Trabalhe apenas dentro de {roots[0]}.")


# ---------------------------------------------------------------- terminal
PATH_TOKEN = re.compile(
    r"""(?ix)
    (?:(?<![\w\\])[a-z]:[\\/][^\s"'|;&<>`)]*)   # C:\... ou C:/... (não "alteracoes:\n")
    | (?:(?<![\w.])/[a-z](?:/[^\s"'|;&<>`)]*)?)(?=[\s"'|;&<>`)]|$)  # /c/... (Git Bash)
    | (?:(?<![\w.~^@{-])~(?:[\\/][^\s"'|;&<>`)]*)?(?=[\s"'|;&<>`)\\/]|$))  # ~ ou ~/... (não HEAD~3)
    | (?:(?:\$HOME|\$env:\w+|%\w+%|\$\{?\w+\}?)[\\/][^\s"'|;&<>`)]*)  # variáveis de ambiente
    | (?:(?<![.\w])(?:\.\.[\\/])+[^\s"'|;&<>`)]*|(?<![.\w])\.\.(?=[\s"'|;&<>`)]|$))  # ../ (não "...")
    """
)
CD_CMD = re.compile(r"(?i)(?:^|[;&|]\s*|\b)(?:cd|pushd|set-location|sl|chdir)\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")
URL = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://\S+")


LEITURA_ITEM = re.compile(r"(?i)ler_item\.py|\bfab(?:\.exe)?\s+get\b.*\bdefinition\b")
GRAVACAO = re.compile(r"(?i)(?<![<>\d&])>{1,2}(?!\s*(?:/dev/null|\$null|nul)\b)|\btee\b|\bout-file\b|\bset-content\b|\badd-content\b")


def check_shell(cmd: str, cwd: Path, roots: list[str]) -> None:
    # Conteúdo de itens do workspace só pode ir para a tela, nunca para arquivo.
    if LEITURA_ITEM.search(cmd) and GRAVACAO.search(re.sub(r"2>&1|2>\s*(?:/dev/null|\$null|nul)\b", " ", cmd)):
        block("a leitura de itens do workspace não pode ser gravada em arquivo (use só a saída na tela).")
    scan = URL.sub(" ", cmd)  # URLs não são caminhos
    for m in CD_CMD.finditer(scan):
        p = to_path(m.group(1), cwd)
        if p is not None and not inside(p, roots):
            block(f"mudança de diretório para fora do projeto: {m.group(1)}")
    for m in PATH_TOKEN.finditer(scan):
        tok = m.group(0)
        p = to_path(tok, cwd)
        if p is None:
            continue
        if sensitive(p):
            block(f"comando referencia caminho sensível: {tok}")
        if not inside(p, roots):
            block(f"comando referencia caminho fora da pasta do projeto: {tok}")
    check_fab(cmd, cwd)


# ---------------------------------------------------------------- fab
def target_workspaces(root: Path) -> set[str] | None:
    cfg = root / "projeto" / "projeto.yaml"
    if not cfg.exists():
        return None
    text = cfg.read_text(encoding="utf-8", errors="ignore")
    names: set[str] = set()
    m = re.search(r"(?m)^\s*workspace_alvo:\s*[\"']?([^\"'\n#]+?)[\"']?\s*(?:#.*)?$", text)
    if m:
        names.add(m.group(1).strip().lower())
    m = re.search(r"(?m)^\s*workspaces_leitura_extra:\s*\[([^\]]*)\]", text)
    if m:
        names |= {x.strip().strip("\"'").lower() for x in m.group(1).split(",") if x.strip()}
    return names


def fab_invocations(cmd: str) -> list[list[str]]:
    out = []
    for seg in re.split(r"&&|\|\||[;|\n]", cmd):
        try:
            toks = shlex.split(seg, posix=True)
        except ValueError:
            toks = seg.split()
        # `fab` só conta na posição de comando: início do segmento, depois de `uv run`,
        # `&`/`call` (PowerShell/cmd) ou de atribuições VAR=valor. Evita falso positivo
        # em `grep fab arquivo`.
        i = 0
        while i < len(toks) and (re.match(r"^\w+=", toks[i]) or toks[i].lower() in {"&", "call"}):
            i += 1
        if i + 1 < len(toks) and toks[i].lower() in {"uv", "uv.exe"} and toks[i + 1] == "run":
            i += 2
            while i < len(toks) and toks[i].startswith("-"):
                i += 1
        if i < len(toks) and os.path.basename(toks[i].replace("\\", "/")).lower() in {"fab", "fab.exe"}:
            out.append(toks[i + 1:])
    return out


def check_fab(cmd: str, cwd: Path) -> None:
    calls = fab_invocations(cmd)
    if not calls:
        return
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    allowed_ws = target_workspaces(root)
    for args in calls:
        words = [a for a in args if not a.startswith("-")]
        first = words[0].lower() if words else (args[0].lower() if args else "")
        second = words[1].lower() if len(words) > 1 else ""
        if first == "auth" and second == "login" and not any(a in {"--help", "-h"} for a in args):
            block("o login no Fabric é manual: peça ao usuário para rodar `uv run fab auth login` no terminal dele.")
        if (first,) in FAB_FREE or first in {"--version", "--help", "-h"}:
            continue
        if first in FAB_WRITE or (first, second) in FAB_WRITE_PAIRS:
            block(f"`fab {first} {second}`: o projeto é somente leitura.")
        if first == "export":
            block("`fab export` copia arquivos do workspace. Leia itens com `uv run python scripts/ler_item.py` (sem gravar).")
        if any(a.lower() in {"-o", "--output"} for a in args):
            block("saída de `fab` para arquivo (-o/--output): nada do workspace é gravado localmente.")
        if first == "api":
            joined = " ".join(args).lower()
            m = re.search(r"(?:-x|--method)\s+(\w+)", joined)
            if m and m.group(1) != "get":
                block("`fab api` com método diferente de GET: o projeto é somente leitura.")
        if first == "auth" or first == "config":
            continue
        # Workspaces citados no comando (padrão Nome.Workspace)
        cited = {w.lower() for w in re.findall(r"([^\s\"'/]+?)\.workspace\b", " ".join(args), flags=re.I)}
        cited |= {w.lower() for w in re.findall(r"[\"']([^\"']+?)\.workspace", " ".join(args), flags=re.I)}
        if allowed_ws is None:
            # Antes da entrevista: só verificação de existência/listagem.
            if first in {"exists", "ls", "dir"}:
                continue
            block("projeto/projeto.yaml ainda não existe. Rode a entrevista (/iniciar-projeto) antes de acessar o Fabric.")
        for ws in cited:
            if ws not in allowed_ws:
                block(f"workspace '{ws}' não está autorizado em projeto/projeto.yaml (permitidos: {', '.join(sorted(allowed_ws))}).")
        if first in {"ls", "dir"} and not cited and not any(a.startswith(".") for a in words[1:]):
            # `fab ls` na raiz lista todos os workspaces: apenas nomes, liberado.
            continue


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    root = project_root(data)
    cwd = Path(data.get("cwd") or root)
    roots = allowed_roots(root)
    if tool in FILE_TOOLS:
        check_file_tool(tool, ti, cwd, roots)
        if tool in EDIT_TOOLS and not manutencao(root):
            check_protecao_arquivo(tool, ti, cwd, root)
    elif tool in SHELL_TOOLS:
        cmd = str(ti.get("command", ""))
        check_shell(cmd, cwd, roots)
        if not manutencao(root):
            check_protecao_shell(cmd, cwd, root)


if __name__ == "__main__":
    main()
