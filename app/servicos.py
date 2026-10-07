"""Serviços do app Fabric Doc Helper: projetos, harness, detecção das ferramentas, abertura e versões.

O app NÃO gerencia contas: a conta do Fabric é conferida pelo assistente em cada conversa
(hook de início + scripts/verificar_login.py) e fica registrada em projeto/projeto.yaml.

Três coisas separadas:
- Código-fonte: o repositório Git fabric-ai-doc-helper (branches, PRs, tags). Só para desenvolvimento.
- App instalado: uma versão publicada (tag vX.Y.Z) baixada como .zip do GitHub e extraída em
  ~/FabricDocHelper/app/versoes/<versão>/. Não é repositório Git. Ao lado: Projetos/ (pasta padrão
  dos projetos) e dados/ (lista de projetos e log). Instalações anteriores ficavam em AppData; ao
  abrir, o app se muda sozinho (migrar_local_antigo, mudar_de_local, remover_instalacao_antiga).
- Pasta de projeto: pasta comum com o "harness" (instruções, skills, guarda, scripts, template e
  configuração do Python) copiado da versão instalada, mais projeto/ com os dados do cliente e o
  marcador .fabric-doc-helper.json (versão do harness + impressão digital de cada arquivo copiado).
  Não é repositório Git e não vai para o GitHub.

Modo desenvolvimento: app rodado do código-fonte (qualquer pasta fora de versoes/). Usa outra pasta
(~/FabricDocHelper-dev, com Projetos/ e dados/), e os projetos recebem o harness direto da
árvore de trabalho (inclusive o que ainda não foi commitado). FDH_PERFIL=dev|producao força o modo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

REPO = "leonardo-trindade/fabric-ai-doc-helper"
VERSAO_MINIMA = (1, 0, 0)  # numeração recomeçou em v1.0.0 (as tags antigas foram apagadas)
RAIZ = Path(__file__).resolve().parents[1]  # versão em uso (origem do harness dos projetos)
LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home()))
# Tudo do app numa pasta do usuário: app\ (versões instaladas), Projetos\ e dados\ (lista de projetos, log).
CASA = Path.home() / "FabricDocHelper"
BASE_INSTALACAO = CASA / "app"
VERSOES = BASE_INSTALACAO / "versoes"
# Locais de instalações anteriores: app em AppData\Local\Programs, lista em AppData\Local, projetos em C:\Fabric.
ANTIGA = LOCAL / "Programs" / "fabric-ai-doc-helper"
DADOS_ANTIGOS = LOCAL / "fabric-ai-doc-helper"
PADROES_ANTIGOS = {r"C:\Fabric", r"C:\Fabric-teste"}


def _mesmo(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


_perfil = os.environ.get("FDH_PERFIL", "").lower()
LEGADO = _mesmo(RAIZ, ANTIGA)  # instalação antiga baseada em Git: o instalador novo substitui
NO_LOCAL_ANTIGO = _mesmo(RAIZ.parent, ANTIGA / "versoes")  # instalação anterior atualizada pelo app: o app se muda
MODO_DEV = _perfil == "dev" or (_perfil != "producao" and not LEGADO and not NO_LOCAL_ANTIGO
                                and not _mesmo(RAIZ.parent, VERSOES))
if MODO_DEV:  # desenvolvimento: lista e projetos separados do uso real
    CASA = Path.home() / "FabricDocHelper-dev"
    DADOS_ANTIGOS = DADOS_ANTIGOS / "dev"
DADOS = CASA / "dados"
ARQUIVO = DADOS / "app.json"
PASTA_PADRAO = str(CASA / "Projetos")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

FERRAMENTAS = {"vscode": "VS Code", "claude": "Claude Desktop"}

# Harness: o que vai para cada pasta de projeto (na raiz, onde as ferramentas de IA procuram).
HARNESS_ARQUIVOS = ["AGENTS.md", "CLAUDE.md", ".mcp.json", "pyproject.toml", "uv.lock", ".python-version"]
HARNESS_PASTAS = [".agents", ".claude", "scripts", "templates"]
HARNESS_FORA = {".agents/MANUTENCAO", ".claude/settings.local.json"}  # nunca copiados
DEPENDENCIAS = {"pyproject.toml", "uv.lock", ".python-version"}
MARCADOR = ".fabric-doc-helper.json"


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
    revisado_em: str = ""  # marcado pelo usuário como revisado (pronto); vazio = em andamento


@dataclass
class Config:
    autor: str = ""
    pasta_padrao: str = PASTA_PADRAO
    projetos: list[Projeto] = field(default_factory=list)


def carregar() -> Config:
    try:
        d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return Config()
    padrao = d.get("pasta_padrao") or PASTA_PADRAO
    if padrao in PADROES_ANTIGOS:  # padrão de versões antigas: passa para Projetos\ (projetos existentes ficam onde estão)
        padrao = PASTA_PADRAO
    return Config(autor=d.get("autor", ""), pasta_padrao=padrao,
                  projetos=[Projeto(**p) for p in d.get("projetos", [])])


def migrar_local_antigo() -> str | None:
    """Uma vez, ao abrir: traz a lista de projetos do local antigo (AppData) para dados\\.

    Os projetos não são movidos (cada um continua na pasta em que foi criado). Retorna aviso, se houver.
    """
    antigo = DADOS_ANTIGOS / "app.json"
    if ARQUIVO.exists() or not antigo.is_file():
        return None
    DADOS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(antigo, ARQUIVO)
    antigo.rename(antigo.with_name("app.json.migrado"))  # fica de cópia de segurança
    salvar(carregar())  # grava já com a pasta padrão nova
    return f"Lista de projetos trazida para {DADOS}. Projetos novos vão para {PASTA_PADRAO}."


def mudar_de_local() -> tuple[bool, str]:
    """App de instalação anterior, atualizado pelo próprio app, continua em AppData: instala esta versão no local novo."""
    if not NO_LOCAL_ANTIGO:
        return True, ""
    return instalar_versao(RAIZ.name)


def remover_instalacao_antiga() -> None:
    """Apaga o app do local antigo (AppData\\Local\\Programs), se este app não estiver rodando de lá."""
    if ANTIGA.exists() and not LEGADO and not NO_LOCAL_ANTIGO and not MODO_DEV:
        try:
            _apagar(ANTIGA)
        except OSError:
            pass  # algum arquivo em uso; tenta de novo na próxima abertura


def salvar(cfg: Config) -> None:
    DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")


def agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- comandos
def rodar(*args: str, cwd: Path | str | None = None, timeout: int = 600,
          env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, creationflags=SEM_JANELA,
                          env={**os.environ, **env} if env else None)


def _erro(r: subprocess.CompletedProcess) -> str:
    return ((r.stderr or "") + (r.stdout or "")).strip()[-600:]


def _apagar(p: Path) -> None:
    def tirar_somente_leitura(func, caminho, _):
        os.chmod(caminho, 0o666)
        func(caminho)
    shutil.rmtree(p, onerror=tirar_somente_leitura)


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
    candidatos += [LOCAL / "Programs" / "Microsoft VS Code" / "Code.exe",
                   Path(os.environ.get("ProgramFiles", "")) / "Microsoft VS Code" / "Code.exe"]
    return next((str(c) for c in candidatos if c.is_file()), None)


def _claude_app_id() -> str | None:
    r = rodar("powershell", "-NoProfile", "-Command",
              "Get-StartApps | Where-Object { $_.AppID -like 'Claude_*!Claude' } | Select-Object -First 1 -ExpandProperty AppID",
              timeout=30)
    return r.stdout.strip() or None


def detectar_ferramentas() -> Ferramentas:
    f = Ferramentas(vscode=_vscode_exe(), claude_app_id=_claude_app_id())
    antigo = LOCAL / "AnthropicClaude" / "claude.exe"
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


# ---------------------------------------------------------------- harness
def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def arquivos_harness(origem: Path | None = None) -> dict[str, Path]:
    """Arquivos do harness na origem (padrão: a versão em uso), por caminho relativo (com '/')."""
    origem = origem or RAIZ
    out: dict[str, Path] = {}
    for nome in HARNESS_ARQUIVOS:
        if (origem / nome).is_file():
            out[nome] = origem / nome
    for pasta in HARNESS_PASTAS:
        for p in sorted((origem / pasta).rglob("*")):
            rel = p.relative_to(origem).as_posix()
            if p.is_file() and rel not in HARNESS_FORA and "__pycache__" not in p.parts and p.suffix != ".pyc":
                out[rel] = p
    return out


def ler_marcador(pasta: Path | str) -> dict:
    try:
        return json.loads((Path(pasta) / MARCADOR).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _gravar_marcador(pasta: Path, dados: dict) -> None:
    (pasta / MARCADOR).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def aplicar_harness(destino: Path, origem: Path | None = None) -> tuple[bool, str | None]:
    """Deixa o harness da pasta igual ao da origem. Retorna (dependências mudaram?, aviso).

    Só toca nos arquivos do harness: projeto/, .venv e qualquer outro arquivo ficam como estão.
    Se algum arquivo do harness foi editado na pasta (impressão digital diferente da registrada),
    nada é alterado e um aviso é retornado.
    """
    marc = ler_marcador(destino)
    antigos: dict[str, str] = marc.get("arquivos", {})
    alterados = [rel for rel, h in antigos.items() if (destino / rel).is_file() and _hash(destino / rel) != h]
    if alterados:
        lista = ", ".join(alterados[:3]) + ("…" if len(alterados) > 3 else "")
        return False, f"O assistente desta pasta foi editado localmente ({lista}); ele não foi atualizado."

    origem = origem or RAIZ
    novos = {rel: (p, _hash(p)) for rel, p in arquivos_harness(origem).items()}
    if not novos:
        return False, f"Harness não encontrado em {origem}."
    hashes = {rel: h for rel, (_, h) in novos.items()}
    versao = versao_atual()
    if hashes == antigos and marc.get("versao") == versao:
        return False, None
    deps = any(antigos.get(rel) != hashes.get(rel) for rel in DEPENDENCIAS)
    if hashes != antigos:
        for rel in set(antigos) - set(novos):  # arquivos que saíram do harness nesta versão
            (destino / rel).unlink(missing_ok=True)
        for rel, (p, _) in novos.items():
            alvo = destino / rel
            alvo.parent.mkdir(parents=True, exist_ok=True)
            if alvo.exists():
                os.chmod(alvo, 0o666)
            shutil.copyfile(p, alvo)
    _gravar_marcador(destino, {**marc, "versao": versao, "atualizado_em": agora(), "arquivos": hashes})
    return deps, None


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


LEIA_ME = """# {cliente} · {projeto}

