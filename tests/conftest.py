"""Configuração comum dos testes. Nada aqui acessa o Fabric, o GitHub ou os atalhos do Windows."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
for pasta in ("scripts", "app"):
    if str(RAIZ / pasta) not in sys.path:
        sys.path.insert(0, str(RAIZ / pasta))

import guarda  # noqa: E402


@pytest.fixture
def fora_da_manutencao(monkeypatch):
    """Simula uma pasta de projeto (modo manutenção desligado), mesmo com .agents/MANUTENCAO no clone."""
    monkeypatch.setattr(guarda, "em_manutencao", lambda root=guarda.RAIZ: False)


@pytest.fixture
def em_manutencao(monkeypatch):
    monkeypatch.setattr(guarda, "em_manutencao", lambda root=guarda.RAIZ: True)


@pytest.fixture
def projeto(tmp_path):
    """Pasta de projeto mínima; `projeto(yaml)` grava o projeto.yaml e devolve a raiz."""
    def criar(yaml: str) -> Path:
        (tmp_path / "projeto").mkdir(exist_ok=True)
        (tmp_path / "projeto" / "projeto.yaml").write_text(yaml, encoding="utf-8")
        return tmp_path
    return criar
