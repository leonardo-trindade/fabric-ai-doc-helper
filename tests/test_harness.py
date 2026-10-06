"""App: pasta de projeto sem Git, harness, versões e hook de início (sem rede e sem atalhos reais).

Os testes marcados `lento` rodam `uv sync` numa pasta temporária (usa o cache do uv).
"""
from __future__ import annotations

import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

import servicos as s
from conftest import RAIZ


@pytest.fixture
def app_dev(tmp_path, monkeypatch):
    """App em modo desenvolvimento (origem = este código-fonte), com dados numa pasta temporária."""
    monkeypatch.setattr(s, "MODO_DEV", True)
    monkeypatch.setattr(s, "LEGADO", False)
    monkeypatch.setattr(s, "RAIZ", RAIZ)
    monkeypatch.setattr(s, "DADOS", tmp_path / "dados")
    monkeypatch.setattr(s, "ARQUIVO", tmp_path / "dados" / "app.json")
    monkeypatch.setattr(s, "rodar", _rodar_sem_uv_sync(s.rodar))
    return tmp_path


def _rodar_sem_uv_sync(original):
    """`uv sync` vira no-op nos testes rápidos (cria só a pasta .venv)."""
    def rodar(*args, cwd=None, **kw):
        if args[:2] == ("uv", "sync"):
            Path(cwd, ".venv").mkdir(exist_ok=True)
            return subprocess.CompletedProcess(args, 0, "", "")
        return original(*args, cwd=cwd, **kw)
    return rodar


def criar(pasta: Path, projeto="Dev") -> s.Projeto:
    return s.criar_projeto(s.carregar(), cliente="Cli", projeto=projeto, autor="A",
                           pasta=str(pasta), ferramenta="vscode")


def test_projeto_sem_git_e_so_com_o_harness(app_dev):
    p = criar(app_dev / "proj")
    d = Path(p.pasta)
    assert not (d / ".git").exists()
    for fora in ("app", "instalar.ps1", "README.md", "tests", "dev", ".github", "CHANGELOG.md"):
        assert not (d / fora).exists(), fora
    assert not (d / ".agents" / "MANUTENCAO").exists()
    for dentro in ("AGENTS.md", "CLAUDE.md", ".claude/settings.json", ".agents/skills", "scripts/guarda.py",
                   "scripts/escolher_workspace.py", "scripts/verificar_documento.py",
                   ".claude/agents/revisor-documento.md", "templates", "LEIA-ME.md", "projeto/projeto.yaml"):
        assert (d / dentro).exists(), dentro
    marcador = s.ler_marcador(d)
    assert marcador["id"] == p.id and marcador["versao"].startswith("dev") and len(marcador["arquivos"]) > 20
    yaml = s.ler_yaml(d)
    assert yaml["cliente"] == "Cli" and yaml["workspace_alvo"] == "" and yaml["conta_fabric"] == ""
    e = s.estado(p)
    assert e.existe and e.conta == "" and e.workspace == "" and e.documentos == [] and e.referencias == []


def test_reabrir_e_alteracao_local(app_dev):
    p = criar(app_dev / "proj")
    d = Path(p.pasta)
    assert s.atualizar_projeto(p) is None
    (d / "AGENTS.md").write_text("editado", encoding="utf-8")
    aviso = s.atualizar_projeto(p)
    assert "editado localmente" in aviso
    assert (d / "AGENTS.md").read_text(encoding="utf-8") == "editado"


def test_pasta_repetida_e_nao_vazia(app_dev):
    p = criar(app_dev / "proj")
    with pytest.raises(ValueError):
        criar(Path(p.pasta), projeto="Outro")
    (app_dev / "cheia").mkdir()
    (app_dev / "cheia" / "x.txt").write_text("x")
    with pytest.raises(ValueError):
        criar(app_dev / "cheia")


def _zip_da_versao(tag: str, alterar: bool) -> bytes:
    arquivo = subprocess.run(["git", "archive", "--format=zip", f"--prefix=fabric-ai-doc-helper-{tag[1:]}/", "HEAD"],
                             cwd=RAIZ, capture_output=True, check=True).stdout
    saida = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(arquivo)) as zin, zipfile.ZipFile(saida, "w") as zout:
        for item in zin.infolist():
            dados = zin.read(item.filename)
            if alterar and item.filename.endswith("/AGENTS.md"):
                dados += f"\n<!-- {tag} -->\n".encode()
            zout.writestr(item, dados)
        if alterar:
            zout.writestr(f"fabric-ai-doc-helper-{tag[1:]}/scripts/novo_{tag[1:].replace('.', '_')}.py", b"# novo\n")
    return saida.getvalue()


