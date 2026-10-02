"""Serviços do app Fabric Doc Helper: cadastro de projetos, detecção das ferramentas e abertura.

O app NÃO gerencia contas: a conta do Fabric é conferida pelo assistente em cada conversa
(hook de início + scripts/verificar_login.py) e fica registrada em projeto/projeto.yaml.

Dados do app (sem tokens, sem dados do workspace): %LOCALAPPDATA%/fabric-ai-doc-helper/app.json.
Cada projeto é uma pasta própria, clonada desta instalação (RAIZ), com os dados em projeto/.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]  # instalação do app (origem dos clones de projeto)
DADOS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "fabric-ai-doc-helper"
ARQUIVO = DADOS / "app.json"
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

FERRAMENTAS = {"vscode": "VS Code", "claude": "Claude Desktop"}


# ---------------------------------------------------------------- dados
@dataclass
class Projeto:
    id: str
    cliente: str
    projeto: str
    pasta: str
    ferramenta: str = "vscode"
    criado_em: str = ""
    ultimo_acesso: str = ""


@dataclass
class Config:
    autor: str = ""
    pasta_padrao: str = r"C:\Fabric"
    projetos: list[Projeto] = field(default_factory=list)


def carregar() -> Config:
    try:
        d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return Config()
    return Config(autor=d.get("autor", ""), pasta_padrao=d.get("pasta_padrao", r"C:\Fabric"),
                  projetos=[Projeto(**p) for p in d.get("projetos", [])])


def salvar(cfg: Config) -> None:
    DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")


def agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- comandos
def rodar(*args: str, cwd: Path | str | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, creationflags=SEM_JANELA)


def _erro(r: subprocess.CompletedProcess) -> str:
    return ((r.stderr or "") + (r.stdout or "")).strip()[-600:]


# ---------------------------------------------------------------- ferramentas
@dataclass
class Ferramentas:
    vscode: str | None = None          # caminho do executável do VS Code
    vscode_extensao: bool | None = None  # extensão Claude Code instalada (None = não verificado)
    claude_app_id: str | None = None   # AppID do Claude Desktop (Menu Iniciar)
    claude_exe: str | None = None      # instalação antiga (fora da Microsoft Store/MSIX)

    @property
    def tem_vscode(self) -> bool:
        return bool(self.vscode)

    @property
    def tem_claude(self) -> bool:
        return bool(self.claude_app_id or self.claude_exe)

    def disponivel(self, chave: str) -> bool:
        return self.tem_vscode if chave == "vscode" else self.tem_claude


def _vscode_exe() -> str | None:
    candidatos = []
    code = shutil.which("code")
    if code:  # .../Microsoft VS Code/bin/code.cmd -> .../Microsoft VS Code/Code.exe
        candidatos.append(Path(code).resolve().parent.parent / "Code.exe")
    try:
        import winreg
        for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                base = winreg.OpenKey(raiz, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
            except OSError:
                continue
            for i in range(winreg.QueryInfoKey(base)[0]):
                try:
                    k = winreg.OpenKey(base, winreg.EnumKey(base, i))
                    nome = winreg.QueryValueEx(k, "DisplayName")[0]
                    if nome.startswith("Microsoft Visual Studio Code"):
                        candidatos.append(Path(winreg.QueryValueEx(k, "InstallLocation")[0]) / "Code.exe")
                except OSError:
                    continue
    except ImportError:
        pass
    candidatos += [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
                   Path(os.environ.get("ProgramFiles", "")) / "Microsoft VS Code" / "Code.exe"]
    return next((str(c) for c in candidatos if c.is_file()), None)


def _claude_app_id() -> str | None:
    r = rodar("powershell", "-NoProfile", "-Command",
              "Get-StartApps | Where-Object { $_.AppID -like 'Claude_*!Claude' } | Select-Object -First 1 -ExpandProperty AppID",
              timeout=30)
    return r.stdout.strip() or None


def detectar_ferramentas() -> Ferramentas:
    f = Ferramentas(vscode=_vscode_exe(), claude_app_id=_claude_app_id())
    antigo = Path(os.environ.get("LOCALAPPDATA", "")) / "AnthropicClaude" / "claude.exe"
    if not f.claude_app_id and antigo.is_file():
        f.claude_exe = str(antigo)
    return f


def vscode_tem_extensao(f: Ferramentas) -> bool:
    if not f.vscode:
        return False
    cli = Path(f.vscode).parent / "bin" / "code.cmd"
    r = rodar(str(cli) if cli.is_file() else "code", "--list-extensions", timeout=60)
    return "anthropic.claude-code" in r.stdout.lower()


def instalar_extensao(f: Ferramentas) -> tuple[bool, str]:
    cli = Path(f.vscode).parent / "bin" / "code.cmd"
    r = rodar(str(cli) if cli.is_file() else "code", "--install-extension", "anthropic.claude-code", timeout=300)
    return r.returncode == 0, _erro(r)


# ---------------------------------------------------------------- projetos
def na_onedrive(pasta: str) -> bool:
    p = os.path.normcase(os.path.abspath(pasta))
    for var in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        base = os.environ.get(var)
        if base and p.startswith(os.path.normcase(os.path.abspath(base))):
            return True
    return False


def nome_pasta(cliente: str, projeto: str) -> str:
    limpo = lambda s: re.sub(r"[^\w\-]+", "-", s.strip()).strip("-")  # noqa: E731
    return f"{limpo(cliente)}-{limpo(projeto)}"


def _yaml_str(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def criar_projeto(cfg: Config, *, cliente: str, projeto: str, workspace: str, autor: str,
                  pasta: str, ferramenta: str, progresso=lambda msg: None) -> Projeto:
    """Clona esta instalação para a pasta do projeto, prepara o ambiente e grava o projeto.yaml."""
    destino = Path(pasta)
    if destino.exists() and any(destino.iterdir()):
        raise ValueError(f"A pasta já existe e não está vazia: {destino}")
    if any(os.path.normcase(p.pasta) == os.path.normcase(str(destino)) for p in cfg.projetos):
        raise ValueError("Já existe um projeto cadastrado nessa pasta.")

    progresso("Copiando o assistente para a pasta do projeto…")
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = rodar("git", "clone", "--quiet", str(RAIZ), str(destino))
    if r.returncode != 0:
        raise RuntimeError(f"Falha ao criar a pasta do projeto (git clone): {_erro(r)}")

    progresso("Instalando o ambiente (uv sync)…")
    r = rodar("uv", "sync", "--quiet", cwd=destino)
    if r.returncode != 0:
        raise RuntimeError(f"Falha no uv sync: {_erro(r)}")

    progresso("Gravando o projeto…")
    pid = uuid.uuid4().hex
    proj_dir = destino / "projeto"
    for sub in ("referencias", "inventario", "analise", "docs/revisado", "planos"):
        (proj_dir / sub).mkdir(parents=True, exist_ok=True)
    (proj_dir / ".id").write_text(pid, encoding="utf-8")
    (proj_dir / "projeto.yaml").write_text(
        "# Gerado pelo app Fabric Doc Helper; a entrevista (iniciar-projeto) completa o restante. Não versionar.\n"
        f"cliente: {_yaml_str(cliente)}\n"
        f"projeto: {_yaml_str(projeto)}\n"
        'fase: ""\n'
        f"autor: {_yaml_str(autor)}\n"
        'classificacao: "RESTRITO"\n'
        f"workspace_alvo: {_yaml_str(workspace)}\n"
        "workspaces_leitura_extra: []\n"
        'workspace_legado: ""\n'
        'conta_fabric: ""\n'
        'tenant_id: ""\n'
        "participantes: []\n"
        "escopo:\n  itens: []\n"
        "nomenclatura: []\n"
        "referencias: []\n"
        "decisoes: []\n",
        encoding="utf-8")

    p = Projeto(id=pid, cliente=cliente.strip(), projeto=projeto.strip(), pasta=str(destino),
                ferramenta=ferramenta, criado_em=agora())
    cfg.projetos.append(p)
    if autor:
        cfg.autor = autor
    salvar(cfg)
    return p


def adicionar_existente(cfg: Config, pasta: str, ferramenta: str) -> Projeto:
    """Cadastra no app uma pasta de projeto criada fora dele (clone manual)."""
    destino = Path(pasta)
    if not (destino / "AGENTS.md").is_file() or not (destino / "scripts" / "guarda.py").is_file():
        raise ValueError("Essa pasta não é um clone do fabric-ai-doc-helper.")
    if any(os.path.normcase(p.pasta) == os.path.normcase(str(destino)) for p in cfg.projetos):
        raise ValueError("Essa pasta já está cadastrada.")
    y = ler_yaml(destino)
    id_arq = destino / "projeto" / ".id"
    pid = id_arq.read_text(encoding="utf-8").strip() if id_arq.is_file() else uuid.uuid4().hex
    p = Projeto(id=pid, cliente=y.get("cliente") or destino.name, projeto=y.get("projeto") or "",
                pasta=str(destino), ferramenta=ferramenta, criado_em=agora())
    cfg.projetos.append(p)
    salvar(cfg)
    return p


def ler_yaml(pasta: Path | str) -> dict:
    arq = Path(pasta) / "projeto" / "projeto.yaml"
    if not arq.is_file():
        return {}
    try:
        import yaml
        return yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


@dataclass
class Estado:
    existe: bool
    etapa: str
    conta: str
    workspace: str
    documentos: list[Path]


def estado(p: Projeto) -> Estado:
    pasta = Path(p.pasta)
    if not pasta.is_dir():
        return Estado(False, "Pasta não encontrada", "", "", [])
    y = ler_yaml(pasta)
    proj = pasta / "projeto"
    docs = sorted((proj / "docs").glob("*.docx"), key=lambda d: d.stat().st_mtime, reverse=True)
    revisados = sorted((proj / "docs" / "revisado").glob("*.docx"), key=lambda d: d.stat().st_mtime, reverse=True)
    if not y or not y.get("workspace_alvo"):
        etapa = "Configuração pendente"
    elif not y.get("conta_fabric"):
        etapa = "Conta a confirmar na 1ª conversa"
    elif not any((proj / "inventario").glob("*.json")):
        etapa = "Inventário pendente"
    elif not (proj / "analise" / "notas.md").is_file():
        etapa = "Análise pendente"
    elif not docs and not revisados:
        etapa = "Documento pendente"
    elif revisados:
        etapa = f"Revisado ({revisados[0].name})"
    else:
        etapa = f"Documento gerado ({docs[0].name})"
    return Estado(True, etapa, y.get("conta_fabric") or "", y.get("workspace_alvo") or "", revisados + docs)


def atualizar_projeto(p: Projeto) -> str | None:
    """Traz para o projeto a versão atual do assistente (desta instalação). Retorna aviso, se houver."""
    r = rodar("git", "pull", "--ff-only", "--quiet", cwd=p.pasta, timeout=120)
    aviso = None if r.returncode == 0 else "Não foi possível atualizar o assistente nesta pasta (alterações locais?)."
    r = rodar("uv", "sync", "--quiet", cwd=p.pasta)
    if r.returncode != 0:
        aviso = f"Falha no uv sync: {_erro(r)}"
    return aviso


def abrir(p: Projeto, f: Ferramentas) -> str:
    """Abre o projeto na ferramenta escolhida. Retorna a mensagem para o usuário."""
    if p.ferramenta == "vscode":
        if not f.vscode:
            raise RuntimeError("VS Code não encontrado neste computador.")
        subprocess.Popen([f.vscode, p.pasta], creationflags=SEM_JANELA)
        return "Abrindo no VS Code. Abra o painel do Claude Code e diga: \"vamos começar\"."
    if not f.tem_claude:
        raise RuntimeError("Claude Desktop não encontrado neste computador.")
    subprocess.run("clip", input=p.pasta.encode("utf-16-le"), creationflags=SEM_JANELA)
    if f.claude_app_id:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{f.claude_app_id}"])
    else:
        subprocess.Popen([f.claude_exe])
    return ("Abrindo o Claude Desktop. O caminho da pasta foi copiado: na aba Code, clique em "
            "\"Select folder\", cole (Ctrl+V) e diga \"vamos começar\".")


def atualizar_app() -> tuple[bool, str]:
    r = rodar("git", "-c", "http.sslBackend=schannel", "pull", "--ff-only", cwd=RAIZ, timeout=300)
    if r.returncode != 0:
        return False, _erro(r)
    r2 = rodar("uv", "sync", "--quiet", cwd=RAIZ)
    if r2.returncode != 0:
        return False, _erro(r2)
    return True, (r.stdout or "").strip() or "Atualizado."
