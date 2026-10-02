"""Guarda do fabric-ai-doc-helper: regras independentes de ferramenta (somente biblioteca padrão).

Bloqueia, antes da execução:
  1. Acesso a arquivos fora da pasta do projeto (onde o repo foi clonado).
  2. Comandos de terminal que referenciam caminhos fora da pasta do projeto.
  3. Comandos `fab` de escrita e acesso a workspaces diferentes do informado
     em projeto/projeto.yaml (chave `workspace_alvo`).
  4. Alteração dos arquivos do assistente (AGENTS.md, CLAUDE.md, README, .agents/, .claude/,
     scripts/, templates/, dependências) e dos arquivos de referência do usuário
     (projeto/referencias/, exceto a pasta gerada _texto/). Leitura é livre.

Quem usa:
  - scripts/fab_ro.py e scripts/_comum.py: validam todo comando `fab` (vale em qualquer ferramenta).
  - scripts/adaptadores/<ferramenta>.py: traduzem o evento de hook de cada ferramenta para
    `verificar_arquivo` / `verificar_comando`.
  - Linha de comando, para ferramentas cujo hook só executa um comando:
        python scripts/guarda.py arquivo leitura|escrita <caminho> [--cwd DIR]
        python scripts/guarda.py comando "<comando>" [--cwd DIR]
        python scripts/guarda.py fab <args do fab...>
    Sai com código 2 e o motivo em stderr para bloquear; 0 para liberar.

Modo manutenção (para evoluir o próprio repositório): o usuário cria MANUALMENTE o arquivo
vazio `.agents/MANUTENCAO`. Enquanto ele existir, a regra 4 fica desligada (as demais
continuam). O próprio arquivo de manutenção nunca pode ser criado/alterado pelo assistente.

Limite conhecido: para comandos de terminal a verificação é textual. Protege contra erro e
distração do modelo, não contra evasão deliberada. Isolamento real exige sandbox ou container.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MANUTENCAO = Path(".agents") / "MANUTENCAO"


class Bloqueio(Exception):
    """Ação proibida pela guarda (a mensagem explica o motivo)."""


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

# Arquivos/pastas somente leitura para o assistente (relativos à raiz do projeto).
PROTEGIDOS = ["AGENTS.md", "CLAUDE.md", "README.md", "pyproject.toml", "uv.lock", ".python-version",
              ".mcp.json", ".gitignore", ".agents", ".claude", "scripts", "templates",
              "projeto/referencias"]
LIBERADOS_DENTRO = ["projeto/referencias/_texto"]  # gerado por scripts/ler_referencia.py
SEMPRE_PROTEGIDOS = [str(MANUTENCAO)]  # nem em modo manutenção
VERBOS_ESCRITA = re.compile(
    r"(?ix)(?:^|[\s;&|(])(?:rm|rmdir|del|erase|rd|mv|move|ren|rename|truncate|touch|chmod|attrib|unlink|"
    r"tee|dd|install|ln|"
    r"sed\s+(?:-\w*\s+)*-i|perl\s+(?:-\w*\s+)*-i|"
    r"git\s+(?:rm|mv|checkout|restore|reset|clean|apply|am|stash)|"
    r"remove-item|move-item|rename-item|new-item|set-content|add-content|clear-content|"
    r"out-file|set-itemproperty|ri|mi|rni|ni|sc|ac|clc)(?=$|[\s;&|)])")
REDIR = re.compile(r">{1,2}\s*(\"[^\"]+\"|'[^']+'|[^\s;&|<>]+)")
COPIA = re.compile(r"(?i)(?:^|[\s;&|(])(cp|copy|copy-item|cpi|xcopy|robocopy)(?=\s)")


# ---------------------------------------------------------------- caminhos
def em_manutencao(root: Path = RAIZ) -> bool:
    return (root / MANUTENCAO).exists()


def norm(p: Path) -> str:
    return os.path.normcase(os.path.abspath(os.path.realpath(p)))


def _sob(p: str, base: str) -> bool:
    return p == base or p.startswith(base + os.sep)


def protegido(path: Path, root: Path, sempre: bool = False) -> bool:
    p = norm(path)
    if any(_sob(p, norm(root / item)) for item in SEMPRE_PROTEGIDOS):
        return True
    if sempre:
        return False
    if any(_sob(p, norm(root / livre)) for livre in LIBERADOS_DENTRO):
        return False
    return any(_sob(p, norm(root / item)) for item in PROTEGIDOS)


def allowed_roots(root: Path, extras: list[Path] | tuple = ()) -> list[str]:
    # extras: áreas de trabalho próprias de cada ferramenta (informadas pelo adaptador).
    return [norm(root), *(norm(Path(e)) for e in extras)]


def inside(path: Path, roots: list[str]) -> bool:
    p = norm(path)
    return any(_sob(p, r) for r in roots)


def sensitive(path: Path) -> bool:
    p = norm(path)
    if os.path.basename(p) in {".env"}:
        return True
    return any(_sob(p, norm(s)) for s in SENSITIVE)


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


def tokens_caminho(cmd: str, cwd: Path) -> list[tuple[str, Path]]:
    try:
        toks = shlex.split(cmd, posix=False)  # preserva "\" de caminhos Windows; aspas saem em to_path
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


# ---------------------------------------------------------------- arquivos
def verificar_arquivo(raw: str, *, escrita: bool = False, cwd: Path | str | None = None,
                      raizes_extra: list[Path] | tuple = (), root: Path = RAIZ) -> None:
    """Valida leitura/escrita de um caminho por uma ferramenta de arquivos do assistente."""
    cwd = Path(cwd or root)
    p = to_path(str(raw), cwd)
    if p is None:
        return
    if sensitive(p):
        raise Bloqueio(f"caminho sensível ({raw}).")
    roots = allowed_roots(root, raizes_extra)
    if not inside(p, roots):
        raise Bloqueio(f"fora da pasta do projeto: {raw}. Trabalhe apenas dentro de {roots[0]}.")
    if escrita and protegido(p, root, sempre=em_manutencao(root)):
        raise Bloqueio(f"arquivo protegido ({raw}). Arquivos do assistente e referências são "
                       "somente leitura; peça ao usuário para alterar manualmente ou ativar o modo manutenção.")


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
LEITURA_ITEM = re.compile(r"(?i)ler_item\.py|\bfab(?:\.exe|_ro\.py)?\s+get\b.*\bdefinition\b")
GRAVACAO = re.compile(r"(?i)(?<![<>\d&])>{1,2}(?!\s*(?:/dev/null|\$null|nul)\b)|\btee\b|\bout-file\b|\bset-content\b|\badd-content\b")


def verificar_comando(cmd: str, *, cwd: Path | str | None = None,
                      raizes_extra: list[Path] | tuple = (), root: Path = RAIZ) -> None:
    """Valida um comando de terminal (bash/PowerShell) antes da execução."""
    cwd = Path(cwd or root)
    roots = allowed_roots(root, raizes_extra)
    # Conteúdo de itens do workspace só pode ir para a tela, nunca para arquivo.
    if LEITURA_ITEM.search(cmd) and GRAVACAO.search(re.sub(r"2>&1|2>\s*(?:/dev/null|\$null|nul)\b", " ", cmd)):
        raise Bloqueio("a leitura de itens do workspace não pode ser gravada em arquivo (use só a saída na tela).")
    scan = URL.sub(" ", cmd)  # URLs não são caminhos
    for m in CD_CMD.finditer(scan):
        p = to_path(m.group(1), cwd)
        if p is not None and not inside(p, roots):
            raise Bloqueio(f"mudança de diretório para fora do projeto: {m.group(1)}")
    for m in PATH_TOKEN.finditer(scan):
        tok = m.group(0)
        p = to_path(tok, cwd)
        if p is None:
            continue
        if sensitive(p):
            raise Bloqueio(f"comando referencia caminho sensível: {tok}")
        if not inside(p, roots):
            raise Bloqueio(f"comando referencia caminho fora da pasta do projeto: {tok}")
    for args in fab_invocations(cmd):
        verificar_fab(args, root)
    _protecao_shell(cmd, cwd, root, sempre=em_manutencao(root))


def _protecao_shell(cmd: str, cwd: Path, root: Path, sempre: bool) -> None:
    for m in REDIR.finditer(cmd):
        p = to_path(m.group(1), cwd)
        if p is not None and protegido(p, root, sempre):
            raise Bloqueio(f"redirecionamento para arquivo protegido: {m.group(1)}")
    toks = tokens_caminho(cmd, cwd)
    alvos = [t for t, p in toks if protegido(p, root, sempre)]
    if not alvos:
        return
    if VERBOS_ESCRITA.search(cmd):
        raise Bloqueio(f"comando que altera arquivo protegido ({alvos[0]}). Arquivos do assistente e "
                       "referências são somente leitura.")
    # Cópia: ler de área protegida é permitido; gravar dentro dela, não.
    if COPIA.search(cmd) and protegido(toks[-1][1], root, sempre):
        raise Bloqueio(f"cópia para dentro de área protegida: {toks[-1][0]}")


# ---------------------------------------------------------------- fab
def target_workspaces(root: Path = RAIZ) -> set[str] | None:
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
    """Argumentos de cada chamada a `fab` (direta ou via scripts/fab_ro.py) num comando."""
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
        base = lambda t: os.path.basename(t.replace("\\", "/")).lower()  # noqa: E731
        if i + 1 < len(toks) and base(toks[i]) in {"python", "python.exe", "python3"} \
                and base(toks[i + 1]) == "fab_ro.py":
            out.append(toks[i + 2:])
        elif i < len(toks) and base(toks[i]) in {"fab", "fab.exe"}:
            out.append(toks[i + 1:])
    return out


def verificar_fab(args: list[str], root: Path = RAIZ) -> None:
    """Valida os argumentos de uma chamada ao Fabric CLI (sem o `fab` inicial)."""
    if not args:
        raise Bloqueio("`fab` sem argumentos abre o modo interativo; use um comando por vez.")
    words = [a for a in args if not a.startswith("-")]
    first = words[0].lower() if words else args[0].lower()
    second = words[1].lower() if len(words) > 1 else ""
    if first == "auth" and second == "login" and not any(a in {"--help", "-h"} for a in args):
        raise Bloqueio("o login no Fabric é manual: peça ao usuário para rodar `uv run fab auth login` no terminal dele.")
    if (first,) in FAB_FREE or first in {"--version", "--help", "-h"}:
        return
    if first in FAB_WRITE or (first, second) in FAB_WRITE_PAIRS:
        raise Bloqueio(f"`fab {first} {second}`: o projeto é somente leitura.")
    if first == "export":
        raise Bloqueio("`fab export` copia arquivos do workspace. Leia itens com `uv run python scripts/ler_item.py` (sem gravar).")
    if any(a.lower() in {"-o", "--output"} for a in args):
        raise Bloqueio("saída de `fab` para arquivo (-o/--output): nada do workspace é gravado localmente.")
    if first == "api":
        joined = " ".join(args).lower()
        m = re.search(r"(?:-x|--method)\s+(\w+)", joined)
        if m and m.group(1) != "get":
            raise Bloqueio("`fab api` com método diferente de GET: o projeto é somente leitura.")
    if first == "config":
        return
    # Workspaces citados no comando (padrão Nome.Workspace)
    cited = {w.lower() for w in re.findall(r"([^\s\"'/]+?)\.workspace\b", " ".join(args), flags=re.I)}
    cited |= {w.lower() for w in re.findall(r"[\"']([^\"']+?)\.workspace", " ".join(args), flags=re.I)}
    allowed_ws = target_workspaces(root)
    if allowed_ws is None:
        # Antes da entrevista: só verificação de existência/listagem.
        if first in {"exists", "ls", "dir"}:
            return
        raise Bloqueio("projeto/projeto.yaml ainda não existe. Rode a entrevista (skill iniciar-projeto) antes de acessar o Fabric.")
    for ws in cited:
        if ws not in allowed_ws:
            raise Bloqueio(f"workspace '{ws}' não está autorizado em projeto/projeto.yaml (permitidos: {', '.join(sorted(allowed_ws))}).")
    # `fab ls` na raiz lista todos os workspaces: apenas nomes, liberado.


# ---------------------------------------------------------------- linha de comando
def main() -> None:
    ap = argparse.ArgumentParser(description="Guarda do fabric-ai-doc-helper (código 2 = bloqueado).")
    sub = ap.add_subparsers(dest="modo", required=True)
    a_arq = sub.add_parser("arquivo")
    a_arq.add_argument("acesso", choices=["leitura", "escrita"])
    a_arq.add_argument("caminho")
    a_arq.add_argument("--cwd")
    a_cmd = sub.add_parser("comando")
    a_cmd.add_argument("comando")
    a_cmd.add_argument("--cwd")
    a_fab = sub.add_parser("fab")
    a_fab.add_argument("args", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    try:
        if a.modo == "arquivo":
            verificar_arquivo(a.caminho, escrita=a.acesso == "escrita", cwd=a.cwd)
        elif a.modo == "comando":
            verificar_comando(a.comando, cwd=a.cwd)
        else:
            verificar_fab(a.args)
    except Bloqueio as e:
        print(f"[guarda fabric-ai-doc-helper] BLOQUEADO: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