@pytest.fixture
def app_producao(app_dev, monkeypatch):
    """Produção simulada: versões v2.0.0 e v2.1.0 servidas de zips locais; sem atalhos reais."""
    zips = {"v2.0.0": _zip_da_versao("v2.0.0", False), "v2.1.0": _zip_da_versao("v2.1.0", True)}
    baixados = []

    def baixar(url, timeout=60):
        tag = url.rsplit("/", 1)[-1].removesuffix(".zip")
        baixados.append(tag)
        return zips[tag]

    base = app_dev / "Programs" / "fabric-ai-doc-helper"
    monkeypatch.setattr(s, "_baixar", baixar)
    monkeypatch.setattr(s, "versoes_publicadas", lambda: ["v2.1.0", "v2.0.0"])
    monkeypatch.setattr(s, "criar_atalhos", lambda raiz, nome="Fabric Doc Helper": (True, ""))
    monkeypatch.setattr(s, "BASE_INSTALACAO", base)
    monkeypatch.setattr(s, "VERSOES", base / "versoes")
    monkeypatch.setattr(s, "MODO_DEV", False)
    return baixados


def test_versoes_atualizar_e_voltar(app_dev, app_producao):
    ok, _ = s.instalar_versao("v2.0.0")
    v200 = s.VERSOES / "v2.0.0"
    assert ok and (v200 / "app" / "main.py").exists() and not (v200 / ".git").exists()
    assert (s.BASE_INSTALACAO / "atual.txt").read_text(encoding="utf-8") == "v2.0.0"

    s.RAIZ = v200  # app rodando da v2.0.0 (monkeypatch de app_dev desfaz no fim)
    assert s.versao_atual() == "v2.0.0"
    p = criar(app_dev / "proj-prod")
    d = Path(p.pasta)
    (d / "projeto" / "analise" / "notas.md").write_text("dados do cliente", encoding="utf-8")
    assert s.ler_marcador(d)["versao"] == "v2.0.0"
    assert s.atualizacao_disponivel() == "v2.1.0"

    assert s.instalar_versao()[0]
    s.RAIZ = s.VERSOES / "v2.1.0"
    assert s.atualizar_projeto(p) is None
    assert "v2.1.0" in (d / "AGENTS.md").read_text(encoding="utf-8")
    assert (d / "scripts" / "novo_2_1_0.py").exists()
    assert (d / "projeto" / "analise" / "notas.md").read_text(encoding="utf-8") == "dados do cliente"

    baixados_antes = len(app_producao)
    assert s.instalar_versao("v2.0.0")[0]
    assert len(app_producao) == baixados_antes  # versão já baixada é reaproveitada
    s.RAIZ = v200
    assert s.atualizar_projeto(p) is None
    assert not (d / "scripts" / "novo_2_1_0.py").exists()  # arquivo que saiu do harness é removido
    assert (d / "projeto" / "analise" / "notas.md").exists()

    assert s.instalar_versao("v9.9.9") == (False, "Versão v9.9.9 não encontrada.")


def test_limpeza_mantem_3_versoes(app_dev, app_producao):
    s.instalar_versao("v2.1.0")
    for t in ("v1.9.0", "v1.8.0", "v1.7.0", "v2.0.0"):
        (s.VERSOES / t / "app").mkdir(parents=True, exist_ok=True)
        (s.VERSOES / t / "app" / "main.py").write_text("")
    s._limpar_versoes(manter={"v2.0.0"})
    assert s.versoes_instaladas() == ["v2.1.0", "v2.0.0", "v1.9.0"]


def test_dev_recusa_instalar_versao(app_dev):
    assert s.instalar_versao()[0] is False


@pytest.mark.lento
def test_hook_de_inicio_dentro_do_projeto(tmp_path, monkeypatch):
    """Projeto real (uv sync de verdade); o hook deve sair com código 0 e JSON válido em ASCII."""
    monkeypatch.setattr(s, "MODO_DEV", True)
    monkeypatch.setattr(s, "RAIZ", RAIZ)
    monkeypatch.setattr(s, "DADOS", tmp_path / "dados")
    monkeypatch.setattr(s, "ARQUIVO", tmp_path / "dados" / "app.json")
    p = criar(tmp_path / "proj")
    r = subprocess.run(["uv", "run", "--quiet", "python", "scripts/adaptadores/claude_code_inicio.py"],
                       cwd=p.pasta, capture_output=True, timeout=600)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    r.stdout.decode("ascii")  # só ASCII: chega íntegro em qualquer codificação
    saida = json.loads(r.stdout)
    contexto = saida["hookSpecificOutput"]["additionalContext"]
    assert "Projeto: Cli · Dev" in contexto and "escolher_workspace.py" in contexto
    assert not (Path(p.pasta) / ".venv" / "Lib" / "site-packages" / "pytest").exists()  # grupo dev fora