Pasta de projeto criada pelo **Fabric Doc Helper** em {data}.

- Abra esta pasta no VS Code (painel do Claude Code) ou na aba Code do Claude Desktop e diga
  "vamos começar". O app Fabric Doc Helper faz isso pelo botão **Abrir**.
- Os dados do cliente ficam em `projeto/` (referências, inventário, análise e documentos).
- Os demais arquivos (AGENTS.md, CLAUDE.md, .agents/, .claude/, scripts/, templates/) são o
  assistente. Não edite: o app os atualiza ao abrir o projeto.
- Esta pasta não é um repositório Git e não deve ir para o GitHub.
"""


def criar_projeto(cfg: Config, *, cliente: str, projeto: str, autor: str,
                  pasta: str, ferramenta: str, progresso=lambda msg: None) -> Projeto:
    """Cria a pasta do projeto com o harness da versão em uso, o ambiente Python e o projeto.yaml."""
    destino = Path(pasta)
    if destino.exists() and any(destino.iterdir()):
        raise ValueError(f"A pasta já existe e não está vazia: {destino}")
    if any(_mesmo(Path(p.pasta), destino) for p in cfg.projetos):
        raise ValueError("Já existe um projeto cadastrado nessa pasta.")

    progresso("Copiando o assistente para a pasta do projeto…")
    destino.mkdir(parents=True, exist_ok=True)
    pid = uuid.uuid4().hex
    _gravar_marcador(destino, {"id": pid, "criado_em": agora()})
    _, aviso = aplicar_harness(destino)
    if aviso:
        raise RuntimeError(aviso)
    (destino / "LEIA-ME.md").write_text(
        LEIA_ME.format(cliente=cliente.strip(), projeto=projeto.strip(), data=agora()), encoding="utf-8")

    progresso("Instalando o ambiente (uv sync)…")
    r = rodar("uv", "sync", "--quiet", cwd=destino)
    if r.returncode != 0:
        raise RuntimeError(f"Falha no uv sync: {_erro(r)}")

    progresso("Gravando o projeto…")
    proj_dir = destino / "projeto"
    for sub in ("referencias", "inventario", "analise", "docs/revisado", "planos"):
        (proj_dir / sub).mkdir(parents=True, exist_ok=True)
    (proj_dir / "projeto.yaml").write_text(
        "# Gerado pelo app Fabric Doc Helper; a entrevista (iniciar-projeto) completa o restante.\n"
        f"cliente: {_yaml_str(cliente)}\n"
        f"projeto: {_yaml_str(projeto)}\n"
        'fase: ""\n'
        f"autor: {_yaml_str(autor)}\n"
        'classificacao: "RESTRITO"\n'
        'workspace_alvo: ""          # escolhido na 1ª conversa (scripts/escolher_workspace.py)\n'
        'workspace_id: ""\n'
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
    """Cadastra no app uma pasta de projeto que não está na lista (outro computador, versão antiga…)."""
    destino = Path(pasta)
    marc = ler_marcador(destino)
    if not marc and not ((destino / "AGENTS.md").is_file() and (destino / "scripts" / "guarda.py").is_file()):
        raise ValueError("Essa pasta não é um projeto do Fabric Doc Helper.")
    if any(_mesmo(Path(p.pasta), destino) for p in cfg.projetos):
        raise ValueError("Essa pasta já está cadastrada.")
    y = ler_yaml(destino)
    id_antigo = destino / "projeto" / ".id"  # projetos da época do Git
    pid = marc.get("id") or (id_antigo.read_text(encoding="utf-8").strip() if id_antigo.is_file() else uuid.uuid4().hex)
    if not marc:
        _gravar_marcador(destino, {"id": pid, "criado_em": agora()})
    p = Projeto(id=pid, cliente=y.get("cliente") or destino.name, projeto=y.get("projeto") or "",
                pasta=str(destino), ferramenta=ferramenta, criado_em=agora())
    cfg.projetos.append(p)
    salvar(cfg)
    return p


def marcar_revisado(cfg: Config, pid: str, revisado: bool) -> None:
    """O usuário considera o projeto pronto (ou o reabre). Só muda a lista do app, não a pasta."""
    for q in cfg.projetos:
        if q.id == pid:
            q.revisado_em = agora() if revisado else ""
    salvar(cfg)


def excluir_projeto(cfg: Config, p: Projeto) -> None:
    """Apaga a pasta do projeto (assistente + dados do cliente) e tira o projeto da lista.

    Só apaga pasta que é de projeto do app (marcador ou harness) e nunca o código-fonte ou a instalação.
    """
    pasta = Path(p.pasta)
    if pasta.exists():
        e_projeto = bool(ler_marcador(pasta)) or (
            (pasta / "AGENTS.md").is_file() and (pasta / "scripts" / "guarda.py").is_file())
        protegidas = (RAIZ, CASA, BASE_INSTALACAO, VERSOES, DADOS, Path(PASTA_PADRAO), Path(cfg.pasta_padrao),
                      Path.home(), Path(pasta.anchor))
        if not e_projeto or (pasta / ".git").exists() or any(
                _mesmo(pasta, x) or _dentro(x, pasta) for x in protegidas):
            raise ValueError(f"Por segurança, essa pasta não é apagada pelo app: {pasta}. Apague-a manualmente.")
        try:
            _apagar(pasta)
        except OSError as ex:
            raise RuntimeError("Não foi possível apagar tudo: algum arquivo está aberto. Feche o VS Code, o Claude "
                               f"e o Word com arquivos do projeto e tente de novo. ({ex})") from ex
    cfg.projetos = [q for q in cfg.projetos if q.id != p.id]
    salvar(cfg)


def _dentro(filho: Path, pai: Path) -> bool:
    """`filho` fica dentro de `pai` (apagar `pai` apagaria `filho`)."""
    try:
        return Path(filho).resolve().is_relative_to(Path(pai).resolve())
    except OSError:
        return False


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
class DocVersao:
    arquivo: Path
    versao: str          # "0.3" (do nome DT_..._v0.3.docx) ou "" se o nome não tiver versão
    revisado: bool       # salvo pelo usuário em projeto/docs/revisado/
    modificado: datetime

    @property
    def rotulo(self) -> str:
        v = f"v{self.versao}" if self.versao else self.arquivo.stem
        return v + (" · revisado" if self.revisado else "")

    @property
    def _ordem(self) -> tuple:
        num = tuple(int(x) for x in self.versao.split(".")) if self.versao else ()
        return (num, self.revisado, self.modificado)


def documentos(pasta: Path | str) -> list[DocVersao]:
    """Versões do documento (geradas e revisadas), da mais nova para a mais antiga.

    Mais nova = maior número de versão no nome (_vX.Y); no empate, a revisada pelo usuário (fonte da
    verdade) e depois a modificada por último. Ignora arquivos temporários do Word (~$...).
    """
    base = Path(pasta) / "projeto" / "docs"
    out = []
    for revisado, pasta_docs in ((False, base), (True, base / "revisado")):
        for arq in pasta_docs.glob("*.docx"):
            if arq.name.startswith("~$"):
                continue
            m = re.search(r"_v(\d+(?:\.\d+)*)", arq.stem)
            out.append(DocVersao(arq, m.group(1) if m else "", revisado,
                                 datetime.fromtimestamp(arq.stat().st_mtime)))
    return sorted(out, key=lambda d: d._ordem, reverse=True)


@dataclass
class Estado:
    existe: bool
    conta: str
    workspace: str
    documentos: list[DocVersao]
    referencias: list[Referencia] = field(default_factory=list)
    versao_harness: str = ""


def estado(p: Projeto) -> Estado:
    pasta = Path(p.pasta)
    if not pasta.is_dir():
        return Estado(False, "", "", [])
    y = ler_yaml(pasta)
    return Estado(True, y.get("conta_fabric") or "", y.get("workspace_alvo") or "", documentos(pasta),
                  referencias(pasta), ler_marcador(pasta).get("versao", ""))


# ---------------------------------------------------------------- referências do projeto
# Arquivos opcionais do usuário em projeto/referencias/, registrados em projeto.yaml → referencias
# com o tipo que as skills usam (levantamento | mapeamento | outro). O assistente só lê esses arquivos.
CATEGORIAS = {"levantamento": "Levantamento de requisitos", "mapeamento": "Mapeamento", "outro": "Outros"}


@dataclass
class Referencia:
    arquivo: Path
    tipo: str            # chave de CATEGORIAS, ou "" se o arquivo está na pasta sem registro

    @property
    def categoria(self) -> str:
        return CATEGORIAS.get(self.tipo, "Sem categoria")


def pasta_referencias(pasta: Path | str) -> Path:
    return Path(pasta) / "projeto" / "referencias"


def _entradas_refs(pasta: Path | str) -> list[dict]:
    return [x for x in (ler_yaml(pasta).get("referencias") or []) if isinstance(x, dict) and x.get("arquivo")]


def referencias(pasta: Path | str) -> list[Referencia]:
    """Arquivos de projeto/referencias/ (sem a pasta gerada _texto/), com a categoria registrada."""
    refs = pasta_referencias(pasta)
    tipos = {Path(x["arquivo"]).name.lower(): x.get("tipo") or "" for x in _entradas_refs(pasta)}
    if not refs.is_dir():
        return []
    arquivos = [a for a in refs.iterdir() if a.is_file() and not a.name.startswith(("~$", "."))]
    return [Referencia(a, tipos.get(a.name.lower(), "")) for a in sorted(arquivos, key=lambda a: a.name.lower())]


def _gravar_entradas_refs(pasta: Path | str, entradas: list[dict]) -> None:
    """Reescreve só o bloco `referencias:` do projeto.yaml (o resto do arquivo e os comentários ficam)."""
    arq = Path(pasta) / "projeto" / "projeto.yaml"
    txt = arq.read_text(encoding="utf-8") if arq.is_file() else ""
    if entradas:
        bloco = "referencias:\n" + "".join(
            "  - {" + ", ".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in x.items()) + "}\n"
            for x in entradas)
    else:
        bloco = "referencias: []\n"
    padrao = re.compile(r"(?ms)^referencias:.*?(?=^\S|\Z)")
    txt = padrao.sub(lambda _: bloco, txt, count=1) if padrao.search(txt) else txt.rstrip("\n") + "\n" + bloco
    arq.write_text(txt, encoding="utf-8")


def _registrar_ref(pasta: Path | str, nome: str, tipo: str) -> None:
    entradas = _entradas_refs(pasta)
    for x in entradas:
        if Path(x["arquivo"]).name.lower() == nome.lower():
            x["tipo"] = tipo
            break
    else:
        entradas.append({"arquivo": f"referencias/{nome}", "tipo": tipo})
    _gravar_entradas_refs(pasta, entradas)


def anexar_referencia(pasta: Path | str, nome: str, conteudo: bytes | Path, tipo: str) -> Referencia:
    """Copia um arquivo para projeto/referencias/ (nunca sobrescreve: nome repetido ganha " (2)")
    e registra a categoria no projeto.yaml."""
    if tipo not in CATEGORIAS:
        raise ValueError(f"Categoria inválida: {tipo}")
    refs = pasta_referencias(pasta)
    refs.mkdir(parents=True, exist_ok=True)
    base = Path(Path(nome).name)  # só o nome, sem pastas
    if not base.stem or base.name.startswith(("~$", ".")):
        raise ValueError(f"Nome de arquivo inválido: {nome}")
    destino, n = refs / base.name, 2
    while destino.exists():
        destino, n = refs / f"{base.stem} ({n}){base.suffix}", n + 1
    if isinstance(conteudo, Path):
        shutil.copy2(conteudo, destino)
    else:
        destino.write_bytes(conteudo)
    _registrar_ref(pasta, destino.name, tipo)
    return Referencia(destino, tipo)


def definir_categoria(pasta: Path | str, ref: Referencia, tipo: str) -> None:
    if tipo not in CATEGORIAS:
        raise ValueError(f"Categoria inválida: {tipo}")
    _registrar_ref(pasta, ref.arquivo.name, tipo)


def remover_referencia(pasta: Path | str, ref: Referencia) -> None:
    """Apaga a cópia em projeto/referencias/ (o original do usuário não é tocado), o texto gerado e o registro."""
    texto = pasta_referencias(pasta) / "_texto" / f"{ref.arquivo.name}.md"
    for a in (ref.arquivo, texto):
        if a.is_file():
            a.unlink()
    _gravar_entradas_refs(pasta, [x for x in _entradas_refs(pasta)
                                  if Path(x["arquivo"]).name.lower() != ref.arquivo.name.lower()])


def abrir_documento(doc: DocVersao) -> None:
    """Abre a versão no programa padrão do Windows para .docx (o Word)."""
    if not doc.arquivo.is_file():
        raise FileNotFoundError(f"O arquivo não existe mais: {doc.arquivo}")
    os.startfile(doc.arquivo)  # noqa: S606  (só arquivos .docx do próprio projeto)


def atualizar_projeto(p: Projeto) -> str | None:
    """Deixa o harness do projeto igual ao da versão em uso (também ao voltar de versão).
    Retorna aviso, se houver. A pasta projeto/ nunca é tocada."""
    pasta = Path(p.pasta)
    deps, aviso = aplicar_harness(pasta)
    if aviso:
        return aviso
    if deps or not (pasta / ".venv").is_dir():
        r = rodar("uv", "sync", "--quiet", cwd=pasta)
        if r.returncode != 0:
            return f"Falha no uv sync: {_erro(r)}"
    return None


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


# ---------------------------------------------------------------- versões
SEMVER = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _semver(tag: str) -> tuple[int, int, int] | None:
    m = SEMVER.match(tag)
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def versao_atual() -> str:
    """Produção: nome da pasta da versão (vX.Y.Z). Desenvolvimento: git describe, ou 'dev'."""
    if MODO_DEV:
        if (RAIZ / ".git").exists():
            r = rodar("git", "describe", "--tags", "--always", "--dirty", cwd=RAIZ, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return "dev-" + r.stdout.strip()
        return "dev"
    if LEGADO:
        return "antiga (Git)"
    return RAIZ.name


def _baixar(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "fabric-doc-helper",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # certificados do Windows (ssl padrão)
        return r.read()


def versoes_publicadas() -> list[str]:
    """Versões (tags vX.Y.Z ≥ v1.0.0) publicadas no GitHub, da mais nova para a mais antiga."""
    dados = json.loads(_baixar(f"https://api.github.com/repos/{REPO}/tags?per_page=100"))
    tags = [t["name"] for t in dados if (_semver(t["name"]) or (0, 0, 0)) >= VERSAO_MINIMA]
    return sorted(tags, key=_semver, reverse=True)


def versoes_instaladas() -> list[str]:
    if not VERSOES.is_dir():
        return []
    tags = [p.name for p in VERSOES.iterdir() if _semver(p.name) and (p / "app" / "main.py").is_file()]
    return sorted(tags, key=_semver, reverse=True)


def atualizacao_disponivel() -> str | None:
    """Versão publicada mais nova que a em uso (só em produção)."""
    if MODO_DEV or LEGADO:
        return None
    try:
        tags = versoes_publicadas()
    except Exception:  # noqa: BLE001  (sem internet, limite da API…)
        return None
    atual = _semver(versao_atual()) or (0, 0, 0)
    return tags[0] if tags and _semver(tags[0]) > atual else None


def novidades(tag: str) -> str:
    """Trecho do CHANGELOG.md da versão `tag` (lido da própria tag no GitHub)."""
    try:
        txt = _baixar(f"https://raw.githubusercontent.com/{REPO}/{tag}/CHANGELOG.md").decode("utf-8")
    except Exception:  # noqa: BLE001
        return f"{tag}: não foi possível ler as novidades agora."
    m = re.search(rf"(?ms)^## {re.escape(tag)}\b.*?(?=^## |\Z)", txt)
    return m.group(0).strip() if m else f"{tag}: sem notas no CHANGELOG.md."


def _extrair_versao(tag: str) -> Path:
    """Baixa o .zip da tag e extrai em versoes/<tag> (sem .git)."""
    destino = VERSOES / tag
    VERSOES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=VERSOES, prefix=".baixando-") as tmp:
        arq = Path(tmp) / "versao.zip"
        arq.write_bytes(_baixar(f"https://github.com/{REPO}/archive/refs/tags/{tag}.zip", timeout=300))
        with zipfile.ZipFile(arq) as z:
            z.extractall(tmp)
        raiz_zip = next(p for p in Path(tmp).iterdir() if p.is_dir())  # fabric-ai-doc-helper-X.Y.Z/
        if destino.exists():
            _apagar(destino)
        shutil.move(str(raiz_zip), str(destino))
    return destino


def criar_atalhos(raiz: Path, nome: str = "Fabric Doc Helper") -> tuple[bool, str]:
    """Atalhos no Menu Iniciar e na Área de Trabalho apontando para a versão em `raiz`."""
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        "foreach ($p in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) { "
        "$a = $s.CreateShortcut((Join-Path $p ($env:FDH_NOME + '.lnk'))); "
        "$a.TargetPath = $env:FDH_ALVO; $a.Arguments = '\"' + $env:FDH_MAIN + '\"'; "
        "$a.WorkingDirectory = $env:FDH_RAIZ; $a.IconLocation = \"$env:SystemRoot\\System32\\imageres.dll,111\"; "
        "$a.Description = 'Projetos de documentacao Microsoft Fabric'; $a.Save() }")
    r = rodar("powershell", "-NoProfile", "-Command", script, timeout=60, env={
        "FDH_NOME": nome, "FDH_RAIZ": str(raiz), "FDH_MAIN": str(raiz / "app" / "main.py"),
        "FDH_ALVO": str(raiz / ".venv" / "Scripts" / "pythonw.exe")})
    return r.returncode == 0, _erro(r)


def _limpar_versoes(manter: set[str], quantas: int = 3, publicadas: list[str] | None = None) -> None:
    """Mantém as `quantas` versões mais novas instaladas (e as de `manter`); apaga as demais e as que
    não estão mais publicadas no GitHub (`publicadas`; ex.: numeração antiga, de antes da v1.0.0)."""
    instaladas = versoes_instaladas()
    sobras = instaladas[quantas:] if publicadas is None else (
        [t for t in instaladas if t not in publicadas] + [t for t in instaladas if t in publicadas][quantas:])
    for tag in sobras:
        if tag not in manter:
            try:
                _apagar(VERSOES / tag)
            except OSError:
                pass  # em uso; fica para a próxima


def instalar_versao(tag: str | None = None) -> tuple[bool, str]:
    """Produção: instala a versão `tag` (padrão: a mais nova) e aponta os atalhos para ela.
    Serve para atualizar e para voltar atrás (versões já baixadas são reaproveitadas)."""
    if MODO_DEV:
        return False, "Modo desenvolvimento: este app roda do código-fonte; atualize com git."
    try:
        tags = versoes_publicadas()
    except Exception as e:  # noqa: BLE001
        return False, f"Não foi possível consultar as versões no GitHub: {e}"
    if not tags:
        return False, "Ainda não há versão publicada."
    alvo = tag or tags[0]
    if alvo not in tags:
        return False, f"Versão {alvo} não encontrada."
    try:
        destino = VERSOES / alvo
        if not (destino / "app" / "main.py").is_file():
            destino = _extrair_versao(alvo)
    except Exception as e:  # noqa: BLE001
        return False, f"Falha ao baixar a versão {alvo}: {e}"
    r = rodar("uv", "sync", "--quiet", cwd=destino)
    if r.returncode != 0:
        return False, f"Falha no uv sync: {_erro(r)}"
    ok, msg = criar_atalhos(destino)
    if not ok:
        return False, f"Versão {alvo} instalada, mas os atalhos não foram atualizados: {msg}"
    (BASE_INSTALACAO / "atual.txt").write_text(alvo, encoding="utf-8")
    _limpar_versoes(manter={alvo, versao_atual()}, publicadas=tags)
    return True, (f"Versão {alvo} instalada. Feche e abra o app pelo atalho; cada projeto recebe a "
                  "versão nova ao ser aberto.")
