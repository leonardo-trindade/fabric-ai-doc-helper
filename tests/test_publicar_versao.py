"""dev/publicar_versao.py: conferências antes de criar a tag, num repositório Git temporário (sem rede)."""
from __future__ import annotations

import importlib.util
import subprocess

import pytest

from conftest import RAIZ

_spec = importlib.util.spec_from_file_location("publicar_versao", RAIZ / "dev" / "publicar_versao.py")
pv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pv)

CHANGELOG = "# Changelog\n\n## {topo} — 2026-10-05\n- novidade\n\n## v2.1.1 — 2026-10-05\n- antes\n"


def git(raiz, *args):
    subprocess.run(["git", *args], cwd=raiz, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """'origin' (bare) + clone de trabalho em modo manutenção, com a tag v2.1.1 publicada."""
    origem, trabalho = tmp_path / "origem.git", tmp_path / "trabalho"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origem))
    git(tmp_path, "clone", "-q", str(origem), str(trabalho))
    git(trabalho, "config", "user.email", "t@t")
    git(trabalho, "config", "user.name", "t")
    (trabalho / ".agents").mkdir()
    (trabalho / ".agents" / "MANUTENCAO").write_text("")
    (trabalho / ".gitignore").write_text(".agents/MANUTENCAO\n")
    (trabalho / "CHANGELOG.md").write_text(CHANGELOG.format(topo="v2.2.0"), encoding="utf-8")
    git(trabalho, "add", ".")
    git(trabalho, "commit", "-q", "-m", "v2.2.0")
    git(trabalho, "tag", "-a", "v2.1.1", "-m", "v2.1.1")
    git(trabalho, "push", "-q", "origin", "main", "--tags")
    return trabalho


def test_caso_certo(repo):
    commit, notas = pv.conferir("v2.2.0", repo, buscar=False)
    assert len(commit) == 40 and notas.startswith("## v2.2.0") and "novidade" in notas


@pytest.mark.parametrize("tag, motivo", [
    ("v2.1.1", "já existe"),
    ("v2.1.0", "não é maior"),
    ("v2.3.0", "topo do CHANGELOG"),
    ("2.2.0", "formato"),
])
def test_versao_recusada(repo, tag, motivo):
    with pytest.raises(pv.Recusa, match=motivo):
        pv.conferir(tag, repo, buscar=False)


def test_commit_local_diferente_da_origin(repo):
    (repo / "x.txt").write_text("x")
    git(repo, "add", "x.txt")
    git(repo, "commit", "-q", "-m", "local, não publicado")
    with pytest.raises(pv.Recusa, match="origin/main"):
        pv.conferir("v2.2.0", repo, buscar=False)


def test_alteracao_nao_commitada(repo):
    (repo / "CHANGELOG.md").write_text("mexido", encoding="utf-8")
    with pytest.raises(pv.Recusa, match="não commitadas"):
        pv.conferir("v2.2.0", repo, buscar=False)


def test_fora_do_modo_manutencao_e_em_pasta_de_projeto(repo):
    (repo / ".agents" / "MANUTENCAO").unlink()
    with pytest.raises(pv.Recusa, match="manutenção"):
        pv.conferir("v2.2.0", repo, buscar=False)
    (repo / ".fabric-doc-helper.json").write_text("{}")
    with pytest.raises(pv.Recusa, match="pasta de projeto"):
        pv.conferir("v2.2.0", repo, buscar=False)
